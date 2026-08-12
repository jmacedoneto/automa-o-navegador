import asyncio
from unittest.mock import MagicMock

from app.automation.runner import NavRunner, NavRunnerConfig
from app.automation.models import Step


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakePage:
    def __init__(self):
        self.actions = []

    async def goto(self, url, **kw):
        self.actions.append(("goto", url))

    async def screenshot(self, **kw):
        return b"PNG"

    async def wait_for_selector(self, selector, **kw):
        self.actions.append(("wait_for", selector))
        class _L:
            pass
        return _L()


class _FakeBrowser:
    def __init__(self):
        self._page = _FakePage()

    async def new_page(self):
        return self._page

    async def close(self):
        pass


class _FakePW:
    @property
    def chromium(self):
        b = _FakeBrowser()
        class _L:
            async def connect_over_cdp(self, _):
                return b
        return _L()

    async def stop(self):
        pass


async def _connect(_):
    return _FakePW(), _FakeBrowser()


def test_visit_child_runs_dict_step(monkeypatch, tmp_path):
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)
    writer = MagicMock()
    from app.automation.runner import set_step_log_writer, _step_log_writer
    original = _step_log_writer
    set_step_log_writer(writer)
    try:
        steps = [
            Step.from_dict({"id": "parent", "for_each": {
                "items": ["a", "b"],
                "as": "x",
                "steps": [{"id": "child", "goto": "https://{{x}}"}],
            }}),
        ]
        cfg = NavRunnerConfig(
            browser_endpoint="ws://fake",
            run_id="r-1",
            screenshot_dir=str(tmp_path),
        )
        runner = NavRunner(cfg=cfg)
        result = _run(runner.run_steps(steps=steps, inputs={}))
        assert result.status == "success"
        gotos = [a for a in result.page.actions if a[0] == "goto"]
        assert gotos == [("goto", "https://a"), ("goto", "https://b")]
        child_started = [c for c in writer.call_args_list if c.kwargs.get("step_id") == "child" and c.kwargs.get("status") == "running"]
        assert len(child_started) == 2
    finally:
        set_step_log_writer(original)


def test_visit_child_runs_step_object(monkeypatch, tmp_path):
    """When `for_each.steps` is a list of Step objects, it still works."""
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)
    steps = [
        Step.from_dict({"id": "parent", "for_each": {
            "items": [1, 2],
            "as": "n",
            "steps": [
                Step.from_dict({"id": "child", "goto": "https://{{n}}"}),
            ],
        }}),
    ]
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-2",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    result = _run(runner.run_steps(steps=steps, inputs={}))
    assert result.status == "success"
    gotos = [a for a in result.page.actions if a[0] == "goto"]
    assert gotos == [("goto", "https://1"), ("goto", "https://2")]


def test_visit_child_inherits_retry_policy(monkeypatch, tmp_path):
    """A child step with `retry` should be retried via with_retry."""
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)

    attempts = {"count": 0}

    class _FlakyPage(_FakePage):
        async def goto(self, url, **kw):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("flaky")
            self.actions.append(("goto", url))

    class _FlakyBrowser(_FakeBrowser):
        def __init__(self):
            self._page = _FlakyPage()

    async def _flaky_connect(_):
        class _P:
            @property
            def chromium(self):
                class _L:
                    async def connect_over_cdp(self, _):
                        return _FlakyBrowser()
                return _L()
            async def stop(self):
                pass
        return _P(), _FlakyBrowser()

    monkeypatch.setattr("app.automation.runner._connect_playwright", _flaky_connect)

    steps = [
        Step.from_dict({"id": "parent", "for_each": {
            "items": ["x"],
            "as": "v",
            "steps": [{"id": "child", "goto": "https://x", "retry": {"attempts": 3, "initial_delay_ms": 1}}],
        }}),
    ]
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-3",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    result = _run(runner.run_steps(steps=steps, inputs={}))
    assert result.status == "success"
    assert attempts["count"] == 3
