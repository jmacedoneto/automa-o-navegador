import asyncio
import pytest

from app.automation.steps.assertion import assert_text
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeLocator:
    def __init__(self, text, *, visible=True):
        self._text = text
        self._visible = visible

    @property
    def first(self):
        return self

    async def wait_for(self, **kwargs):
        if not self._visible:
            raise TimeoutError(f"wait_for timed out; kwargs={kwargs}")
        return self

    async def text_content(self):
        return self._text


class _FakePage:
    def __init__(self, locator):
        self._locator = locator
        self.calls = []

    def get_by_text(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return self._locator


def test_assert_text_succeeds_when_visible():
    loc = _FakeLocator("Salvo com sucesso")
    page = _FakePage(loc)
    _run(assert_text(page, {"text": "Salvo com sucesso"}, RunContext()))
    assert page.calls == [("Salvo com sucesso", {"exact": True})]


def test_assert_text_fails_when_missing():
    loc = _FakeLocator("algo diferente", visible=False)
    page = _FakePage(loc)
    with pytest.raises(AssertionError, match="not visible"):
        _run(assert_text(page, {"text": "Esperado", "timeout_ms": 100}, RunContext()))


def test_assert_text_resolves_interpolated_text():
    loc = _FakeLocator("OK")
    page = _FakePage(loc)
    ctx = RunContext(inputs={"expected": "OK"})
    _run(assert_text(page, {"text": "{{input.expected}}"}, ctx))
    assert page.calls == [("OK", {"exact": True})]
