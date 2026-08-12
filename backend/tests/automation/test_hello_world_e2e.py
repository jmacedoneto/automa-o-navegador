"""Offline end-to-end test using a fake Playwright that fakes example.com.

Does NOT hit the internet — proves the runner end-to-end given a faked browser.
"""
import asyncio

from app.automation.runner import NavRunner, NavRunnerConfig
from app.automation.models import Step


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _H1Content:
    async def text_content(self):
        return "Example Domain"


class _H1Wait:
    async def wait_for(self, **kwargs):
        return self


class _FakeLocator:
    @property
    def first(self):
        return self

    async def click(self, **kwargs):
        return None

    async def fill(self, value, **kwargs):
        return None

    async def wait_for(self, **kwargs):
        return self


class _FakePage:
    def __init__(self):
        self.url = ""
        self.shots = 0

    async def goto(self, url, **kwargs):
        self.url = url

    async def wait_for_selector(self, selector, **kwargs):
        if selector == "h1":
            return _H1Content()
        raise AssertionError(f"unexpected selector {selector}")

    def get_by_text(self, text, **kwargs):
        # The h1 we returned has text_content "Example Domain"
        return _FakeLocator()

    async def screenshot(self, **kwargs):
        self.shots += 1
        return b"PNG"

    def locator(self, selector):
        return _FakeLocator()


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
        class _Launcher:
            async def connect_over_cdp(self, _endpoint):
                return _FakeBrowser()
        return _Launcher()

    async def stop(self):
        pass


async def _fake_connect(_endpoint):
    return _FakePW(), _FakeBrowser()


def test_hello_world_steps_pass(monkeypatch, tmp_path):
    import json
    import pathlib
    monkeypatch.setattr("app.automation.runner._connect_playwright", _fake_connect)

    plan_path = pathlib.Path("/root/navegador/automa-o-navegador/.worktrees/navrunner-p0/examples/hello_world/steps.json")
    payload = json.loads(plan_path.read_text())

    steps = [Step.from_dict(s) for s in payload["steps"]]
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="hello-1",
        screenshot_dir=str(tmp_path / "shots"),
    )
    runner = NavRunner(cfg=cfg)
    result = _run(runner.run_steps(steps=steps, inputs={}))

    assert result.status == "success"
    assert result.errors == []
    # One after-shot per successful step = 3
    assert result.page.shots >= 3
    assert result.page.url == "https://example.com"
