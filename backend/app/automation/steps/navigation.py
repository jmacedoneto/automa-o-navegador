"""Navigation step handlers — goto, wait_for."""
from typing import Any
from playwright.async_api import Page

from app.automation.bindings import interpolate
from app.automation.models import RunContext


async def goto(page: Page, params: dict[str, Any], ctx: RunContext) -> None:
    """Navigate to `params["url"]`. Interpolates against ctx."""
    url = interpolate(params["url"], ctx)
    timeout_ms = int(params.get("timeout_ms", 30000))
    await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")


async def wait_for(page: Page, params: dict[str, Any], ctx: RunContext) -> Any:
    """Wait for `params["selector"]` to be visible."""
    selector = interpolate(params["selector"], ctx)
    timeout_ms = int(params.get("timeout_ms", 30000))
    return await page.wait_for_selector(selector, timeout=timeout_ms, state="visible")