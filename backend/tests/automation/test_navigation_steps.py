import asyncio
import pytest

from app.automation.steps.navigation import goto, wait_for
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakePage:
    def __init__(self):
        self.goto_calls = []
        self.waits = []

    async def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))
        class _Resp:
            status = 200
        return _Resp()

    async def wait_for_selector(self, selector, **kwargs):
        self.waits.append((selector, kwargs))
        class _Loc:
            pass
        return _Loc()


def test_goto_resolves_url_through_bindings():
    page = _FakePage()
    ctx = RunContext(inputs={"base": "https://app.apvs.vc"})
    _run(goto(page, {"url": "{{input.base}}/cotacao"}, ctx))
    assert page.goto_calls == [("https://app.apvs.vc/cotacao", {"timeout": 30000, "wait_until": "domcontentloaded"})]


def test_goto_with_custom_timeout():
    page = _FakePage()
    _run(goto(page, {"url": "https://x", "timeout_ms": 5000}, RunContext()))
    assert page.goto_calls[0][1]["timeout"] == 5000


def test_wait_for_returns_locator():
    page = _FakePage()
    loc = _run(wait_for(page, {"selector": ".dash", "timeout_ms": 10000}, RunContext()))
    assert loc is not None
    assert page.waits == [(".dash", {"timeout": 10000, "state": "visible"})]