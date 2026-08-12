import asyncio

from app.automation.interpreter import execute_step
from app.automation.models import Step, RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakePage:
    def __init__(self):
        self.actions = []

    async def goto(self, url, **kwargs):
        self.actions.append(("goto", url))
        class _R:
            status = 200
        return _R()

    async def wait_for_selector(self, selector, **kwargs):
        self.actions.append(("wait_for_selector", selector))
        class _L:
            pass
        return _L()

    async def get_by_text(self, text, **kwargs):
        self.actions.append(("get_by_text", text, kwargs))
        class _L:
            @property
            def first(self):
                return self
            async def wait_for(self, **kwargs):
                return self
            async def text_content(self):
                return "OK"
        return _L()

    def locator(self, selector):
        self.actions.append(("locator", selector))
        class _L:
            @property
            def first(self):
                return self
            async def click(self, **kw):
                _FakePage.clicked.append(selector)
            async def fill(self, value, **kw):
                _FakePage.filled.append((selector, value))
        _FakePage.clicked = []
        _FakePage.filled = []
        return _L()


def test_execute_step_dispatches_goto():
    page = _FakePage()
    step = Step.from_dict({"id": "s1", "goto": "https://x"})
    _run(execute_step(page, step, RunContext()))
    assert ("goto", "https://x") in page.actions


def test_execute_step_dispatches_click():
    page = _FakePage()
    step = Step.from_dict({"id": "s1", "click": {"selector": "button"}})
    _run(execute_step(page, step, RunContext()))
    assert ("locator", "button") in page.actions


def test_execute_step_dispatches_fill():
    page = _FakePage()
    step = Step.from_dict({"id": "s1", "fill": {"#f": "v"}})
    _run(execute_step(page, step, RunContext()))
    assert ("locator", "#f") in page.actions
    assert _FakePage.filled == [("#f", "v")]


def test_execute_step_interpolates_params():
    page = _FakePage()
    step = Step.from_dict({"id": "s1", "goto": "{{input.u}}"})
    _run(execute_step(page, step, RunContext(inputs={"u": "https://y"})))
    assert ("goto", "https://y") in page.actions


def test_execute_step_unknown_action_raises():
    page = _FakePage()
    step = Step(id="s1", action="frobnicate", params={})
    try:
        _run(execute_step(page, step, RunContext()))
    except NotImplementedError as e:
        assert "frobnicate" in str(e)
    else:
        raise AssertionError("expected NotImplementedError")
