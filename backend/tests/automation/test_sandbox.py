import asyncio

from app.automation.sandbox import run_sandboxed


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_sandbox_executes_simple_expression():
    result = _run(run_sandboxed("1 + 2", {}))
    assert result == 3


def test_sandbox_executes_multi_stmt():
    code = """
total = 0
for i in range(6):
    total += i
result = total
"""
    result = _run(run_sandboxed(code, {}))
    assert result == 15


def test_sandbox_blocks_os_import():
    with __import__("pytest").raises(Exception, match="(sandbox|blocked|not allowed|Forbidden)"):
        _run(run_sandboxed("import os; os.listdir('/')", {}))


def test_sandbox_blocks_subprocess():
    with __import__("pytest").raises(Exception, match="(sandbox|blocked|not allowed|Forbidden)"):
        _run(run_sandboxed("import subprocess; subprocess.run(['ls'])", {}))


def test_sandbox_blocks_dynamic_import():
    """Even via getattr, __import__ is blocked at the module level."""
    with __import__("pytest").raises(Exception, match="(sandbox|blocked|not allowed|Forbidden)"):
        _run(run_sandboxed("__import__('os').system('echo pwned')", {}))


def test_sandbox_allows_safe_stdlib():
    code = """
import json
import re
import math
payload = json.dumps({'x': math.sqrt(16)})
m = re.match(r'.*4.*', payload)
"""
    result = _run(run_sandboxed(code, {}))
    assert result is not None


def test_sandbox_exposes_inputs_and_bindings():
    code = """
bindings['_touched'] = True
result = inputs.get('cliente', {}).get('nome', 'unknown')
"""
    ns = {"inputs": {"cliente": {"nome": "Ana"}}, "bindings": {}}
    _run(run_sandboxed(code, ns))
    assert ns["bindings"]["_touched"] is True


def test_sandbox_timeout_returns_best_effort():
    """A long-running script is killed at the timeout."""
    import time
    t0 = time.time()
    try:
        _run(run_sandboxed("import time; time.sleep(10)", {}, timeout_s=1))
    except Exception:
        pass
    elapsed = time.time() - t0
    assert elapsed < 8, f"sandbox took {elapsed:.1f}s, expected < 8s"
