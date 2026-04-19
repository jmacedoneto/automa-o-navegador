"""
Browser execution engine — connects to Browserless via Playwright.
Supports step types: navigate, click, type, wait, waitForSelector,
screenshot, extractTable, extractText, extractImages, download, selectOption, scroll.
Variables in steps are resolved via {{key}} syntax.

After every step a screenshot is taken for live preview.
Downloaded Excel/CSV files are auto-parsed into extracted_data.
If no extraction steps ran, the final page HTML is captured.
"""
import re
import csv
import asyncio
import base64
import os
from typing import Any, Callable

from playwright.async_api import async_playwright, Browser, Page


def resolve_vars(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        def replace(m):
            return str(variables.get(m.group(1), m.group(0)))
        return re.sub(r"\{\{(\w+)\}\}", replace, value)
    if isinstance(value, dict):
        return {k: resolve_vars(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_vars(i, variables) for i in value]
    return value


def _parse_excel(path: str) -> list[list[str]]:
    """Parse .xlsx / .xls file into a list-of-rows."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append([str(c) if c is not None else "" for c in row])
        return rows
    except Exception as e:
        return [[f"Erro ao ler Excel: {e}"]]


def _parse_csv(path: str) -> list[list[str]]:
    """Parse .csv file into a list-of-rows."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            return [row for row in reader]
    except Exception as e:
        return [[f"Erro ao ler CSV: {e}"]]


async def _take_screenshot(page: Page, on_screenshot: Callable[[str], None] | None) -> None:
    """Take a viewport screenshot and call the on_screenshot callback."""
    if on_screenshot is None:
        return
    try:
        img = await page.screenshot(full_page=False, type="jpeg", quality=70)
        on_screenshot(base64.b64encode(img).decode())
    except Exception:
        pass


async def execute_automation(
    steps: list[dict],
    variables: dict[str, Any],
    browserless_url: str,
    browserless_token: str,
    on_step: Callable[[int], None] | None = None,
    on_screenshot: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    cdp_url = browserless_url.rstrip("/")
    if cdp_url.startswith("https://"):
        cdp_url = cdp_url.replace("https://", "wss://")
    elif cdp_url.startswith("http://"):
        cdp_url = cdp_url.replace("http://", "ws://")

    if browserless_token:
        cdp_url = f"{cdp_url}?token={browserless_token}"

    screenshots: list[str] = []
    extracted_data: dict[str, Any] = {}
    steps_completed = 0
    has_explicit_extraction = False  # True if any extractTable/extractText/download(parsed) ran

    async with async_playwright() as p:
        browser: Browser = await p.chromium.connect_over_cdp(cdp_url)
        page: Page = await browser.new_page()

        try:
            for i, step in enumerate(steps):
                step = resolve_vars(step, variables)
                action = step.get("type") or step.get("action", "")
                selector = step.get("selector", "")

                if action == "navigate":
                    url = step.get("url") or step.get("value", "")
                    # Fallback: extract URL from description when url/value are empty
                    # (happens when old extension stored URL only in description)
                    if not url:
                        desc = step.get("description", "")
                        url_match = re.search(r'https?://\S+', desc)
                        if url_match:
                            url = url_match.group(0)
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                elif action == "hover":
                    if selector:
                        await page.hover(selector, timeout=10000)
                        # Wait for hover-triggered content (menus, dropdowns) to appear
                        hover_wait = step.get("waitTime", 1000)
                        if hover_wait > 0:
                            await asyncio.sleep(hover_wait / 1000)

                elif action == "click":
                    if selector:
                        try:
                            await page.click(selector, timeout=10000)
                        except Exception as click_err:
                            # If element is in DOM but CSS-hidden (hover menus), dispatch event
                            if "not visible" in str(click_err).lower() or "not attached" in str(click_err).lower():
                                try:
                                    # dispatch_event bypasses visibility — works for CSS hover menus
                                    await page.locator(selector).dispatch_event("click", timeout=8000)
                                except Exception:
                                    # Last resort: force click at bounding box
                                    await page.locator(selector).click(force=True, timeout=8000)
                            else:
                                raise
                    elif step.get("x") is not None and step.get("y") is not None:
                        # Coordinate-based click (from agent execution)
                        await page.mouse.click(int(step["x"]), int(step["y"]))
                    if action == "click":
                        # Wait for any navigation triggered by the click to settle
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=5000)
                        except Exception:
                            pass

                elif action == "type":
                    if selector:
                        await page.fill(selector, step.get("value", ""), timeout=10000)

                elif action == "selectOption":
                    if selector:
                        value = step.get("value", "")
                        if step.get("selectBy") == "label":
                            await page.select_option(selector, label=value, timeout=10000)
                        else:
                            await page.select_option(selector, value=value, timeout=10000)

                elif action == "evaluate":
                    # Run arbitrary JavaScript on the page; result stored in extracted_data if key given
                    script = step.get("script") or step.get("value", "")
                    if script:
                        result = await page.evaluate(script)
                        key = step.get("key")
                        if key:
                            extracted_data[key] = result

                elif action == "wait":
                    await asyncio.sleep(step.get("duration", 1000) / 1000)

                elif action == "waitForSelector":
                    if selector:
                        await page.wait_for_selector(selector, timeout=15000)

                elif action == "scroll":
                    try:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    except Exception:
                        pass

                elif action == "screenshot":
                    png = await page.screenshot(full_page=step.get("full_page", False))
                    b64 = base64.b64encode(png).decode()
                    screenshots.append(b64)
                    if on_screenshot:
                        on_screenshot(b64)

                elif action == "extractTable":
                    has_explicit_extraction = True
                    tbl_selector = selector or "table"
                    data = await page.evaluate(
                        """(sel) => {
                            const table = document.querySelector(sel);
                            if (!table) return [];
                            const rows = Array.from(table.querySelectorAll('tr'));
                            return rows.map(r =>
                                Array.from(r.querySelectorAll('th,td')).map(c => c.innerText.trim())
                            );
                        }""",
                        tbl_selector,
                    )
                    key = step.get("key", f"table_{i}")
                    extracted_data[key] = data

                elif action == "extractText":
                    if selector:
                        has_explicit_extraction = True
                        text = await page.inner_text(selector)
                        key = step.get("key", f"text_{i}")
                        extracted_data[key] = text

                elif action == "extractImages":
                    has_explicit_extraction = True
                    img_selector = selector or "img"
                    # Fetch each image URL and convert to base64
                    img_urls = await page.evaluate(
                        """(sel) => Array.from(document.querySelectorAll(sel))
                            .map(img => img.src || img.currentSrc)
                            .filter(src => src && src.startsWith('http'))""",
                        img_selector,
                    )
                    limit = step.get("limit", 20)
                    imgs_b64 = []
                    for img_url in img_urls[:limit]:
                        try:
                            import httpx
                            async with httpx.AsyncClient(timeout=10) as client:
                                resp = await client.get(img_url)
                            if resp.status_code == 200:
                                mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                                b64 = base64.b64encode(resp.content).decode()
                                imgs_b64.append({
                                    "url": img_url,
                                    "mime": mime,
                                    "base64": f"data:{mime};base64,{b64}",
                                })
                        except Exception:
                            imgs_b64.append({"url": img_url, "mime": None, "base64": None})
                    key = step.get("key", f"images_{i}")
                    extracted_data[key] = imgs_b64

                elif action == "download":
                    if selector:
                        import httpx
                        import time
                        
                        intercepted_req = None
                        async def handle_route(route):
                            nonlocal intercepted_req
                            req = route.request
                            # Intercept any POST or requests that look like a file download
                            if req.method == "POST" or "Excel" in req.url or "export" in req.url.lower() or "download" in req.url.lower():
                                intercepted_req = {
                                    "url": req.url,
                                    "method": req.method,
                                    "headers": req.headers,
                                    "post_data": req.post_data_buffer
                                }
                                await route.abort()
                            else:
                                await route.continue_()
                                
                        await page.route("**/*", handle_route)
                        
                        try:
                            try:
                                await page.click(selector, timeout=8000)
                            except Exception as click_err:
                                if "aborted" not in str(click_err).lower() and "failed" not in str(click_err).lower():
                                    raise click_err
                            
                            # Wait for interception
                            for _ in range(30):
                                if intercepted_req:
                                    break
                                await asyncio.sleep(0.5)
                                
                            key = step.get("key", f"file_{i}")
                            if intercepted_req:
                                cookies = await page.context.cookies()
                                cookie_dict = {c["name"]: c["value"] for c in cookies}
                                
                                _dl_timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
                                async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
                                    if intercepted_req["method"] == "POST":
                                        resp = await client.post(
                                            intercepted_req["url"],
                                            headers=intercepted_req["headers"],
                                            content=intercepted_req["post_data"],
                                            cookies=cookie_dict,
                                            timeout=_dl_timeout,
                                        )
                                    else:
                                        resp = await client.get(
                                            intercepted_req["url"],
                                            headers=intercepted_req["headers"],
                                            cookies=cookie_dict,
                                            timeout=_dl_timeout,
                                        )
                                
                                cd = resp.headers.get("content-disposition", "")
                                filename = f"download_{int(time.time())}.xlsx"
                                if "filename=" in cd:
                                    filename = cd.split("filename=")[1].strip('"\'')
                                    
                                path = f"/tmp/{filename}"
                                with open(path, "wb") as f:
                                    f.write(resp.content)
                                    
                                ext = os.path.splitext(filename)[1].lower()
                                if ext in (".xlsx", ".xls"):
                                    has_explicit_extraction = True
                                    extracted_data[key] = _parse_excel(path)
                                elif ext == ".csv":
                                    has_explicit_extraction = True
                                    extracted_data[key] = _parse_csv(path)
                                else:
                                    extracted_data[key] = path
                            else:
                                extracted_data[key] = [["Erro: Download n\u00e3o interceptado."]]
                        except Exception as e:
                            extracted_data[step.get("key", f"file_{i}")] = [[f"Erro no download: {e}"]]
                        finally:
                            await page.unroute("**/*")

                elif action == "cotacao_pvs_loop":
                    from app.services.cotacao_executor import run_cotacao_loop
                    creds = {
                        "login_cnpj": variables.get("login_cnpj", ""),
                        "login_senha": variables.get("login_senha", ""),
                    }
                    loop_result = await run_cotacao_loop(
                        page=page,
                        step=step,
                        credentials=creds,
                        on_step=on_step,
                        on_screenshot=on_screenshot,
                    )
                    extracted_data["cotacao_result"] = loop_result
                    has_explicit_extraction = True

                steps_completed += 1

                # Honour per-step waitTime (in ms) — hover already consumed its own wait above
                if action != "hover":
                    wait_ms = step.get("waitTime", 0)
                    if wait_ms and wait_ms > 0:
                        await asyncio.sleep(wait_ms / 1000)

                # Screenshot after every step — but NOT after hover (mouse must stay put)
                if action != "hover":
                    await _take_screenshot(page, on_screenshot)

                if on_step:
                    on_step(steps_completed)

            # If no explicit extraction occurred, capture full page HTML as fallback
            if not has_explicit_extraction:
                try:
                    extracted_data["page_html"] = await page.content()
                except Exception:
                    pass

        finally:
            await browser.close()

    return {
        "steps_completed": steps_completed,
        "total_steps": len(steps),
        "extracted_data": extracted_data,
        "screenshots": screenshots,
    }
