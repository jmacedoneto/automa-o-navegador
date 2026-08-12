import asyncio
import os

from app.automation.runner import NavRunner, NavRunnerConfig
from app.automation.models import Step


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _RecordingPage:
    def __init__(self):
        self.actions = []
        self.shots = 0

    async def goto(self, url, **kwargs):
        self.actions.append(("goto", url))
        class _R:
            status = 200
        return _R()

    async def wait_for_selector(self, selector, **kwargs):
        self.actions.append(("wait_for", selector))
        class _L:
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
                self.__class__.clicked = getattr(self.__class__, "clicked", 0) + 1
            async def fill(self, value, **kw):
                self.__class__.filled = getattr(self.__class__, "filled", []) + [(selector, value)]
        return _L()

    def get_by_text(self, text, **kwargs):
        self.actions.append(("get_by_text", text, kwargs))
        class _L:
            @property
            def first(self):
                return self
            async def wait_for(self, **kw):
                return self
        return _L()

    async def screenshot(self, **kwargs):
        self.shots += 1
        return b"PNG"


class _RecordingBrowser:
    def __init__(self):
        self.page = _RecordingPage()

    async def new_page(self):
        return self.page

    async def close(self):
        pass


class _FakePW:
    def __init__(self, browser):
        self._browser = browser

    @property
    def chromium(self):
        browser = self._browser
        class _L:
            async def connect_over_cdp(self, endpoint):
                browser.page.actions.append(("connect", endpoint))
                return browser
        return _L()

    async def stop(self):
        pass


async def _fake_connect(endpoint):
    browser = _RecordingBrowser()
    pw = _FakePW(browser)
    return pw, browser


def test_runner_executes_steps(monkeypatch, tmp_path):
    monkeypatch.setattr("app.automation.runner._connect_playwright", _fake_connect)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    steps = [
        Step.from_dict({"id": "open", "goto": "https://example.com"}),
        Step.from_dict({"id": "wait", "wait_for": {"selector": "h1", "timeout_ms": 10000}}),
        Step.from_dict({"id": "click", "click": {"selector": "button"}}),
    ]
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-1",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    result = _run(runner.run_steps(steps=steps, inputs={}))

    assert result.status == "success"
    assert ("goto", "https://example.com") in result.page.actions
    assert ("wait_for", "h1") in result.page.actions
    assert ("locator", "button") in result.page.actions
    # At least one screenshot was taken per successful step
    assert result.page.shots >= 3


def test_runner_failed_step_records_error_and_screenshot(monkeypatch, tmp_path):
    monkeypatch.setattr("app.automation.runner._connect_playwright", _fake_connect)

    # Make goto raise (simulating broken selector / network issue)
    class _BrokenPage(_RecordingPage):
        async def goto(self, url, **kwargs):
            self.actions.append(("goto", url))
            raise RuntimeError("navigation failed")

    class _BrokenBrowser(_RecordingBrowser):
        def __init__(self):
            super().__init__()
            self.page = _BrokenPage()

    async def _broken_connect(endpoint):
        browser = _BrokenBrowser()
        pw = _FakePW(browser)
        return pw, browser

    monkeypatch.setattr("app.automation.runner._connect_playwright", _broken_connect)

    steps = [Step.from_dict({"id": "open", "goto": "https://x"})]
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-2",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    result = _run(runner.run_steps(steps=steps, inputs={}))

    assert result.status == "failed"
    assert len(result.errors) == 1
    assert "open" in result.errors[0] and "navigation failed" in result.errors[0]
    # on_fail screenshot was attempted
    assert any("on_fail" in k for k in result.screenshot_keys)
