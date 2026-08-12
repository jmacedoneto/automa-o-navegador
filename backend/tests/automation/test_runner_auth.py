import asyncio
from unittest.mock import AsyncMock

from app.automation.runner import NavRunner, NavRunnerConfig
from app.automation.auth import AuthSpec
from app.automation.models import Step


def run(coro):
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
        self.page = _FakePage()

    async def new_page(self):
        return self.page

    async def close(self):
        pass


class _FakePW:
    @property
    def chromium(self):
        browser = _FakeBrowser()
        class _L:
            async def connect_over_cdp(self, _):
                return browser
        return _L()

    async def stop(self):
        pass


async def _connect(_):
    return _FakePW(), _FakeBrowser()


def test_run_steps_with_auth_runs_auth_first(monkeypatch, tmp_path):
    """When `auth` is supplied, the runner calls run_auth before any step."""
    monkeypatch.setattr("app.automation.runner._connect_playwright", _connect)

    fake_run_auth = AsyncMock()
    monkeypatch.setattr("app.automation.runner.run_auth", fake_run_auth)

    auth_spec = AuthSpec(
        type="form_login",
        url="https://app.apvs.vc/home",
        credentials_ref="apvs_login",
        selectors={"user": "input", "pass": "input", "submit": "button"},
        success_assert={"selector": ".dashboard", "timeout_ms": 5000},
    )
    cfg = NavRunnerConfig(
        browser_endpoint="ws://fake",
        run_id="r-1",
        screenshot_dir=str(tmp_path),
    )
    runner = NavRunner(cfg=cfg)
    steps = [Step.from_dict({"id": "noop", "goto": "https://x.example"})]
    result = run(runner.run_steps(steps=steps, inputs={}, credentials={}, auth=auth_spec))
    assert result.status == "success"
    fake_run_auth.assert_called_once()
    args, kwargs = fake_run_auth.call_args
    assert kwargs["spec"] is auth_spec
