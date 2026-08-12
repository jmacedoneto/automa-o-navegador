"""
GPT-4o Vision browser automation agent.
Takes screenshots, asks GPT-4o what to do next, executes actions.
"""
import asyncio
import base64
import json
from typing import Callable, Any
from openai import AsyncOpenAI

SYSTEM_PROMPT = """You are an autonomous browser agent with full vision and reasoning capabilities.
You control a real web browser (viewport 1280x720). Each turn you receive a screenshot.

━━━ YOUR MISSION ━━━
Understand the user's GOAL — not just the literal words, but the INTENT.
Example: "export inadimplência report" means → find the reports section → locate the correct report → set any required filters → click export → confirm download.
Never get stuck on one approach. If something doesn't work after 2 attempts, think differently.

━━━ RESPONSE FORMAT ━━━
Always respond with a single JSON object:
{
  "think": "Brief reasoning: what I see, what state I'm in, what the goal requires, what's the best next step and why",
  "action": "navigate|click|type|clear_type|select|read_select|key|scroll|wait|done",
  ... action-specific fields ...
}

━━━ AVAILABLE ACTIONS ━━━
{"think":"...", "action":"navigate", "url":"https://..."}
{"think":"...", "action":"click", "x":640, "y":360}
{"think":"...", "action":"type", "selector":"#id", "value":"text"}
{"think":"...", "action":"clear_type", "selector":"#id", "value":"text"}  ← clears field first, then types
{"think":"...", "action":"select", "selector":"#id", "value":"option label"}
{"think":"...", "action":"read_select", "x":640, "y":360}  ← inspects dropdown options at coords
{"think":"...", "action":"key", "key":"Enter|Tab|Escape"}
{"think":"...", "action":"scroll", "direction":"down|up"}
{"think":"...", "action":"wait"}  ← wait for page/content to load
{"think":"...", "action":"done", "description":"what was accomplished"}

━━━ INTELLIGENCE RULES ━━━

READING THE SCREEN:
- Before acting, identify: What page am I on? What has changed? Is there a loading indicator? Any error message?
- Read all visible text, labels, buttons, and menus carefully.
- If you see a modal, dialog, or overlay — deal with it before proceeding.
- If content is loading (spinner, "carregando...") → use wait.

NAVIGATION & MENUS:
- Top navigation bars, sidebars, and breadcrumbs are your map. Use them.
- Hover menus: click the parent menu item first, wait for submenu to appear, then click the submenu item.
- If a menu item isn't visible, scroll to find it or look for a "more" / "≡" button.

FORMS & FILTERS:
- Fill ALL required fields before submitting. Look for asterisks (*) or "obrigatório".
- For date pickers: click the field, type the date directly (DD/MM/YYYY or YYYY-MM-DD), or use the calendar.
- For custom dropdowns (not native <select>): click to open, wait for options to appear, then click the option.
- For native <select>: use read_select to get options, then use select action.

LOGIN:
- Username field first, then password field. Never mix them.
- After filling, press Enter or click the login button.
- If login fails, read the error and try again with the correct credentials.

EXPORTS & DOWNLOADS:
- Look for buttons like "Exportar", "Baixar", "Download", "Excel", "CSV", "PDF".
- After clicking export, wait for the download dialog or file generation.
- Confirm any download dialog that appears.
- When a file downloads, the task goal is typically complete.

RECOVERY (when stuck):
- Attempt 1 fails → analyze WHY from the screenshot, adjust approach.
- Attempt 2 fails → try a completely different method (different selector, different navigation path).
- After 3 failed attempts on the same goal → scroll to look for the element, or navigate back and try from scratch.
- Never repeat the exact same failed action more than twice.

COMPLETION:
- Use "done" only when the GOAL is visibly accomplished (file downloaded, data extracted, form submitted, confirmation shown).
- Describe what was accomplished in the "description" field.

For click: use pixel coordinates (x, y) from the screenshot.
For type/select/clear_type: use CSS selector (#id preferred, [name=...] second, tag+attribute third).
"""

_GET_ELEMENT_AT_JS = """
([x, y]) => {
    let el = document.elementFromPoint(x, y);
    if (!el) return null;
    // Walk up to find SELECT
    let node = el;
    for (let i = 0; i < 8 && node && node.tagName; i++) {
        if (node.tagName === 'SELECT') { el = node; break; }
        node = node.parentElement;
    }
    const info = {
        tag: el.tagName.toLowerCase(),
        isSelect: el.tagName === 'SELECT',
        options: [],
    };
    if (info.isSelect) {
        info.options = Array.from(el.options).map(o => ({ value: o.value, label: o.text.trim() }));
    }
    if (el.id) info.selector = '#' + el.id;
    else if (el.getAttribute('name')) info.selector = el.tagName.toLowerCase() + '[name="' + el.getAttribute('name') + '"]';
    else info.selector = el.tagName.toLowerCase();
    return info;
}
"""


