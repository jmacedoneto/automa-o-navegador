"""Assertion step handlers — assert_text."""
from typing import Any
from playwright.async_api import Page

from app.automation.bindings import interpolate
from app.automation.models import RunContext


async def assert_text(page: Page, params: dict[str, Any], ctx: RunContext) -> None:
    text = interpolate(params["text"], ctx)
    timeout_ms = int(params.get("timeout_ms", 5000))
    locator = page.get_by_text(text, exact=True).first
    try:
        await locator.wait_for(state="visible", timeout=timeout_ms)
    except Exception as e:
        raise AssertionError(
            f"Expected text {text!r} not visible within {timeout_ms}ms: {e}"
        ) from e
