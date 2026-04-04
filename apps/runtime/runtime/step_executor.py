import asyncio
import base64
import re
from typing import Any, Callable


def _resolve_vars(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return re.sub(r"\{\{(\w+)\}\}", lambda m: str(variables.get(m.group(1), m.group(0))), value)
    if isinstance(value, dict):
        return {k: _resolve_vars(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_vars(i, variables) for i in value]
    return value


class StepExecutor:
    def __init__(self, page, variables: dict[str, Any] | None = None, on_screenshot: Callable | None = None):
        self._page = page
        self._variables = variables or {}
        self._on_screenshot = on_screenshot

    async def execute_step(self, raw_step: dict) -> dict:
        step = _resolve_vars(raw_step, self._variables)
        action = step.get("action") or step.get("type", "")
        selector = step.get("selector", "")
        result = {"action": action, "success": True, "skipped": False, "error": ""}

        try:
            if action == "navigate":
                url = step.get("url") or step.get("value", "")
                if url:
                    await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            elif action == "click":
                if selector:
                    await self._page.click(selector, timeout=10000)
                    try:
                        await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass

            elif action == "type":
                if selector:
                    await self._page.fill(selector, step.get("value", ""), timeout=10000)

            elif action == "selectOption":
                if selector:
                    value = step.get("value", "")
                    if step.get("selectBy") == "label":
                        await self._page.select_option(selector, label=value, timeout=10000)
                    else:
                        await self._page.select_option(selector, value=value, timeout=10000)

            elif action == "wait":
                await asyncio.sleep(step.get("duration", 1000) / 1000)

            elif action == "waitForSelector":
                if selector:
                    await self._page.wait_for_selector(selector, timeout=15000)

            elif action == "scroll":
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            elif action == "hover":
                if selector:
                    await self._page.hover(selector, timeout=10000)

            elif action == "key":
                await self._page.keyboard.press(step.get("key", step.get("value", "Enter")))

            elif action == "screenshot":
                png = await self._page.screenshot(full_page=step.get("full_page", False))
                if self._on_screenshot:
                    self._on_screenshot(base64.b64encode(png).decode())

            elif action == "extractTable":
                data = await self._page.evaluate("""(sel) => {
                    const table = document.querySelector(sel);
                    if (!table) return [];
                    return Array.from(table.querySelectorAll('tr')).map(r =>
                        Array.from(r.querySelectorAll('th,td')).map(c => c.innerText.trim())
                    );
                }""", selector or "table")
                result["extracted"] = data

            elif action == "extractText":
                if selector:
                    result["extracted"] = await self._page.inner_text(selector)

            else:
                result["skipped"] = True

            wait_ms = step.get("waitTime", 0)
            if wait_ms and wait_ms > 0 and action not in ("wait", "hover"):
                await asyncio.sleep(wait_ms / 1000)

        except Exception as exc:
            result["success"] = False
            result["error"] = str(exc)

        return result