def _parse_downloaded_file(path: str) -> Any:
    """Parse a downloaded file and return its data."""
    import os, csv
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True)
            ws = wb.active
            return [
                [str(c) if c is not None else "" for c in row]
                for row in ws.iter_rows(values_only=True)
            ]
        elif ext == ".csv":
            with open(path, newline="", encoding="utf-8-sig") as f:
                return list(csv.reader(f))
        else:
            return path  # unknown type — return path
    except Exception as e:
        return f"Erro ao ler arquivo: {e}"


async def run_agent(
    page,
    instruction: str,
    api_key: str,
    model: str,
    on_screenshot: Callable,
    on_action: Callable,
    on_step: Callable,
    on_done: Callable,
    max_steps: int = 30,
    on_download: Callable | None = None,
):
    """Run the vision agent loop."""

    # Fall back to gpt-4o only for models that definitely don't support vision
    _no_vision = ("gpt-3.5", "o1-mini", "o3-mini")
    if any(model.startswith(p) for p in _no_vision):
        model = "gpt-4o"

    client = AsyncOpenAI(api_key=api_key)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: {instruction}"},
    ]

    step_count = 0
    last_action_raw = ""
    repeat_count = 0
    downloaded_files: dict[str, Any] = {}

    # current_page can be updated when a popup/new tab opens
    current_page = page

    for turn in range(max_steps):
        # ── Screenshot ──────────────────────────────────────────────────────
        try:
            img = await current_page.screenshot(type="png")
        except Exception as e:
            await on_done(success=False, message=str(e))
            return

        b64 = base64.b64encode(img).decode()
        await on_screenshot(b64)

        # On the first turn and after type actions: explicitly ask to verify
        verify_note = ""
        if turn > 0 and last_action_raw:
            try:
                prev = json.loads(last_action_raw)
                if prev.get("action") in ("type", "clear_type"):
                    verify_note = f"\nIMPORTANT: Verify the field now shows \"{prev.get('value','')}\" correctly. If it shows wrong content, use clear_type to fix it."
                elif prev.get("action") == "click":
                    verify_note = "\nVerify the click had the expected effect (navigation, modal opened, button activated, etc)."
            except Exception:
                pass

        vision_turn = {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Step {turn + 1} — current browser screenshot. What is the current state and what is the next action?{verify_note}"},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{b64}", "detail": "low"
                }},
            ],
        }

        # ── Ask model ──────────────────────────────────────────────────────
        # Keep message history trimmed: system + task + last 20 text messages
        # Images are NEVER stored in history — only the current screenshot is sent
        trimmed_history = messages[:2] + messages[2:][-20:] if len(messages) > 22 else messages
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=trimmed_history + [vision_turn],
                response_format={"type": "json_object"},
                max_completion_tokens=800,
                temperature=0,
            )
        except Exception as e:
            await on_done(success=False, message=f"OpenAI error: {e}")
            return

        raw = (resp.choices[0].message.content or "{}").strip()

        # Detect repeated action (stuck)
        if raw == last_action_raw:
            repeat_count += 1
            if repeat_count >= 2:
                messages.append({"role": "user", "content": "You seem stuck repeating the same action. Analyze the screenshot carefully and try a completely different approach."})
                repeat_count = 0
        else:
            repeat_count = 0
        last_action_raw = raw

        try:
            action = json.loads(raw)
        except json.JSONDecodeError:
            action = {"action": "done", "description": "AI returned invalid JSON"}

        await on_action(action)

        act = action.get("action", "done")
        desc = action.get("description", act)

        if act == "done":
            await on_done(success=True, message=desc, downloads=downloaded_files)
            return

        # ── Execute action ──────────────────────────────────────────────────
        step = None
        error_msg = None
        extra_context = ""

        try:
            if act == "navigate":
                url = action.get("url", "")
                await current_page.goto(url, wait_until="domcontentloaded", timeout=20000)
                step = {"action": "navigate", "selector": "", "value": url,
                        "description": desc, "waitTime": 1000}

            elif act == "click":
                x, y = int(action.get("x", 640)), int(action.get("y", 360))

                # Priority 1: detect new popup/tab opening
                popup_caught = False
                try:
                    async with current_page.context.expect_event("page", timeout=2000) as popup_info:
                        await current_page.mouse.click(x, y)
                    popup = await popup_info.value
                    await popup.wait_for_load_state("domcontentloaded", timeout=8000)
                    current_page = popup
                    popup_caught = True
                    extra_context = (
                        "Uma nova aba/popup foi aberta. Você agora está nela — "
                        "continue interagindo normalmente (screenshot mostrará a nova aba)."
                    )
                except Exception:
                    pass

                if not popup_caught:
                    # Priority 2: detect file download
                    try:
                        async with current_page.expect_download(timeout=3000) as dl_info:
                            await current_page.mouse.click(x, y)
                        download = await dl_info.value
                        filename = download.suggested_filename
                        path = f"/tmp/{filename}"
                        await download.save_as(path)
                        parsed = _parse_downloaded_file(path)
                        downloaded_files[filename] = parsed
                        if on_download:
                            await on_download(filename, parsed)
                        extra_context = (
                            f"Download realizado: {filename}. "
                            f"Dados extraídos ({type(parsed).__name__}). "
                            "A tarefa está concluída — use action 'done'."
                        )
                    except Exception:
                        # Priority 3: plain click
                        await current_page.mouse.click(x, y)

                step = {"action": "click", "selector": "", "value": "",
                        "x": x, "y": y,
                        "description": desc, "waitTime": 500}

            elif act == "type":
                sel = action.get("selector", "")
                val = action.get("value", "")
                if sel:
                    try:
                        await current_page.fill(sel, val)
                    except Exception:
                        await current_page.keyboard.type(val)
                else:
                    await current_page.keyboard.type(val)
                step = {"action": "type", "selector": sel, "value": val,
                        "description": desc, "waitTime": 500}

            elif act == "clear_type":
                # Click field, select all, then type fresh value
                sel = action.get("selector", "")
                val = action.get("value", "")
                if sel:
                    try:
                        await current_page.click(sel)
                        await current_page.keyboard.press("Control+a")
                        await current_page.keyboard.press("Delete")
                        await current_page.fill(sel, val)
                    except Exception:
                        await current_page.keyboard.press("Control+a")
                        await current_page.keyboard.type(val)
                else:
                    await current_page.keyboard.press("Control+a")
                    await current_page.keyboard.type(val)
                step = {"action": "type", "selector": sel, "value": val,
                        "description": desc, "waitTime": 500}

            elif act == "select":
                sel = action.get("selector", "")
                val = action.get("value", "")
                try:
                    await current_page.select_option(sel, label=val, timeout=5000)
                except Exception:
                    try:
                        await current_page.select_option(sel, value=val, timeout=5000)
                    except Exception as e2:
                        error_msg = str(e2)
                if not error_msg:
                    step = {"action": "selectOption", "selector": sel, "value": val,
                            "description": desc, "waitTime": 500, "selectBy": "label"}

            elif act == "read_select":
                # Inspect element at coordinates and return options as context
                x, y = int(action.get("x", 640)), int(action.get("y", 360))
                el_info = await current_page.evaluate(_GET_ELEMENT_AT_JS, [x, y])
                if el_info and el_info.get("isSelect"):
                    opts = [o["label"] for o in el_info.get("options", [])]
                    extra_context = (
                        f"SELECT element found at ({x},{y}): selector={el_info.get('selector')!r}, "
                        f"options={opts}. Use action 'select' with this selector and one of these option labels."
                    )
                else:
                    extra_context = f"No <select> element at ({x},{y}). It may be a custom dropdown — try clicking it."

            elif act == "key":
                key = action.get("key", "Enter")
                await current_page.keyboard.press(key)
                step = {"action": "key", "selector": "", "value": key,
                        "description": desc, "waitTime": 300}

            elif act == "scroll":
                direction = action.get("direction", "down")
                delta = 400 if direction == "down" else -400
                await current_page.mouse.wheel(0, delta)

            elif act == "wait":
                await asyncio.sleep(2)

        except Exception as e:
            error_msg = str(e)

        # Wait for navigation / DOM settle
        try:
            await current_page.wait_for_load_state("domcontentloaded", timeout=4000)
        except Exception:
            pass
        await asyncio.sleep(0.5)

        if step:
            step_count += 1
            step["order"] = step_count
            await on_step(step)

        # Update conversation — store TEXT ONLY in history, never images
        # (images are sent fresh each turn via vision_turn, not accumulated)
        action_label = action.get("action", "?")
        action_summary = action.get("description") or action.get("url") or action.get("value") or action_label
        messages.append({"role": "user", "content": f"[Step {turn + 1}] Screenshot taken."})
        messages.append({"role": "assistant", "content": raw})
        if extra_context:
            messages.append({"role": "user", "content": extra_context})
        elif error_msg:
            messages.append({"role": "user", "content": f"Action '{action_label}' failed: {error_msg}. Try a different approach."})
        else:
            messages.append({"role": "user", "content": f"Action '{action_label}' ({action_summary}) executed successfully."})

    await on_done(success=False, message="Maximum steps reached without completing task", downloads=downloaded_files)
