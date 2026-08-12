import asyncio
import pytest

from app.automation.run_python import run_python
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_run_python_returns_value():
    page = object()
    ctx = RunContext()
    _run(run_python(page, {"value": "1 + 2", "bind": "sum"}, ctx))
    assert ctx.bindings["sum"] == 3


def test_run_python_no_bind_drops_return():
    page = object()
    ctx = RunContext()
    _run(run_python(page, {"value": "1 + 2"}, ctx))
    assert "sum" not in ctx.bindings


def test_run_python_receives_page_inputs_bindings():
    seen = {}
    page = type("P", (), {"url": "https://x"})()
    ctx = RunContext(inputs={"k": 1}, bindings={"b": 2})
    _run(run_python(page, {
        "value": (
            "seen['page'] = page.url; "
            "seen['input'] = inputs['k']; "
            "seen['binding'] = bindings['b']"
        ),
        "_test_seen": seen,
    }, ctx))
    assert seen["page"] == "https://x"
    assert seen["input"] == 1
    assert seen["binding"] == 2


def test_run_python_timeout_enforced():
    page = object()
    ctx = RunContext()
    with pytest.raises(TimeoutError, match="timed out"):
        _run(run_python(page, {"value": "import time; time.sleep(2)", "timeout_ms": 100}, ctx))


def test_run_python_exception_propagates():
    page = object()
    ctx = RunContext()
    with pytest.raises(RuntimeError, match="boom"):
        _run(run_python(page, {"value": "raise RuntimeError('boom')"}, ctx))


def test_run_python_multiline_code():
    """A multi-line script with imports + statements should work."""
    page = object()
    ctx = RunContext()
    code = """
total = 0
for i in range(5):
    total += i
"""
    _run(run_python(page, {"value": code, "bind": "total"}, ctx))
    assert ctx.bindings["total"] == 10
