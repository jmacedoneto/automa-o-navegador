"""Interaction step handlers — click, fill."""
from typing import Any
from playwright.async_api import Page

from app.automation.bindings import interpolate
from app.automation.models import RunContext


async def click(page: Page, params: dict[str, Any], ctx: RunContext) -> None:
    """Click `params["selector"]`."""
    selector = interpolate(params["selector"], ctx)
    timeout_ms = int(params.get("timeout_ms", 30000))
    await page.locator(selector).first.click(timeout=timeout_ms)


async def fill(page: Page, params: dict[str, Any], ctx: RunContext) -> None:
    """params: {selector: value, ...}. Fills each (selector, value) pair."""
    for raw_selector, raw_value in params.items():
        selector = interpolate(raw_selector, ctx)
        value = interpolate(raw_value, ctx)
        await page.locator(selector).first.fill(value)
