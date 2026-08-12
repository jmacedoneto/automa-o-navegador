import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.automation.auth import parse_auth, run_auth, AuthSpec
from app.automation.models import RunContext


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_parse_auth_cookie_reuse():
    raw = {
        "type": "cookie_reuse",
        "url": "https://app.apvs.vc/dashboard",
        "cookies": [{"name": "sessionid", "value": "abc", "domain": ".apvs.vc"}],
        "success_assert": {"selector": ".dashboard", "timeout_ms": 30000},
    }
    spec = parse_auth(raw)
    assert spec.type == "cookie_reuse"
    assert spec.cookies == [{"name": "sessionid", "value": "abc", "domain": ".apvs.vc"}]


def test_parse_auth_otp_via_telegram():
    raw = {
        "type": "otp_via_telegram",
        "url": "https://app.apvs.vc/login",
        "credentials_ref": "apvs_login",
        "telegram_chat_id": "123456",
        "otp_selector": "input[name=otp]",
        "submit_selector": "button[type=submit]",
        "success_assert": {"selector": ".dashboard", "timeout_ms": 30000},
    }
    spec = parse_auth(raw)
    assert spec.type == "otp_via_telegram"
    assert spec.telegram_chat_id == "123456"


def test_run_auth_cookie_reuse():
    page = MagicMock()
    page.add_cookies = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()

    spec = AuthSpec(
        type="cookie_reuse",
        url="https://app.apvs.vc/dashboard",
        cookies=[{"name": "sess", "value": "xyz", "domain": ".apvs.vc"}],
        success_assert={"selector": ".dashboard", "timeout_ms": 5000},
    )
    ctx = RunContext()
    _run(run_auth(page, spec, ctx))
    page.add_cookies.assert_called_once()
    page.goto.assert_called_once_with(spec.url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_selector.assert_called_once_with(".dashboard", timeout=5000, state="visible")


def test_run_auth_otp_via_telegram_fetches_otp():
    """OTP flow: login first, then poll Telegram for the code, fill, submit."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock(return_value=MagicMock(fill=AsyncMock()))

    fake_message = "Seu código: 123456"
    fake_telegram = AsyncMock(return_value=fake_message)
    # Monkeypatch the helper at the module level.
    import app.automation.auth as auth_mod
    original = getattr(auth_mod, "_fetch_telegram_message", None)
    auth_mod._fetch_telegram_message = fake_telegram
    try:
        spec = AuthSpec(
            type="otp_via_telegram",
            url="https://app.apvs.vc/login",
            credentials_ref="apvs_login",
            telegram_chat_id="999",
            otp_selector="input[name=otp]",
            submit_selector="button[type=submit]",
            success_assert={"selector": ".dashboard", "timeout_ms": 5000},
        )
        ctx = RunContext(credentials={"apvs_login": {"user": "u", "pass": "p"}})
        _run(run_auth(page, spec, ctx))
        fake_telegram.assert_called_once_with("999", timeout_s=60)
        # OTP was filled (look for "123456" in any fill call).
        all_fill_values = []
        for call in page.fill.call_args_list:
            args, kwargs = call
            if len(args) >= 2:
                all_fill_values.append(args[1])
            else:
                all_fill_values.append(kwargs.get("value", ""))
        assert any("123456" in str(v) for v in all_fill_values), f"OTP not found in fill calls: {all_fill_values}"
    finally:
        if original is not None:
            auth_mod._fetch_telegram_message = original


def test_parse_auth_unknown_type_still_raises():
    with __import__("pytest").raises(ValueError, match="Unsupported"):
        parse_auth({"type": "oauth_magic", "url": "x"})
