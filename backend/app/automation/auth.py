"""Auth block — declarative login flows.

P1a implements `form_login`. P5 adds `cookie_reuse` and `otp_via_telegram`.
`success_assert` is mandatory because we can't assume a login worked without
signaling; treating absence as success has burned cotacao_pvs in the past.
"""
from dataclasses import dataclass, field
import re
from typing import Any

from app.automation.bindings import interpolate
from app.automation.models import RunContext


SUPPORTED_TYPES = {"form_login", "cookie_reuse", "otp_via_telegram"}


@dataclass
class AuthSpec:
    type: str
    url: str
    credentials_ref: str | None = None
    selectors: dict[str, str] = field(default_factory=dict)
    success_assert: dict[str, Any] = field(default_factory=dict)
    # cookie_reuse:
    cookies: list[dict] = field(default_factory=list)
    # otp_via_telegram:
    telegram_chat_id: str | None = None
    otp_selector: str | None = None
    submit_selector: str | None = None


def parse_auth(raw: dict[str, Any]) -> AuthSpec:
    if not isinstance(raw, dict):
        raise ValueError(f"auth block must be a dict, got {type(raw).__name__}")
    auth_type = raw.get("type")
    if auth_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported auth type {auth_type!r}; supported: {sorted(SUPPORTED_TYPES)}")
    if "url" not in raw or "success_assert" not in raw:
        raise ValueError("auth block missing required field(s): url, success_assert")

    if auth_type == "form_login":
        if "credentials_ref" not in raw or "selectors" not in raw:
            raise ValueError("form_login requires credentials_ref, selectors")
        return AuthSpec(
            type=auth_type,
            url=raw["url"],
            credentials_ref=raw["credentials_ref"],
            selectors=raw["selectors"],
            success_assert=raw["success_assert"],
        )
    if auth_type == "cookie_reuse":
        if "cookies" not in raw or not isinstance(raw["cookies"], list):
            raise ValueError("cookie_reuse requires 'cookies' list")
        return AuthSpec(
            type=auth_type,
            url=raw["url"],
            cookies=raw["cookies"],
            success_assert=raw["success_assert"],
        )
    if auth_type == "otp_via_telegram":
        missing = [f for f in ("credentials_ref", "telegram_chat_id", "otp_selector", "submit_selector") if f not in raw]
        if missing:
            raise ValueError(f"otp_via_telegram missing required field(s): {missing}")
        return AuthSpec(
            type=auth_type,
            url=raw["url"],
            credentials_ref=raw["credentials_ref"],
            selectors={
                "user": "input[type=text]",
                "pass": "input[type=password]",
                "submit": raw["submit_selector"],
            },
            success_assert=raw["success_assert"],
            telegram_chat_id=raw["telegram_chat_id"],
            otp_selector=raw["otp_selector"],
            submit_selector=raw["submit_selector"],
        )
    raise ValueError(f"Unhandled auth type {auth_type!r}")


# ── OTP helpers ─────────────────────────────────────────────────────────

_OTP_RE = re.compile(r"\b(\d{4,8})\b")


async def _fetch_telegram_message(chat_id: str, timeout_s: int = 60) -> str:
    """Fetch the latest message from a Telegram chat within `timeout_s`.

    Default impl uses the Telegram Bot API (HTTPS). Requires:
    - TELEGRAM_BOT_TOKEN env var
    - chat_id from the auth block
    """
    import os
    import httpx
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var not set")
    update_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    elapsed = 0
    last_update_id = None
    async with httpx.AsyncClient(timeout=5) as client:
        while elapsed < timeout_s:
            params = {"timeout": 1, "allowed_updates": '["message"]'}
            if last_update_id is not None:
                params["offset"] = last_update_id + 1
            resp = await client.get(update_url, params=params)
            data = resp.json().get("result") or []
            for update in data:
                if str(update.get("message", {}).get("chat", {}).get("id")) != str(chat_id):
                    last_update_id = update.get("update_id", last_update_id)
                    continue
                msg_text = update["message"].get("text", "")
                last_update_id = update["update_id"]
                m = _OTP_RE.search(msg_text)
                if m:
                    return m.group(1)
            await asyncio.sleep(2)
            elapsed += 2
    raise TimeoutError(f"No OTP message received in {timeout_s}s from chat {chat_id}")


