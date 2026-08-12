"""Extraction steps — extract_text, extract_table, screenshot.

`screenshot` writes to a local file path. P1a's runner then uploads to MinIO
when env is configured (handled in storage.py, not here).
"""
from pathlib import Path
from typing import Any

from app.automation.bindings import interpolate
from app.automation.models import RunContext


async def extract_text(page: Any, params: dict[str, Any], ctx: RunContext) -> None:
    """Read text from `params["selector"]` and bind to `params["bind"]` (if set)."""
    selector = interpolate(params["selector"], ctx)
    value = await page.locator(selector).first.text_content()
    bind = params.get("bind")
    if bind:
        ctx.bindings[bind] = value


async def extract_table(page: Any, params: dict[str, Any], ctx: RunContext) -> None:
    """Read an HTML table into a list of dicts (header row + data rows)."""
    selector = interpolate(params["selector"], ctx)
    table = page.query_selector(selector)
    if table is None:
        raise ValueError(f"extract_table: no table found at {selector!r}")
    rows = table.query_selector_all("tr")
    if not rows:
        raise ValueError(f"extract_table: table at {selector!r} has no rows")
    header_cells = rows[0].query_selector_all("th, td")
    headers = [await c.text_content() for c in header_cells]
    out = []
    for row in rows[1:]:
        cells = row.query_selector_all("td")
        if len(cells) != len(headers):
            # Skip malformed rows silently; structured error lands in P2.
            continue
        values = [await c.text_content() for c in cells]
        out.append(dict(zip(headers, values)))
    bind = params.get("bind")
    if bind:
        ctx.bindings[bind] = out


async def screenshot(page: Any, params: dict[str, Any], ctx: RunContext) -> None:
    """Capture a screenshot to `params["path"]`. Creates parent dirs if needed."""
    path = params["path"]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = await page.screenshot(path=str(target))
    if data is not None:
        target.write_bytes(data)
