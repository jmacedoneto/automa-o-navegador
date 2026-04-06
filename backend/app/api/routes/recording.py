"""
WebSocket browser recording endpoint.
Opens a Browserless session, streams screenshots to the frontend,
and records user interactions as AutoPilot steps.

Protocol (JSON messages):
  Client → Server:
    {"type": "navigate", "url": "..."}
    {"type": "click", "x": N, "y": N, "display_w": N, "display_h": N}
    {"type": "type", "selector": "...", "value": "...", "is_password": bool}
    {"type": "select_option", "selector": "...", "value": "...", "select_by": "label"|"value"}
    {"type": "key", "key": "Enter"}
    {"type": "delete_step", "index": N}
    {"type": "stop"}

  Server → Client:
    {"type": "ready", "viewport": {"w": N, "h": N}}
    {"type": "screenshot", "data": "base64..."}
    {"type": "step_added", "step": {...}}
    {"type": "steps_reset", "steps": [...]}
    {"type": "input_focused", "selector": "...", "is_password": bool}
    {"type": "select_options", "selector": "...", "options": [{"value": "...", "label": "..."}]}
    {"type": "live_url", "url": "..."}
    {"type": "steps", "steps": [...]}   ← final, sent on stop
    {"type": "error", "message": "..."}
"""
import asyncio
import base64
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from playwright.async_api import async_playwright

logger = logging.getLogger("recording")

from app.core.config import settings
from app.core.database import get_db, get_setting
from app.core.model_config import normalize_openai_model
from app.services.browserless_live import build_live_url
from app.services.computer_agent import run_agent
def create_recording_payload(automation_id: str | None) -> dict:
    return {"automation_id": automation_id, "status": "pending"}

router = APIRouter(prefix="/recording", tags=["recording"])

VIEWPORT_W = 1280
VIEWPORT_H = 720

# Injected before every page load — patches jQuery so Select2 / custom events are captured
# Also intercepts mousedown on <select> elements to prevent native dropdown from opening
_INIT_SCRIPT = """
window.__recEvents = [];
window.__pendingSelect = null;

// Intercept mousedown on SELECT elements in capture phase (fires before dropdown opens)
document.addEventListener('mousedown', function(e) {
    let el = e.target;
    for (let i = 0; i < 8 && el && el !== document; i++) {
        if (el.tagName === 'SELECT') {
            e.preventDefault();
            e.stopImmediatePropagation();
            let sel;
            if (el.id) sel = '#' + el.id;
            else if (el.getAttribute('name')) sel = 'select[name="' + el.getAttribute('name') + '"]';
            else {
                let parts = [], node = el;
                for (let j = 0; j < 6 && node && node.tagName; j++) {
                    let idx = 1, sib = node.previousElementSibling;
                    while (sib) { if (sib.tagName === node.tagName) idx++; sib = sib.previousElementSibling; }
                    parts.unshift(node.tagName.toLowerCase() + (idx > 1 ? ':nth-of-type(' + idx + ')' : ''));
                    node = node.parentElement;
                    if (node && node.id) { parts.unshift('#' + node.id); break; }
                }
                sel = parts.join(' > ');
            }
            window.__pendingSelect = {
                selector: sel,
                options: Array.from(el.options).map(o => ({ value: o.value, label: o.text.trim() }))
            };
            return;
        }
        el = el.parentElement;
    }
}, true);

const _patch = () => {
    if (!window.jQuery || window.__jqPatched) return;
    window.__jqPatched = true;
    const orig = jQuery.fn.trigger;
    jQuery.fn.trigger = function(type) {
        const t = (type && typeof type === 'object') ? type.type : String(type);
        if (t === 'change') {
            const el = this[0];
            if (el && el.id) {
                window.__recEvents.push({
                    action: el.tagName === 'SELECT' ? 'selectOption' : 'type',
                    selector: '#' + el.id,
                    value: el.tagName === 'SELECT'
                        ? (el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : el.value)
                        : el.value,
                    selectBy: el.tagName === 'SELECT' ? 'label' : undefined,
                });
            }
        }
        return orig.apply(this, arguments);
    };
};
const _t = setInterval(() => { _patch(); if (window.__jqPatched) clearInterval(_t); }, 150);
"""

