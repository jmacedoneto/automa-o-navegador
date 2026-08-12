import asyncio
from unittest.mock import MagicMock

from app.automation.runner import NavRunner, NavRunnerConfig, set_step_log_writer, _step_log_writer
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


class _FakeBrowser:
    def __init__(self):
        self.page = _FakePage()

    async def new_page(self):
        return self.page

    async def close(self):
        pass


class _FakePW:
    @property
    def chromium(self):
        class _L:
            async def connect_over_cdp(self, _):
                return _FakeBrowser()
        return _L()

    async def stop(self):
        pass


async def _connect(_):
    return _FakePW(), _FakeBrowser()


def test_runner_invokes_step_log_writer(monkeypatch, tmp_path):
    writer = MagicMock()
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)

    # Save and restore the module-level writer.
    original = _step_log_writer
    set_step_log_writer(writer)
    try:
        steps = [Step.from_dict({"id": "open", "goto": "https://x"})]
        cfg = NavRunnerConfig(
            browser_endpoint="ws://fake",
            run_id="r-1",
            screenshot_dir=str(tmp_path),
        )
        runner = NavRunner(cfg=cfg)
        _run(runner.run_steps(steps=steps, inputs={}))

        # Writer called at least twice: starting + finished (ok).
        assert writer.call_count >= 2
        # Inspect the first call's kwargs.
        first_call = writer.call_args_list[0]
        assert first_call.kwargs.get("run_id") == "r-1"
        assert first_call.kwargs.get("step_id") == "open"
    finally:
        set_step_log_writer(original)


def test_runner_no_writer_no_error(monkeypatch, tmp_path):
    """When no writer is set, the runner still works (no-op)."""
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)
    original = _step_log_writer
    set_step_log_writer(None)
    try:
        steps = [Step.from_dict({"id": "open", "goto": "https://x"})]
        cfg = NavRunnerConfig(
            browser_endpoint="ws://fake",
            run_id="r-2",
            screenshot_dir=str(tmp_path),
        )
        runner = NavRunner(cfg=cfg)
        result = _run(runner.run_steps(steps=steps, inputs={}))
        assert result.status == "success"
    finally:
        set_step_log_writer(original)


def test_runner_failed_step_emits_failed_event(monkeypatch, tmp_path):
    writer = MagicMock()
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)

    class _BrokenPage(_FakePage):
        async def goto(self, url, **kw):
            raise RuntimeError("navigation failed")

    class _BrokenBrowser(_FakeBrowser):
        def __init__(self):
            super().__init__()
            self.page = _BrokenPage()

    async def _broken_connect(_):
        return _FakePW(), _BrokenBrowser()

    monkeypatch.setattr("app.automation.runner._connect_playwright", _broken_connect)

    original = _step_log_writer
    set_step_log_writer(writer)
    try:
        steps = [Step.from_dict({"id": "open", "goto": "https://x"})]
        cfg = NavRunnerConfig(
            browser_endpoint="ws://fake",
            run_id="r-3",
            screenshot_dir=str(tmp_path),
        )
        runner = NavRunner(cfg=cfg)
        result = _run(runner.run_steps(steps=steps, inputs={}))
        assert result.status == "failed"
        # Last call is a "failed" event.
        failed_calls = [c for c in writer.call_args_list if c.kwargs.get("status") == "failed"]
        assert len(failed_calls) >= 1
        assert "navigation failed" in (failed_calls[-1].kwargs.get("error") or "")
    finally:
        set_step_log_writer(original)
