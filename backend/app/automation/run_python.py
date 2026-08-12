"""run_python step — execute arbitrary code in a subprocess sandbox.

P5 implementation: code runs in a separate Python process via the
`run_sandboxed` helper. The sandbox denies `os`, `subprocess`, `importlib`,
`ctypes`, `socket`, etc. Enforces a timeout via process termination.
"""
from typing import Any

from app.automation.models import RunContext
from app.automation.sandbox import run_sandboxed


async def run_python(page: Any, params: dict[str, Any], ctx: RunContext) -> Any:
    """Execute `params["value"]` as Python code in a subprocess sandbox."""
    code = params["value"]
    timeout_ms = int(params.get("timeout_ms", 30000))
    bind = params.get("bind")

    ns = {
        "page": page,
        "inputs": ctx.inputs,
        "bindings": ctx.bindings,
        "asyncio": __import__("asyncio"),
    }
    # Preserve the legacy `_test_seen` hook used by test_run_python.
    test_seen = params.get("_test_seen")
    if test_seen is not None:
        ns["seen"] = test_seen
    out = await run_sandboxed(code, ns, timeout_s=max(1, timeout_ms // 1000))
    if bind:
        # The sandbox returns either the eval-mode value or, for exec-mode
        # scripts without an explicit `result = ...`, a dict of user vars.
        # Prefer the named variable when the return is a dict.
        if isinstance(out, dict) and bind in out:
            ctx.bindings[bind] = out[bind]
        else:
            ctx.bindings[bind] = out
    return out
