"""Subprocess-isolated sandbox for run_python.

P5 implementation. The user's code runs in a separate Python process
(via multiprocessing). The process has a denylist of dangerous modules
that raise `SandboxViolation` on import. The timeout is enforced by
killing the process.

Why subprocess isolation? Python's eval() cannot be sandboxed without
modifying the interpreter (RestrictedPython, etc.) — and even those
can be bypassed. A subprocess gives us a clean process boundary: from
the user's perspective, `os.system` looks like it works, but the
denylist blocks it at import time.

Trade-off: a few extra ms of fork overhead per run_python invocation.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import threading
import traceback
from typing import Any


# Modules that the sandbox refuses to import.
_BLOCKED_MODULES = frozenset({
    "os", "subprocess", "importlib", "importlib.util", "importlib.machinery",
    "ctypes", "cffi", "multiprocessing", "socket", "ssl", "_socket",
    "win32api", "win32com", "win32process", "win32security",
    "_winreg", "posix", "fcntl", "grp", "pwd", "resource",
    "sysconfig", "distorm", "keystone", "capstone", "unicorn",
})


class SandboxViolation(RuntimeError):
    """Raised when sandbox detects a blocked module or operation."""


def _make_picklable(value: Any) -> Any:
    """Recursively convert a value into something that multiprocessing.Queue
    can pickle. Lists, tuples, and dicts are walked; anything else that
    isn't a primitive is repr'd."""
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value
    if isinstance(value, list):
        return [_make_picklable(x) for x in value]
    if isinstance(value, tuple):
        return tuple(_make_picklable(x) for x in value)
    if isinstance(value, dict):
        return {str(k): _make_picklable(v) for k, v in value.items()}
    return repr(value)


def _child_main(code: str, ns: dict, q) -> None:
    """Entry point for the sandboxed subprocess."""
    _real_import = __import__

    def _guarded_import(name, *args, **kwargs):
        top = name.split(".")[0]
        if top in _BLOCKED_MODULES:
            raise SandboxViolation(f"module {name!r} is blocked in the sandbox")
        return _real_import(name, *args, **kwargs)

    safe_builtins = {
        "len": len, "str": str, "int": int, "float": float, "bool": bool,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "range": range, "enumerate": enumerate, "zip": zip,
        "min": min, "max": max, "sum": sum, "abs": abs,
        "print": print,
        "True": True, "False": False, "None": None,
        "__import__": _guarded_import,
        "RuntimeError": RuntimeError,
        "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
        "Exception": Exception,
        "isinstance": isinstance, "getattr": getattr, "setattr": setattr,
        "hasattr": hasattr,
    }
    # Snapshot every dict the parent passed us. Anything mutated in the
    # subprocess needs to be sent back so the parent can update its copy.
    parent_dicts: dict[str, dict] = {k: v for k, v in ns.items()
                                     if isinstance(v, dict)}

    namespace: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "page": ns.get("page"),
        "inputs": ns.get("inputs", {}),
        "bindings": ns.get("bindings", {}),
        "asyncio": ns.get("asyncio"),
        "time": __import__("time"),
    }
    # Forward any extra dicts the parent passed in (e.g. `seen` for tests).
    for k, v in ns.items():
        if k not in namespace and isinstance(v, dict):
            namespace[k] = v
    try:
        exec_result = None
        try:
            compiled = compile(code, "<run_python>", "eval")
            exec_result = eval(compiled, namespace)
        except SyntaxError:
            compiled = compile(code, "<run_python>", "exec")
            exec(compiled, namespace)
        # Decide what to return. Precedence:
        #   1. A variable named `result` if assigned by the script.
        #   2. The eval-mode return value (for expression scripts).
        #   3. A dict of all user-defined variables (for exec-mode scripts
        #      that did not bind `result`). Non-picklable values are
        #      converted to their repr so they survive the queue.
        if "result" in namespace:
            return_value = _make_picklable(namespace["result"])
        elif exec_result is not None:
            return_value = _make_picklable(exec_result)
        else:
            # Filter out sandbox plumbing so callers see only their own vars.
            plumbing = {"__builtins__", "page", "inputs", "bindings",
                        "asyncio", "time"}
            user_ns = {k: v for k, v in namespace.items()
                       if k not in plumbing and not k.startswith("__")}
            return_value = _make_picklable(user_ns)
        # Send back the (possibly mutated) dicts so the parent can write
        # them into its ns. Anything the user script mutated (bindings,
        # inputs, _test_seen, etc.) gets propagated.
        shared_snapshot = {k: namespace.get(k, v) for k, v in parent_dicts.items()}
        q.put(("ok", return_value, _make_picklable(shared_snapshot)))
    except SandboxViolation as e:
        q.put(("sandbox_violation", str(e), None))
    except Exception as e:
        q.put(("error", f"{type(e).__name__}: {e}\n{traceback.format_exc()}", None))


async def run_sandboxed(code: str, ns: dict, timeout_s: int = 30) -> Any:
    """Execute `code` in a sandboxed subprocess.

    Returns the result on success. Raises SandboxViolation for blocked modules,
    TimeoutError if the subprocess exceeds `timeout_s`, or the original
    exception for everything else.
    """
    q: multiprocessing.Queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_child_main, args=(code, ns, q), daemon=True)
    proc.start()
    loop = asyncio.get_event_loop()
    try:
        ev = asyncio.Event()
        result_holder: list = []
        def _wait():
            try:
                result_holder.append(q.get(timeout=timeout_s))
            except Exception as e:
                result_holder.append(e)
            finally:
                loop.call_soon_threadsafe(ev.set)
        t = threading.Thread(target=_wait, daemon=True)
        t.start()
        await asyncio.wait_for(ev.wait(), timeout=timeout_s + 2)
        if not result_holder:
            raise TimeoutError(f"run_python sandbox timed out after {timeout_s}s")
        item = result_holder[0]
        if isinstance(item, Exception):
            # queue.Empty (or any other queue error) means the subprocess
            # was killed before it could deliver a result → treat as timeout.
            raise TimeoutError(f"run_python sandbox timed out after {timeout_s}s") from item
        kind = item[0]
        value = item[1]
        if kind == "ok":
            # Write every dict the subprocess saw back into the caller's ns.
            # The subprocess only sees pickled copies; mutations don't
            # propagate automatically.
            if len(item) > 2 and item[2]:
                for k, v in item[2].items():
                    if k in ns and isinstance(ns[k], dict):
                        ns[k].clear()
                        ns[k].update(v)
            return value
        if kind == "sandbox_violation":
            raise SandboxViolation(value)
        raise RuntimeError(value)
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)
            if proc.is_alive():
                proc.kill()