_LIVE_CAPTURE_SCRIPT = """
window.__apLastEventSig = "";
window.__apLastEventAt = 0;

function __apSelector(el) {
    if (!el || el === document.body) return "body";
    const tag = el.tagName.toLowerCase();
    if (el.id) return "#" + CSS.escape(el.id);
    if (el.getAttribute('name')) return tag + '[name="' + el.getAttribute('name') + '"]';
    if (el.getAttribute('data-testid')) return '[data-testid="' + el.getAttribute('data-testid') + '"]';
    if (el.getAttribute('aria-label')) return '[aria-label="' + el.getAttribute('aria-label') + '"]';
    let parts = [], node = el;
    for (let i = 0; i < 6 && node && node.tagName; i++) {
        let part = node.tagName.toLowerCase();
        let idx = 1, sib = node.previousElementSibling;
        while (sib) { if (sib.tagName === node.tagName) idx++; sib = sib.previousElementSibling; }
        if (idx > 1) part += ':nth-of-type(' + idx + ')';
        parts.unshift(part);
        node = node.parentElement;
        if (node && node.id) { parts.unshift('#' + node.id); break; }
    }
    return parts.join(' > ');
}

function __apText(el) {
    return (el.innerText || el.textContent || el.value || el.title || el.placeholder || '').trim().slice(0, 60);
}

function __apPush(event) {
    const normalized = {
        action: event.action,
        selector: event.selector || '',
        value: event.value || '',
        description: event.description || '',
        waitTime: event.waitTime || 500,
        is_password: !!event.is_password,
        selectBy: event.selectBy
    };
    const sig = JSON.stringify(normalized);
    const now = Date.now();
    if (sig === window.__apLastEventSig && now - window.__apLastEventAt < 400) return;
    window.__apLastEventSig = sig;
    window.__apLastEventAt = now;
    window.__recEvents.push(normalized);
}

function __apClickable(el) {
    if (!el || el === document.body) return false;
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const type = (el.type || '').toLowerCase();
    if (['a', 'button', 'label'].includes(tag)) return true;
    if (tag === 'input' && ['checkbox', 'radio', 'submit', 'button', 'reset', 'image'].includes(type)) return true;
    if (['button', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'radio', 'checkbox', 'tab', 'switch', 'link'].includes(role)) return true;
    try { if (getComputedStyle(el).cursor === 'pointer') return true; } catch (_) {}
    return false;
}

document.addEventListener('click', function(e) {
    let target = e.target;
    while (target && target !== document.body) {
        const tag = target.tagName ? target.tagName.toLowerCase() : '';
        const type = (target.type || '').toLowerCase();
        if ((tag === 'input' && ['text', 'password', 'email', 'number', 'search', 'tel', 'url'].includes(type)) || tag === 'textarea') return;
        if (tag === 'select') return;
        if (__apClickable(target)) {
            __apPush({
                action: 'click',
                selector: __apSelector(target),
                description: __apText(target),
                waitTime: 500
            });
            return;
        }
        target = target.parentElement;
    }
}, true);

document.addEventListener('blur', function(e) {
    const target = e.target;
    if (!target || !target.tagName) return;
    const tag = target.tagName.toLowerCase();
    const type = (target.type || 'text').toLowerCase();
    if (tag !== 'input' && tag !== 'textarea') return;
    if (tag === 'input' && !['text', 'password', 'email', 'number', 'search', 'tel', 'url'].includes(type)) return;
    const value = target.value || '';
    if (!value) return;
    __apPush({
        action: 'type',
        selector: __apSelector(target),
        value: value,
        description: __apText(target),
        waitTime: 500,
        is_password: type === 'password'
    });
}, true);

document.addEventListener('change', function(e) {
    const target = e.target;
    if (!target || !target.tagName || target.tagName.toLowerCase() !== 'select') return;
    const value = target.value || '';
    if (!value) return;
    const option = target.options[target.selectedIndex];
    __apPush({
        action: 'selectOption',
        selector: __apSelector(target),
        value: option && option.text ? option.text.trim() : value,
        description: __apText(target),
        waitTime: 500,
        selectBy: 'label'
    });
}, true);
"""

