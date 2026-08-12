"""Auth block — declarative login flows.

P1a implements `form_login` only. P5 adds `cookie_reuse` and `otp_via_telegram`.
`success_assert` is mandatory because we can't assume a login worked without
signaling; treating absence as success has burned cotacao_pvs in the past.
"""
from dataclasses import dataclass
from typing import Any

from app.automation.bindings import interpolate
from app.automation.models import RunContext


SUPPORTED_TYPES = {"form_login"}


@dataclass
class AuthSpec:
    type: str
    url: str
    credentials_ref: str
    selectors: dict[str, str]
    success_assert: dict[str, Any]


def parse_auth(raw: dict[str, Any]) -> AuthSpec:
    """Parse an auth block. Raises ValueError on missing/invalid fields."""
    if not isinstance(raw, dict):
        raise ValueError(f"auth block must be a dict, got {type(raw).__name__}")
    auth_type = raw.get("type")
    if auth_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported auth type {auth_type!r}; supported: {sorted(SUPPORTED_TYPES)}")
    missing = [f for f in ("url", "credentials_ref", "selectors", "success_assert") if f not in raw]
    if missing:
        raise ValueError(f"auth block missing required field(s): {missing}")
    return AuthSpec(
        type=auth_type,
        url=raw["url"],
        credentials_ref=raw["credentials_ref"],
        selectors=raw["selectors"],
        success_assert=raw["success_assert"],
    )


async def run_auth(page: Any, spec: AuthSpec, ctx: RunContext) -> None:
    """Execute the auth flow against `page`. Mutates nothing on `ctx`."""
    if spec.type != "form_login":
        raise ValueError(f"Auth type {spec.type!r} not implemented in P1a")

    creds = ctx.credentials.get(spec.credentials_ref)
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