# ── Auth runners ────────────────────────────────────────────────────────

async def run_auth(page: Any, spec: AuthSpec, ctx: RunContext) -> None:
    if spec.type == "form_login":
        await _run_form_login(page, spec, ctx)
        return
    if spec.type == "cookie_reuse":
        await _run_cookie_reuse(page, spec)
        return
    if spec.type == "otp_via_telegram":
        await _run_otp_via_telegram(page, spec, ctx)
        return
    raise ValueError(f"Auth type {spec.type!r} not implemented")


async def _run_form_login(page: Any, spec: AuthSpec, ctx: RunContext) -> None:
    creds = ctx.credentials.get(spec.credentials_ref) if spec.credentials_ref else None
    if creds is None:
        raise KeyError(f"credentials_ref {spec.credentials_ref!r} not found in ctx.credentials")

    await page.goto(spec.url, timeout=30000, wait_until="domcontentloaded")

    user_selector = interpolate(spec.selectors["user"], ctx)
    pass_selector = interpolate(spec.selectors["pass"], ctx)
    user_value = interpolate(str(creds.get("user", "")), ctx)
    pass_value = interpolate(str(creds.get("pass", "")), ctx)
    await page.fill(user_selector, user_value, timeout=15000)
    await page.fill(pass_selector, pass_value, timeout=15000)

    submit_selector = interpolate(spec.selectors["submit"], ctx)
    await page.click(submit_selector, timeout=30000)

    success_selector = interpolate(spec.success_assert["selector"], ctx)
    success_timeout = int(spec.success_assert.get("timeout_ms", 5000))
    await page.wait_for_selector(success_selector, timeout=success_timeout, state="visible")


async def _run_cookie_reuse(page: Any, spec: AuthSpec) -> None:
    # Playwright add_cookies accepts: name, value, domain/url, path, expires, httpOnly, secure, sameSite.
    cookies = [
        {k: v for k, v in c.items() if k in ("name", "value", "domain", "url", "path", "expires", "httpOnly", "secure", "sameSite")}
        for c in spec.cookies
    ]
    if cookies:
        await page.add_cookies(cookies)
    await page.goto(spec.url, timeout=30000, wait_until="domcontentloaded")
    success_selector = interpolate(spec.success_assert["selector"], type("C", (), {"bindings": {}, "credentials": {}, "inputs": {}})())
    success_timeout = int(spec.success_assert.get("timeout_ms", 5000))
    await page.wait_for_selector(success_selector, timeout=success_timeout, state="visible")


async def _run_otp_via_telegram(page: Any, spec: AuthSpec, ctx: RunContext) -> None:
    import asyncio
    creds = ctx.credentials.get(spec.credentials_ref) if spec.credentials_ref else None
    if creds is None:
        raise KeyError(f"credentials_ref {spec.credentials_ref!r} not found in ctx.credentials")
    await page.goto(spec.url, timeout=30000, wait_until="domcontentloaded")
    # Fill user/pass (assumes first screen has them).
    if creds.get("user"):
        first_input = await page.query_selector("input[type=text]")
        if first_input:
            await first_input.fill(str(creds["user"]))
    if creds.get("pass"):
        pwd_input = await page.query_selector("input[type=password]")
        if pwd_input:
            await pwd_input.fill(str(creds["pass"]))
    # Submit to reach OTP screen.
    submit_btn = await page.query_selector("button[type=submit]")
    if submit_btn:
        await page.click("button[type=submit]", timeout=15000)
    # Fetch OTP from Telegram.
    msg = await _fetch_telegram_message(spec.telegram_chat_id, timeout_s=60)
    m = _OTP_RE.search(msg)
    if not m:
        raise RuntimeError(f"No OTP code found in Telegram message: {msg!r}")
    otp = m.group(1)
    # Fill OTP.
    await page.fill(spec.otp_selector, otp, timeout=15000)
    # Submit.
    await page.click(spec.submit_selector, timeout=15000)
    # Wait for success.
    success_selector = interpolate(spec.success_assert["selector"], type("Ctx", (), {"bindings": {}, "credentials": {}, "inputs": {}})())
    success_timeout = int(spec.success_assert.get("timeout_ms", 5000))
    await page.wait_for_selector(success_selector, timeout=success_timeout, state="visible")