# Returns info about the element at screen coordinates (x, y)
_GET_SELECT_OPTIONS_JS = """
(selector) => {
    const el = document.querySelector(selector);
    if (!el || el.tagName !== 'SELECT') return [];
    return Array.from(el.options).map(o => ({ value: o.value, label: o.text.trim() }));
}
"""

_GET_ELEMENT_JS = """
([x, y]) => {
    let el = document.elementFromPoint(x, y);
    if (!el) return null;

    // Walk up to find a native <select> (handles Select2/Chosen wrappers that
    // render a fake UI on top of a hidden <select>)
    let nativeSelect = null;
    if (el.tagName !== 'SELECT') {
        // Check if we're inside a Select2 container: look for data-select2-id
        // on a parent, or a sibling/parent <select>
        let node = el;
        for (let i = 0; i < 8 && node && node.tagName; i++) {
            if (node.tagName === 'SELECT') { nativeSelect = node; break; }
            // Select2: container has class select2 or select2-container
            const cls = node.className || '';
            if (typeof cls === 'string' && (cls.includes('select2') || cls.includes('chosen-'))) {
                // Try to find sibling/nearby select
                const parent = node.parentElement;
                if (parent) {
                    const sel = parent.querySelector('select');
                    if (sel) { nativeSelect = sel; break; }
                }
            }
            node = node.parentElement;
        }
        if (nativeSelect) el = nativeSelect;
    }

    const info = {
        tag: el.tagName.toLowerCase(),
        isInput: ['INPUT', 'TEXTAREA'].includes(el.tagName),
        isSelect: el.tagName === 'SELECT',
        inputType: el.type || '',
        text: (el.innerText || el.textContent || '').trim().slice(0, 60),
    };
    // Best selector: #id > [name] > nth-child path
    if (el.id) {
        info.selector = '#' + el.id;
    } else if (el.getAttribute('name')) {
        info.selector = el.tagName.toLowerCase() + '[name="' + el.getAttribute('name') + '"]';
    } else {
        let parts = [], node = el;
        for (let i = 0; i < 6 && node && node.tagName; i++) {
            let idx = 1, sib = node.previousElementSibling;
            while (sib) { if (sib.tagName === node.tagName) idx++; sib = sib.previousElementSibling; }
            parts.unshift(node.tagName.toLowerCase() + (idx > 1 ? ':nth-of-type(' + idx + ')' : ''));
            node = node.parentElement;
            if (node && node.id) { parts.unshift('#' + node.id); break; }
        }
        info.selector = parts.join(' > ');
    }
    return info;
}
"""


