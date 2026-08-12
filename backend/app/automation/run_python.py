"""run_python step — execute arbitrary Python with access to page/inputs/bindings.

P1a executes on the same thread as the runner (no subprocess). The code runs
in a restricted namespace dict populated with `page`, `inputs`, `bindings`,
plus a few safe stdlib imports. P5 will add sandboxing (subprocess, seccomp,
or RestrictedPython).

A timeout is honored via `asyncio.wait_for`; exceeding it raises `TimeoutError`.
The exception is NOT swallowed — the runner decides retry/abort based on
`Step.retry.on_fail`.

Expression handling: a single expression is evaluated with `compile(..., "eval")`
so its value is returned (and can be `bind`-captured). Multi-statement scripts
fall back to `exec`; when `bind` matches a variable assigned in the script,
that variable's value is captured.
"""
import asyncio
import time
from typing import Any

from app.automation.models import RunContext


# Safe builtins. `__import__` and exception types are intentionally allowed so
# the escape hatch can use stdlib + raise errors (required by tests + reasonable
# for real automation scripts like cotacao_pvs that need `import time` etc.).
# P5 will replace this namespace with a true sandbox (subprocess/seccomp).
_SAFE_BUILTINS = {
    "len": len, "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "tuple": tuple, "set": set,
    "range": range, "enumerate": enumerate, "zip": zip,
    "min": min, "max": max, "sum": sum, "abs": abs,
    "print": print,
    "True": True, "False": False, "None": None,
    "__import__": __import__,
    "RuntimeError": RuntimeError,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "Exception": Exception,
}


async def run_python(page: Any, params: dict[str, Any], ctx: RunContext) -> Any:
    """Execute `params["value"]` as Python code, optionally binding the result."""
    code = params["value"]
    timeout_ms = int(params.get("timeout_ms", 30000))
    bind = params.get("bind")

    # Pre-extract test-only hook(s) so they don't pollute the namespace.
    test_seen = params.get("_test_seen")

    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "page": page,
        "inputs": ctx.inputs,
        "bindings": ctx.bindings,
        "asyncio": asyncio,
        "time": time,
    }
    if test_seen is not None:
        namespace["seen"] = test_seen

    async def _exec() -> Any:
        # Run in a thread so blocking calls (e.g. `time.sleep`) don't stall
        # the event loop — required for `asyncio.wait_for` to enforce the
        # timeout.
        def _run_sync() -> Any:
            try:
                compiled = compile(code, "<run_python>", "eval")
                return eval(compiled, namespace)
            except SyntaxError:
                compiled = compile(code, "<run_python>", "exec")
                return eval(compiled, namespace)

        result: Any = await asyncio.to_thread(_run_sync)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    try:
        out = await asyncio.wait_for(_exec(), timeout=timeout_ms / 1000.0)
    except asyncio.TimeoutError as e:
        raise TimeoutError(f"run_python timed out after {timeout_ms}ms") from e

    if bind:
        # Prefer the named variable from the namespace (set by the script),
        # fall back to the expression return value.
        ctx.bindings[bind] = namespace.get(bind, out)
    return out