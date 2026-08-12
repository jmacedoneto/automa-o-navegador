import asyncio
import pytest

from app.automation.auth import AuthSpec, parse_auth, run_auth
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_parse_auth_form_login():
    raw = {
        "type": "form_login",
        "url": "https://app.apvs.vc/login",
        "credentials_ref": "app_login",
        "selectors": {"user": "#cnpj", "pass": "#senha", "submit": "button[type=submit]"},
        "success_assert": {"selector": ".dashboard", "timeout_ms": 15000},
    }
    spec = parse_auth(raw)
    assert spec.type == "form_login"
    assert spec.url == "https://app.apvs.vc/login"
    assert spec.credentials_ref == "app_login"
    assert spec.selectors == {"user": "#cnpj", "pass": "#senha", "submit": "button[type=submit]"}
    assert spec.success_assert == {"selector": ".dashboard", "timeout_ms": 15000}


def test_parse_auth_unknown_type_raises():
    with pytest.raises(ValueError, match="Unsupported auth type"):
        parse_auth({"type": "oauth_magic", "url": "x"})


def test_parse_auth_missing_url_raises():
    with pytest.raises(ValueError, match="missing required field"):
        parse_auth({"type": "form_login"})


def test_parse_auth_success_assert_required():
    with pytest.raises(ValueError, match="success_assert"):
        parse_auth({"type": "form_login", "url": "https://x", "credentials_ref": "y"})


def test_run_auth_fills_and_submits():
    calls = {"goto": [], "fill": [], "click": [], "wait": []}

    class _Page:
        async def goto(self, url, **kw):
            calls["goto"].append((url, kw))

        async def fill(self, selector, value, **kw):
            calls["fill"].append((selector, value, kw))

        async def click(self, selector, **kw):
            calls["click"].append((selector, kw))

        async def wait_for_selector(self, selector, **kw):
            calls["wait"].append((selector, kw))
            return object()

    page = _Page()
    spec = AuthSpec(
        type="form_login",
        url="https://app.apvs.vc/login",
        credentials_ref="app_login",
        selectors={"user": "#cnpj", "pass": "#senha", "submit": "button[type=submit]"},
        success_assert={"selector": ".dashboard", "timeout_ms": 5000},
    )
    ctx = RunContext(credentials={"app_login": {"user": "123", "pass": "secret"}})
    _run(run_auth(page, spec, ctx))
    assert calls["goto"] == [("https://app.apvs.vc/login", {"timeout": 30000, "wait_until": "domcontentloaded"})]
    assert calls["fill"] == [
        ("#cnpj", "123", {"timeout": 15000}),
        ("#senha", "secret", {"timeout": 15000}),
    ]
    assert calls["click"] == [("button[type=submit]", {"timeout": 30000})]
    assert calls["wait"] == [(".dashboard", {"timeout": 5000, "state": "visible"})]


def test_run_auth_raises_on_missing_credentials():
    class _Page:
        async def goto(self, url, **kw):
            return None

    page = _Page()
    spec = AuthSpec(
        type="form_login",
        url="https://x",
        credentials_ref="missing",
        selectors={"user": "#u", "pass": "#p", "submit": "button"},
        success_assert={"selector": ".ok", "timeout_ms": 1000},
    )
    ctx = RunContext(credentials={})
    with pytest.raises(KeyError, match="missing"):
        _run(run_auth(page, spec, ctx))