@router.websocket("/ws")
async def recording_ws(websocket: WebSocket):
    await websocket.accept()
    session_payload = create_recording_payload(websocket.query_params.get("automation_id"))
    db = get_db()
    session_res = db.table("recording_sessions").insert(session_payload).execute()
    session_id = session_res.data[0]["id"]
    logger.info("legacy recording session started", extra={"id": session_id, **session_payload})
    session_status = "pending"

    def _update_session(fields: dict):
        try:
            db.table("recording_sessions").update(fields).eq("id", session_id).execute()
        except Exception:
            pass

    browserless_url = ((await get_setting("browserless_url")) or settings.BROWSERLESS_URL or "").rstrip("/")
    if not browserless_url:
        await websocket.send_json({"type": "error", "message": "Browserless URL não configurado em Configurações"})
        await websocket.close()
        session_status = "failed"
        _update_session({
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })
        return

    cdp_url = browserless_url
    if cdp_url.startswith("https://"):
        cdp_url = cdp_url.replace("https://", "wss://")
    elif cdp_url.startswith("http://"):
        cdp_url = cdp_url.replace("http://", "ws://")
    browserless_token = ((await get_setting("browserless_token")) or settings.BROWSERLESS_TOKEN or "").strip()
    if browserless_token:
        cdp_url = f"{cdp_url}?token={browserless_token}"

    runtime_id = browserless_url
    _update_session({
        "status": "running",
        "runtime_id": runtime_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    session_status = "running"

    steps: list[dict] = []
    last_seen_url = ""
    last_screenshot_at = 0.0

    async def send(msg: dict):
        await websocket.send_json(msg)

    async def add_step(step: dict):
        nonlocal steps
        normalized = {
            "order": len(steps) + 1,
            "action": step.get("action", "click"),
            "selector": step.get("selector", ""),
            "value": step.get("value", ""),
            "description": step.get("description", ""),
            "waitTime": step.get("waitTime", 500),
        }
        if step.get("selectBy"):
            normalized["selectBy"] = step["selectBy"]

        last = steps[-1] if steps else None
        if last and all(
            last.get(field) == normalized.get(field)
            for field in ("action", "selector", "value", "description")
        ):
            return

        steps.append(normalized)
        await send({"type": "step_added", "step": normalized})

    async def push_screenshot(page):
        nonlocal last_screenshot_at
        try:
            img = await page.screenshot(full_page=False, type="jpeg", quality=70)
            await send({"type": "screenshot", "data": base64.b64encode(img).decode(), "fmt": "jpeg"})
            last_screenshot_at = asyncio.get_running_loop().time()
        except Exception:
            pass

    async def drain_jq(page):
        """Pull jQuery-captured events from the page and emit as steps."""
        try:
            evts = await page.evaluate("window.__recEvents && window.__recEvents.splice(0) || []")
        except Exception:
            return  # context destroyed by navigation — nothing to drain
        for ev in evts:
            await add_step({
                "action": ev.get("action", "click"),
                "selector": ev.get("selector", ""),
                "value": ev.get("value", ""),
                "description": ev.get("description", ""),
                "waitTime": 500,
                "selectBy": ev.get("selectBy"),
            })

    async def drain_live_events(page):
        try:
            evts = await page.evaluate("window.__recEvents && window.__recEvents.splice(0) || []")
        except Exception:
            return
        for ev in evts:
            value = "{{password}}" if ev.get("is_password") else ev.get("value", "")
            await add_step({
                "action": ev.get("action", "click"),
                "selector": ev.get("selector", ""),
                "value": value,
                "description": ev.get("description", ""),
                "waitTime": ev.get("waitTime", 500),
                "selectBy": ev.get("selectBy"),
            })

    async def maybe_track_navigation(page):
        nonlocal last_seen_url
        try:
            current_url = page.url
        except Exception:
            return
        if not current_url or current_url == "about:blank" or current_url == last_seen_url:
            return
        last_seen_url = current_url
        await add_step({
            "action": "navigate",
            "selector": "",
            "value": current_url,
            "description": "",
            "waitTime": 1000,
        })

    async def fetch_live_url(page_url: str):
        sessions_base = browserless_url
        if sessions_base.startswith("ws://"):
            sessions_base = sessions_base.replace("ws://", "http://", 1)
        elif sessions_base.startswith("wss://"):
            sessions_base = sessions_base.replace("wss://", "https://", 1)

        sessions_url = f"{sessions_base}/sessions"
        if browserless_token:
            sessions_url = f"{sessions_url}?token={browserless_token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(sessions_url)
                response.raise_for_status()
                sessions = response.json()
        except Exception as exc:
            logger.warning("could not fetch browserless sessions", extra={"error": str(exc)})
            return None

        current_session = None
        page_host = ""
        try:
            page_host = httpx.URL(page_url).host or ""
        except Exception:
            pass

        for session in sessions:
            session_url = session.get("url") or ""
            if page_host and page_host in session_url:
                current_session = session
                break

        if not current_session and sessions:
            current_session = sessions[0]
        if not current_session or not current_session.get("devtoolsFrontendUrl"):
            return None

        public_scheme = websocket.headers.get("x-forwarded-proto") or "https"
        public_host = (
            websocket.headers.get("x-forwarded-host")
            or websocket.headers.get("host")
            or (httpx.URL(browserless_url).host if "://" in browserless_url else browserless_url)
        )
        return build_live_url(
            devtools_frontend_url=current_session["devtoolsFrontendUrl"],
            public_scheme=public_scheme,
            public_host=public_host,
            token=browserless_token,
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            page = await browser.new_page()
            await page.set_viewport_size({"width": VIEWPORT_W, "height": VIEWPORT_H})
            await page.add_init_script(_INIT_SCRIPT)
            await page.add_init_script(_LIVE_CAPTURE_SCRIPT)
            await page.add_init_script(
                f"window.__autopilotRecordingSession = {json.dumps(session_payload)};"
            )

            await send({"type": "ready", "viewport": {"w": VIEWPORT_W, "h": VIEWPORT_H}})
            await push_screenshot(page)
            live_url = await fetch_live_url(page.url)
            if live_url:
                await send({"type": "live_url", "url": live_url})

            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                except asyncio.TimeoutError:
                    await maybe_track_navigation(page)
                    await drain_live_events(page)
                    if asyncio.get_running_loop().time() - last_screenshot_at > 1.0:
                        await push_screenshot(page)
                    continue

                msg = json.loads(raw)
                cmd = msg.get("type")

                # ── Navigate ────────────────────────────────────────────────
                if cmd == "navigate":
                    url = msg.get("url", "")
                    if url:
                        await add_step({
                            "action": "navigate",
                            "selector": "",
                            "value": url,
                            "description": "",
                            "waitTime": 1000,
                        })
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(0.8)
                        last_seen_url = page.url
                        await push_screenshot(page)
                        live_url = await fetch_live_url(page.url)
                        if live_url:
                            await send({"type": "live_url", "url": live_url})

                # ── Click ────────────────────────────────────────────────────
                elif cmd == "click":
                    disp_w = msg.get("display_w", VIEWPORT_W)
                    disp_h = msg.get("display_h", VIEWPORT_H)
                    ax = int(msg.get("x", 0) * VIEWPORT_W / disp_w)
                    ay = int(msg.get("y", 0) * VIEWPORT_H / disp_h)

                    # Detect element BEFORE clicking (context is guaranteed intact here)
                    el = None
                    try:
                        await page.evaluate("window.__pendingSelect = null")
                        el = await page.evaluate(_GET_ELEMENT_JS, [ax, ay])
                    except Exception:
                        pass
                    print(f"[REC] CLICK at ({ax},{ay}) pre-click el={el}", flush=True)

                    if el and el.get("isSelect"):
                        # Native select: fetch options without clicking (avoids native dropdown)
                        sel = el.get("selector", "")
                        try:
                            options = await page.evaluate(_GET_SELECT_OPTIONS_JS, sel)
                        except Exception:
                            options = []
                        print(f"[REC] SELECT via elementFromPoint selector={sel!r} options_count={len(options)}", flush=True)
                        await send({"type": "select_options", "selector": sel, "options": options})
                    else:
                        # Perform the actual mouse click
                        try:
                            await page.mouse.click(ax, ay)
                        except Exception as exc:
                            print(f"[REC] mouse.click error: {exc}", flush=True)

                        # Wait for any navigation to settle
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=5000)
                        except Exception:
                            pass
                        await asyncio.sleep(0.2)

                        # Check if mousedown listener intercepted a select AFTER click settled
                        pending_sel = None
                        try:
                            pending_sel = await page.evaluate(
                                "(function(){ var p=window.__pendingSelect; window.__pendingSelect=null; return p; })()"
                            )
                        except Exception:
                            pass  # navigation destroyed context — that's fine, it was a link click
                        print(f"[REC] post-click pending_sel={pending_sel}", flush=True)

                        # Fallback: check if a <select> got focused by the click
                        focused_select = None
                        if not pending_sel:
                            try:
                                focused_select = await page.evaluate("""
                                    () => {
                                        const el = document.activeElement;
                                        if (!el || el.tagName !== 'SELECT') return null;
                                        let sel = null;
                                        if (el.id) sel = '#' + el.id;
                                        else if (el.getAttribute('name')) sel = 'select[name="' + el.getAttribute('name') + '"]';
                                        if (!sel) return null;
                                        const opts = Array.from(el.options).map(o => ({value: o.value, label: o.text.trim()}));
                                        el.blur();  // prevent native dropdown from staying open
                                        return {selector: sel, options: opts};
                                    }
                                """)
                            except Exception:
                                pass

                        if pending_sel:
                            sel = pending_sel.get("selector", "")
                            options = pending_sel.get("options", [])
                            print(f"[REC] SELECT via mousedown selector={sel!r} options_count={len(options)}", flush=True)
                            await send({"type": "select_options", "selector": sel, "options": options})
                        elif focused_select:
                            sel = focused_select.get("selector", "")
                            options = focused_select.get("options", [])
                            print(f"[REC] SELECT via activeElement selector={sel!r} options_count={len(options)}", flush=True)
                            await send({"type": "select_options", "selector": sel, "options": options})
                        else:
                            await drain_jq(page)
                            if el:
                                sel = el.get("selector", "")
                                if el.get("isInput"):
                                    await send({"type": "input_focused", "selector": sel,
                                                "is_password": el.get("inputType") == "password"})
                                else:
                                    already = any(s.get("selector") == sel for s in steps[-3:])
                                    if not already:
                                        await add_step({
                                            "action": "click",
                                            "selector": sel,
                                            "value": "",
                                            "description": el.get("text", ""),
                                            "waitTime": 500,
                                        })

                        await push_screenshot(page)

                # ── Type ─────────────────────────────────────────────────────
                elif cmd == "type":
                    sel = msg.get("selector", "")
                    val = msg.get("value", "")
                    is_pwd = msg.get("is_password", False)
                    stored = "{{password}}" if is_pwd else val
                    try:
                        if sel:
                            await page.fill(sel, val)
                        else:
                            await page.keyboard.type(val)
                    except Exception:
                        pass
                    await add_step({
                        "action": "type",
                        "selector": sel,
                        "value": stored,
                        "description": "",
                        "waitTime": 500,
                    })
                    await push_screenshot(page)

                # ── Select option (from frontend picker) ─────────────────────
                elif cmd == "select_option":
                    sel = msg.get("selector", "")
                    val = msg.get("value", "")
                    select_by = msg.get("select_by", "label")
                    try:
                        if select_by == "value":
                            await page.select_option(sel, value=val)
                        else:
                            await page.select_option(sel, label=val)
                    except Exception:
                        try:
                            await page.select_option(sel, value=val)
                        except Exception:
                            pass
                    await add_step({
                        "action": "selectOption",
                        "selector": sel,
                        "value": val,
                        "description": "",
                        "waitTime": 500,
                        "selectBy": select_by,
                    })
                    await drain_jq(page)
                    await push_screenshot(page)

                # ── Key press ────────────────────────────────────────────────
                elif cmd == "key":
                    await page.keyboard.press(msg.get("key", "Enter"))
                    # Wait for any navigation triggered by the key press (e.g. Enter on a form)
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    await asyncio.sleep(0.3)
                    await push_screenshot(page)

                # ── Delete step ──────────────────────────────────────────────
                elif cmd == "delete_step":
                    idx = msg.get("index", -1)
                    if 0 <= idx < len(steps):
                        steps.pop(idx)
                        for i, s in enumerate(steps):
                            s["order"] = i + 1
                        await send({"type": "steps_reset", "steps": steps})

                # ── AI Agent run ─────────────────────────────────────────────
                elif cmd == "agent_run":
                    instruction = msg.get("instruction", "")
                    if not instruction:
                        await send({"type": "agent_error", "message": "Instrução vazia"})
                    else:
                        api_key = await get_setting("openai_api_key")
                        model = normalize_openai_model(await get_setting("openai_model"))
                        if not api_key:
                            await send({"type": "agent_error", "message": "OpenAI API key não configurada em Configurações"})
                        else:
                            await send({"type": "agent_started"})

                            async def _on_screenshot(b64: str):
                                await send({"type": "screenshot", "data": b64, "fmt": "png"})

                            async def _on_action(action: dict):
                                await send({"type": "agent_action", "action": action})

                            async def _on_step(step: dict):
                                steps.append(step)
                                await send({"type": "step_added", "step": step})

                            async def _on_done(success: bool = True, message: str = ""):
                                await send({"type": "agent_done", "success": success, "message": message})

                            await run_agent(
                                page=page,
                                instruction=instruction,
                                api_key=api_key,
                                model=model,
                                on_screenshot=_on_screenshot,
                                on_action=_on_action,
                                on_step=_on_step,
                                on_done=_on_done,
                            )

                # ── Stop & return steps ──────────────────────────────────────
                elif cmd == "stop":
                    session_status = "finished"
                    await send({"type": "steps", "steps": steps})
                    break

            await browser.close()

    except WebSocketDisconnect:
        session_status = "cancelled"
        pass
    except Exception as e:
        session_status = "failed"
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        _update_session({
            "status": session_status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })
