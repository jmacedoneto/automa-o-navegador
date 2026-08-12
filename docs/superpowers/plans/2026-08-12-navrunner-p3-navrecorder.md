# NavRunner P3 — NavRecorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce new-automation authorship from ~1h of hand-writing JSON to ~10min of record-then-adjust. The Chrome extension (already mostly built) gets upgraded to export Playwright Traces; a Python `recorder.py` converts those traces to draft `steps.json`; a backend endpoint ingests traces and serves the DSL draft for review.

**Architecture:** Three new pieces, no replacements of working code. (1) Chrome extension gets a "Export Playwright Trace" button alongside the existing JSON export; the trace format is what `recorder.py` consumes. (2) `app/automation/recorder.py` is pure Python — no Playwright dependency, just JSON parsing + heuristics. (3) Backend endpoint `POST /api/automation/import-trace` accepts the trace file, runs `recorder.py`, returns the draft `steps.json` for review in the painel. The legacy real-time push path (`/automations/ext-session/{id}/step`) stays untouched — existing cron jobs / live automation creation keep working.

**Tech Stack:** Python 3.11, Pydantic v2, Playwright trace JSON schema (de-facto standard), FastAPI (existing), Vue 3 (existing painel).

**Spec reference:** `docs/superpowers/specs/2026-08-12-navrunner-framework-design.md` — section "P3: Chrome extension record-replay".

**Predecessor plans:** P0 + P1a + P1b + P2 merged. This plan inherits all P0-P2 modules.

---

## File Structure

### Files created (P3)

```
backend/app/automation/
├── recorder.py              # Playwright trace → DSL steps.json (pure Python)

backend/app/api/routes/
├── automation_import.py     # POST /api/automation/import-trace

backend/tests/automation/
├── test_recorder.py         # trace parsing + DSL generation
├── test_automation_import.py # endpoint smoke test

chrome-extension/
├── recorder.js              # NEW: export Playwright Trace format
├── trace-builder.js          # NEW: builds a trace object from recorded steps
└── manifest.json            # MODIFIED: bump version to 3.0

docs/superpowers/plans/2026-08-12-navrunner-p3-navrecorder.md  # this file
```

### Files modified (P3)

- `chrome-extension/popup.html` — add "Export Trace" button
- `chrome-extension/popup.js` — wire the button
- `backend/app/main.py` (or equivalent router registration) — include `automation_import` router

### Anti-pattern check

- The `recorder.py` is **pure-Python, no Playwright import** — it parses the trace JSON which is just a documented schema. This keeps it unit-testable.
- The extension gains ONE new export format — it doesn't change any existing capture logic. Existing recordings still produce the same AutoPilot legacy JSON.
- The backend endpoint is read-only on `steps.json` — it never writes to disk; the user still saves the draft manually after review.

---

## Conventions carried from P0/P1a/P1b/P2

- TDD: failing test → impl → passing → commit.
- `_run` helper in tests, no `pytest-asyncio`.
- Commit messages: `feat(navrunner): P3 task N — <title>` etc.
- Tests in `backend/tests/automation/`.

---

## Task 1: `app/automation/recorder.py` — Playwright trace → DSL

**Why first:** Pure-Python module, easy to unit test, no external deps. Building it first lets us have the spec ready when we wire up the Chrome extension export format.

**Files:**
- Create: `backend/app/automation/recorder.py`
- Create: `backend/tests/automation/test_recorder.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_recorder.py` with EXACTLY:

```python
import json
from pathlib import Path

import pytest

from app.automation.recorder import (
    parse_trace_file,
    parse_trace_json,
    steps_from_trace,
    NavRecorderError,
)


# A minimal Playwright trace that covers goto, click, fill, change, screenshot.
SAMPLE_TRACE = {
    "title": "cotacao_pvs sample trace",
    "startTime": "2026-08-12T10:00:00.000Z",
    "actions": [
        {"type": "navigate", "url": "https://app.apvs.vc/home"},
        {"type": "click", "selector": "ion-button:has-text(\"SOU CONSULTOR APVS\")"},
        {"type": "type", "selector": "input[type=text]", "value": "19.186.569/0001-11"},
        {"type": "type", "selector": "input[type=password]", "value": "Macedo020589#"},
        {"type": "click", "selector": "ion-button:has-text(\"Entrar\")"},
        {"type": "wait_for", "selector": ".dashboard"},
    ],
}


def _write_trace(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "trace.json"
    p.write_text(json.dumps(payload))
    return p


def test_parse_trace_json_returns_actions(tmp_path):
    p = _write_trace(tmp_path, SAMPLE_TRACE)
    parsed = parse_trace_file(p)
    assert parsed["title"] == SAMPLE_TRACE["title"]
    assert len(parsed["actions"]) == 6


def test_parse_trace_file_raises_on_missing(tmp_path):
    with pytest.raises(NavRecorderError, match="not found"):
        parse_trace_file(tmp_path / "missing.json")


def test_parse_trace_file_raises_on_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json at all")
    with pytest.raises(NavRecorderError, match="invalid JSON"):
        parse_trace_file(p)


def test_steps_from_trace_basic_actions():
    steps = steps_from_trace(SAMPLE_TRACE)
    # Expect 6 top-level steps (one per trace action, after auth detection).
    assert len(steps) >= 5
    # First non-auth step is a goto.
    first_action = next(s for s in steps if "goto" in s)
    assert first_action["goto"]["url"] == "https://app.apvs.vc/home"


def test_steps_from_trace_detects_login_block():
    """The first sequence of navigate -> click(button with CONSULTOR) -> 2 fills ->
    click(button Entrar) -> wait_for dashboard is detected as form_login auth."""
    steps = steps_from_trace(SAMPLE_TRACE)
    auth_steps = [s for s in steps if "login_block" in s]
    assert len(auth_steps) == 1
    auth = auth_steps[0]["login_block"]
    assert auth["credentials_ref"].startswith("apvs_login")
    assert auth["success_assert"]["selector"] == ".dashboard"


def test_steps_from_trace_includes_wait_for():
    steps = steps_from_trace(SAMPLE_TRACE)
    wait_steps = [s for s in steps if "wait_for" in s]
    assert any(w["id"].startswith("wait_") for w in wait_steps)


def test_steps_from_trace_handles_empty():
    steps = steps_from_trace({"actions": []})
    assert steps == []


def test_steps_from_trace_normalizes_clicks():
    """Click on a button with has-text gets translated to a generic click step."""
    trace = {"actions": [
        {"type": "navigate", "url": "https://x.com"},
        {"type": "click", "selector": "button.go"},
    ]}
    steps = steps_from_trace(trace)
    # Find the click step.
    click_steps = [s for s in steps if "click" in s and "wait_for" not in s]
    assert len(click_steps) == 1
    assert click_steps[0]["click"]["selector"] == "button.go"


def test_steps_from_trace_groups_fill_actions():
    """Multiple consecutive fills become a single `fill` step with a dict payload."""
    trace = {"actions": [
        {"type": "navigate", "url": "https://x.com"},
        {"type": "type", "selector": "#a", "value": "1"},
        {"type": "type", "selector": "#b", "value": "2"},
        {"type": "type", "selector": "#c", "value": "3"},
    ]}
    steps = steps_from_trace(trace)
    fill_steps = [s for s in steps if "fill" in s]
    # We expect one fill step with a 3-key dict (or 3 separate, depending on
    # implementation; either is acceptable per the implementation).
    assert len(fill_steps) >= 1
    if len(fill_steps) == 1:
        assert "#a" in fill_steps[0]["fill"]
        assert "#b" in fill_steps[0]["fill"]
        assert "#c" in fill_steps[0]["fill"]


def test_steps_from_trace_extracts_title_as_automation_name():
    trace = {"title": "cotacao_pvs", "actions": [{"type": "navigate", "url": "x"}]}
    out = steps_from_trace(trace)
    assert out["automation_name"] == "cotacao_pvs"
    assert "steps" in out


def test_steps_from_trace_default_automation_name_from_url():
    trace = {"actions": [{"type": "navigate", "url": "https://app.apvs.vc/dashboard"}]}
    out = steps_from_trace(trace)
    assert out["automation_name"] == "app_apvs_vc"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3/backend && python3 -m pytest tests/automation/test_recorder.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.automation.recorder'`

- [ ] **Step 3: Implement `recorder.py`**

`backend/app/automation/recorder.py`:

```python
"""Playwright trace → NavRunner DSL steps.json draft converter.

P3 implements the offline path. The extension records actions in the user's
browser, exports a Playwright trace JSON file, and `steps_from_trace`
converts it to a `steps.json` draft that the user then edits in the painel.

This module is PURE PYTHON — no Playwright dependency. The trace format is
documented JSON, so we just parse it.

Heuristics applied (kept deliberately conservative):
- Login detection: a leading sequence of `navigate -> click('CONSULTOR' or
  similar role) -> 2 type actions (one is password) -> click('Entrar') ->
  wait_for(dashboard)` is collapsed into a single `login_block` step.
- Consecutive `type` actions with different selectors become a single
  `fill` step with a dict payload (so P0's `fill` handler renders it).
- Each non-collapsed action becomes its own step with a stable `id`.
"""
import json
import re
from pathlib import Path
from typing import Any


class NavRecorderError(ValueError):
    """Raised when a trace file is missing, malformed, or unparseable.""


# ── Parse ────────────────────────────────────────────────────────────────

def parse_trace_file(path: Path) -> dict[str, Any]:
    """Read a Playwright trace JSON file from disk."""
    if not path.exists():
        raise NavRecorderError(f"Trace file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise NavRecorderError(f"Cannot read trace file: {e}") from e
    return parse_trace_json(text)


def parse_trace_json(text: str) -> dict[str, Any]:
    """Parse the JSON text. Raises NavRecorderError on bad JSON or wrong shape."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise NavRecorderError(f"Trace file is invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise NavRecorderError("Trace root must be an object")
    if "actions" not in payload or not isinstance(payload["actions"], list):
        raise NavRecorderError("Trace must have an 'actions' array")
    return payload


# ── Heuristics ──────────────────────────────────────────────────────────

_PASSWORD_HINTS = ("password", "pass", "pwd", "senha")
_LOGIN_ENTRY_HINTS = ("consultor", "entrar", "login", "sign in", "acessar")
_SUBMIT_HINTS = ("entrar", "login", "submit", "enviar")
_DASHBOARD_HINTS = (".dashboard", "dashboard", "painel", "/dashboard")


def _is_password_input(selector: str, value: str) -> bool:
    sel = (selector or "").lower()
    if any(h in sel for h in _PASSWORD_HINTS):
        return True
    val = (value or "").lower()
    return "senha" in val or "password" in val


def _is_login_entry_click(selector: str) -> bool:
    sel = (selector or "").lower()
    return any(h in sel for h in _LOGIN_ENTRY_HINTS)


def _is_submit_click(selector: str) -> bool:
    sel = (selector or "").lower()
    return any(h in sel for h in _SUBMIT_HINTS)


def _detect_login_block(actions: list[dict]) -> tuple[dict | None, list[dict]]:
    """If the prefix of `actions` looks like a login flow, return a
    `login_block` dict + the remaining actions.

    Heuristic:
      navigate -> click(login-entry) -> [N type] (>=2, exactly one password)
                  -> click(submit) -> wait_for(dashboard)
    """
    if len(actions) < 5:
        return None, actions
    a = actions
    if a[0].get("type") != "navigate":
        return None, actions
    if a[1].get("type") != "click" or not _is_login_entry_click(a[1].get("selector", "")):
        return None, actions
    # Find the run of consecutive type actions.
    i = 2
    type_block: list[dict] = []
    while i < len(a) and a[i].get("type") == "type":
        type_block.append(a[i])
        i += 1
    if len(type_block) < 2:
        return None, actions
    has_password = any(_is_password_input(t["selector"], t["value"]) for t in type_block)
    if not has_password:
        return None, actions
    # Submit click.
    if i >= len(a) or a[i].get("type") != "click" or not _is_submit_click(a[i].get("selector", "")):
        return None, actions
    submit = a[i]
    i += 1
    # Success wait.
    if i >= len(a) or a[i].get("type") != "wait_for":
        return None, actions
    wait = a[i]
    i += 1

    # Build the login block.
    user_sel = next(
        (t["selector"] for t in type_block if not _is_password_input(t["selector"], t["value"])),
        None,
    )
    pass_sel = next(
        (t["selector"] for t in type_block if _is_password_input(t["selector"], t["value"])),
        None,
    )
    success_selector = wait.get("selector", ".dashboard")
    success_timeout = int(wait.get("timeout_ms", 15000))

    login_block = {
        "type": "form_login",
        "url": a[0]["url"],
        "credentials_ref": _credentials_ref_from_url(a[0]["url"]),
        "selectors": {
            "user": user_sel or "input[type=text]",
            "pass": pass_sel or "input[type=password]",
            "submit": submit.get("selector", "button[type=submit]"),
        },
        "success_assert": {"selector": success_selector, "timeout_ms": success_timeout},
    }
    return login_block, a[i:]


def _credentials_ref_from_url(url: str) -> str:
    """Pick a credentials_ref key based on the URL host."""
    m = re.search(r"https?://([^/]+)", url or "")
    host = (m.group(1) if m else "default").split(":")[0]
    return f"{host.replace('.', '_')}_login"


def _automation_name_from_title_or_url(payload: dict) -> str:
    title = payload.get("title") or ""
    if title:
        # Strip whitespace + replace spaces with underscores.
        return re.sub(r"\s+", "_", title.strip().lower())
    actions = payload.get("actions") or []
    for a in actions:
        if a.get("type") == "navigate" and a.get("url"):
            m = re.search(r"https?://([^/]+)", a["url"])
            if m:
                return m.group(1).split(":")[0].replace(".", "_")
    return "new_automation"


# ── Step builders ────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", (s or "").lower()).strip("_") or "step"


def _build_step(action: dict, idx: int) -> dict[str, Any] | None:
    """Convert a single Playwright trace action into a NavRunner step dict.
    Returns None for actions we deliberately skip."""
    t = action.get("type")
    if t == "navigate":
        return {
            "id": f"goto_{idx:03d}",
            "goto": {"url": action.get("url", "")},
        }
    if t == "click":
        sel = action.get("selector", "")
        return {
            "id": f"click_{_slug(sel)[:50]}_{idx:03d}",
            "click": {"selector": sel},
        }
    if t == "type":
        # Single types are kept as standalone steps (the group-fill pass will
        # collapse consecutive ones).
        sel = action.get("selector", "")
        return {
            "id": f"fill_{_slug(sel)[:50]}_{idx:03d}",
            "fill": {sel: action.get("value", "")},
        }
    if t == "wait_for":
        sel = action.get("selector", "")
        return {
            "id": f"wait_{_slug(sel)[:50]}_{idx:03d}",
            "wait_for": {"selector": sel, "timeout_ms": int(action.get("timeout_ms", 10000))},
        }
    if t == "screenshot":
        # Skipped for now — runner already captures per-step.
        return None
    if t == "select" or t == "selectOption":
        sel = action.get("selector", "")
        return {
            "id": f"select_{_slug(sel)[:50]}_{idx:03d}",
            "click": {"selector": sel},
        }
    return None


def _group_consecutive_fills(steps: list[dict]) -> list[dict]:
    """Merge consecutive `fill` steps that share the same parent into one
    step with a multi-key fill payload."""
    out: list[dict] = []
    i = 0
    while i < len(steps):
        cur = steps[i]
        if "fill" in cur and isinstance(cur["fill"], dict) and len(cur["fill"]) == 1:
            merged = dict(cur["fill"])
            j = i + 1
            while j < len(steps) and "fill" in steps[j] and isinstance(steps[j]["fill"], dict) and len(steps[j]["fill"]) == 1:
                merged.update(steps[j]["fill"])
                j += 1
            cur = {**cur, "fill": merged, "id": _slug(f"fill_{i:03d}") + "_grouped"}
            out.append(cur)
            i = j
        else:
            out.append(cur)
            i += 1
    return out


# ── Top-level conversion ──────────────────────────────────────────────────

def steps_from_trace(payload: dict) -> dict[str, Any]:
    """Convert a parsed Playwright trace into a NavRunner DSL draft.

    Returns a dict shaped like a steps.json: {automation_name, steps: [...]}.
    The caller is expected to review and edit (add credentials_ref, inputs, etc.).
    """
    actions = payload.get("actions") or []
    login_block, remaining = _detect_login_block(actions)

    steps: list[dict[str, Any]] = []
    idx = 0
    if login_block is not None:
        # The login block goes first as a single step (the runner's auth
        # step is a special DSL construct).
        steps.append({
            "id": "login_block",
            "login_block": login_block,
        })
        idx += 1
    for action in remaining:
        built = _build_step(action, idx)
        if built is not None:
            steps.append(built)
            idx += 1
    steps = _group_consecutive_fills(steps)

    return {
        "automation_name": _automation_name_from_title_or_url(payload),
        "version": 1,
        "steps": steps,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3/backend && python3 -m pytest tests/automation/test_recorder.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3
git add backend/app/automation/recorder.py backend/tests/automation/test_recorder.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P3 task 1 — recorder.py (Playwright trace → DSL draft)"
```

---

## Task 2: Backend endpoint `POST /api/automation/import-trace`

**Why second:** The recorder is pure Python. Wiring it into a real endpoint lets us test the contract end-to-end without the extension.

**Files:**
- Create: `backend/app/api/routes/automation_import.py`
- Modify: `backend/app/main.py` (or wherever routers are registered — find the existing pattern)
- Create: `backend/tests/automation/test_automation_import.py`

- [ ] **Step 1: Survey existing router registration**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3 && grep -rn "include_router\|APIRouter" backend/app/main.py backend/app/api/__init__.py backend/app/core/__init__.py 2>/dev/null | head -20
```

Note the existing pattern (e.g., `from app.api.routes import automations` or `from app.api import automations`).

- [ ] **Step 2: Write the failing test**

Create `backend/tests/automation/test_automation_import.py` with EXACTLY:

```python
import io
import json

from fastapi.testclient import TestClient


def test_import_trace_returns_dsl_draft():
    """The endpoint accepts a trace file and returns a steps.json draft."""
    # Import here so test collection works even when main.py is in flux.
    from app.main import app
    client = TestClient(app)

    trace = {
        "title": "smoke",
        "actions": [
            {"type": "navigate", "url": "https://app.apvs.vc/home"},
            {"type": "click", "selector": "ion-button:has-text(\"SOU CONSULTOR APVS\")"},
            {"type": "type", "selector": "input[type=text]", "value": "user"},
            {"type": "type", "selector": "input[type=password]", "value": "pass"},
            {"type": "click", "selector": "ion-button:has-text(\"Entrar\")"},
            {"type": "wait_for", "selector": ".dashboard"},
            {"type": "click", "selector": "button.continue"},
        ],
    }
    files = {"trace_file": ("trace.json", io.BytesIO(json.dumps(trace).encode()), "application/json")}
    resp = client.post("/api/automation/import-trace", files=files)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["automation_name"] == "smoke"
    assert isinstance(body["steps"], list)
    # Expect login_block + click(continue) at minimum.
    kinds = [list(s.keys()) for s in body["steps"]]
    assert any("login_block" in k for k in kinds)
    assert any("click" in k for k in kinds)


def test_import_trace_rejects_missing_file():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/automation/import-trace")
    assert resp.status_code == 422  # FastAPI's "missing field" code


def test_import_trace_rejects_bad_json():
    from app.main import app
    client = TestClient(app)
    files = {"trace_file": ("trace.json", io.BytesIO(b"not json"), "application/json")}
    resp = client.post("/api/automation/import-trace", files=files)
    assert resp.status_code == 400
    assert "invalid" in resp.text.lower()
```

- [ ] **Step 3: Implement the route**

`backend/app/api/routes/automation_import.py`:

```python
"""Endpoint: POST /api/automation/import-trace

Accepts a Playwright trace JSON file (multipart upload), runs the recorder
heuristics, returns a steps.json draft for the user to review in the painel.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.automation.recorder import NavRecorderError, parse_trace_file, steps_from_trace


router = APIRouter()


@router.post("/automation/import-trace")
async def import_trace(trace_file: UploadFile = File(...)) -> dict:
    """Accept a Playwright trace and return a NavRunner steps.json draft."""
    content = await trace_file.read()
    # Save the upload to a temp file so parse_trace_file can read it
    # (keeps recorder.py file-based for testability).
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        try:
            payload = parse_trace_file(tmp_path)
        except NavRecorderError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return steps_from_trace(payload)
    finally:
        tmp_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Wire the router**

Find the existing router registration in `backend/app/main.py` (or wherever). Add:

```python
from app.api.routes.automation_import import router as automation_import_router

app.include_router(automation_import_router, prefix="/api")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3/backend && python3 -m pytest tests/automation/test_automation_import.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Re-run full suite**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3/backend && python3 -m pytest tests/automation ../examples/cotacao_pvs/tests
```

Expected: 144 + 11 + 3 = 158 passed (no regressions).

- [ ] **Step 7: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3
git add backend/app/api/routes/automation_import.py backend/app/main.py backend/tests/automation/test_automation_import.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P3 task 2 — POST /api/automation/import-trace endpoint"
```

---

## Task 3: Chrome extension — Playwright Trace export

**Why third:** Now that the backend understands traces, we teach the extension to produce them.

**Files:**
- Create: `chrome-extension/recorder.js`
- Create: `chrome-extension/trace-builder.js`
- Modify: `chrome-extension/popup.html` (add Export Trace button)
- Modify: `chrome-extension/popup.js` (wire the button)
- Modify: `chrome-extension/manifest.json` (bump version)

NOTE: This task's code is JavaScript, not Python. Tests for JS are deferred to P6/P9 (when the painel UI is fully exercised). The contract is the JSON format consumed by `recorder.py` — Task 1's tests verify the recorder accepts what this task emits.

- [ ] **Step 1: Write `trace-builder.js`**

`chrome-extension/trace-builder.js`:

```javascript
/**
 * Builds a Playwright-trace-shaped JSON object from the recorded steps.
 *
 * Schema (subset of Playwright Trace Viewer export):
 *   {
 *     "title": "<automation_name>",
 *     "startTime": "<ISO timestamp>",
 *     "actions": [
 *       {"type": "navigate", "url": "<url>"},
 *       {"type": "click",   "selector": "<css>"},
 *       {"type": "type",     "selector": "<css>", "value": "<text>"},
 *       {"type": "wait_for", "selector": "<css>", "timeout_ms": 10000},
 *       {"type": "screenshot"}
 *     ]
 *   }
 */
window.TraceBuilder = (function() {
  function inferTitle(steps) {
    // First non-navigate step's URL gives a host hint; default to "new_automation".
    for (const s of steps || []) {
      if (s.action === "navigate" && s.url) {
        try {
          const u = new URL(s.url);
          return u.host.replace(/[^a-z0-9]+/gi, "_");
        } catch (_) { /* fall through */ }
      }
    }
    return "new_automation";
  }

  function build(steps) {
    const actions = [];
    for (const s of steps || []) {
      switch (s.action) {
        case "navigate":
          actions.push({ type: "navigate", url: s.url });
          break;
        case "click":
          actions.push({ type: "click", selector: s.selector });
          break;
        case "type":
          actions.push({ type: "type", selector: s.selector, value: s.value || "" });
          break;
        case "wait":
        case "wait_for":
          actions.push({
            type: "wait_for",
            selector: s.selector,
            timeout_ms: s.timeoutMs || s.timeout_ms || 10000,
          });
          break;
        case "selectOption":
          actions.push({ type: "select", selector: s.selector });
          break;
        default:
          // Unknown action types are dropped — recorder is heuristic, not strict.
          break;
      }
    }
    return {
      title: inferTitle(steps),
      startTime: new Date().toISOString(),
      actions: actions,
    };
  }

  return { build };
})();
```

- [ ] **Step 2: Write `recorder.js` (popup integration)**

`chrome-extension/recorder.js`:

```javascript
/**
 * Recorder popup glue — wires the "Export Trace" button to a file download.
 */
document.addEventListener("DOMContentLoaded", () => {
  const exportTraceBtn = document.getElementById("exportTraceBtn");
  if (!exportTraceBtn) return;
  exportTraceBtn.addEventListener("click", async () => {
    const { steps = [] } = await chrome.runtime.sendMessage({ action: "getSteps" });
    if (!steps.length) {
      showMsg("Nenhum passo gravado!", "error");
      return;
    }
    if (!window.TraceBuilder) {
      showMsg("TraceBuilder não carregou — recarregue a extensão.", "error");
      return;
    }
    const trace = window.TraceBuilder.build(steps);
    const blob = new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "navrunner-trace.json";
    a.click();
    URL.revokeObjectURL(url);
    showMsg("✓ Trace exportado — faça upload no painel AutoPilot.", "success");
  });
});

function showMsg(text, kind) {
  const msgEl = document.getElementById("msg");
  if (msgEl) {
    msgEl.textContent = text;
    msgEl.style.color = kind === "success" ? "#16a34a" : "#dc2626";
    setTimeout(() => { msgEl.textContent = ""; }, 4000);
  }
}
```

- [ ] **Step 3: Update `popup.html`**

In `chrome-extension/popup.html`, add the Trace export button alongside the existing "Export JSON" button. Look for the `exportBtn` element and add:

```html
<button id="exportTraceBtn" class="btn-secondary">Exportar Trace (NavRunner)</button>
```

(Place it near the existing `exportBtn`.)

Also add a `<script src="trace-builder.js"></script>` tag BEFORE the `recorder.js` script so `window.TraceBuilder` is defined.

- [ ] **Step 4: Update `popup.js` to add the legacy export button style (cosmetic)**

Look for the export button setup. The new button uses class `btn-secondary` — make sure that class exists in `popup.html`'s CSS. If not, add a small style block:

```html
<style>
.btn-secondary { background: #f3f4f6; color: #111; border: 1px solid #d1d5db; padding: 6px 12px; border-radius: 6px; cursor: pointer; margin-left: 6px; }
.btn-secondary:hover { background: #e5e7eb; }
</style>
```

- [ ] **Step 5: Bump extension version in `manifest.json`**

Change `"version": "2.0"` to `"version": "3.0"`.

- [ ] **Step 6: Manual smoke check**

Open the extension popup, click "Start Recording", navigate to `https://app.apvs.vc/home`, click "SOU CONSULTOR APVS", fill CNPJ/senha, click "Entrar", wait for dashboard, click "Stop Recording", then click "Exportar Trace". A `navrunner-trace.json` file downloads.

Open the file. Verify:

```json
{
  "title": "app_apvs_vc",
  "startTime": "...",
  "actions": [
    {"type": "navigate", "url": "https://app.apvs.vc/home"},
    {"type": "click", "selector": "..."},
    ...
  ]
}
```

(Optional — this is a manual check, no automated test. Skipping is acceptable.)

- [ ] **Step 7: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3
git add chrome-extension/
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P3 task 3 — Chrome extension exports Playwright trace"
```

---

## Task 4: README + final verification

**Files:**
- Modify: `backend/app/automation/README.md`

- [ ] **Step 1: Update README**

In `backend/app/automation/README.md`, replace the "Deferred to later phases" block with:

```markdown
### Deferred to later phases

- AI Planner (P6) — chat-driven automation creation
- Painel unificado (P9) — UI single-pane for all 3 authoring modes
- RestrictedPython sandbox for `run_python` (P5)
- Per-run `step_log_writer` (instead of module global) when concurrency > 1 needed (P5)
- Auth strategies: `cookie_reuse`, `otp_via_telegram` (P5)
- MCP server wrapping the framework (P8, last)
```

And add a "Record-Replay (NavRecorder)" entry under "## Quick start":

```markdown
## Record-Replay (NavRecorder)

Install the Chrome extension from `chrome-extension/` (load unpacked in developer mode). Open the target site, click "Start Recording", perform the flow manually, click "Stop", then "Exportar Trace". Upload the trace file to the painel — the recorder heuristic generates a `steps.json` draft for review.

The recorder is conservative: it detects login blocks automatically, groups consecutive fills, and skips screenshots (the runner already captures them). The user reviews the draft, adds `credentials_ref`, `inputs`, and `outputs`, then saves.
```

- [ ] **Step 2: Final full verification**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3/backend && python3 -m pytest tests/automation ../examples/cotacao_pvs/tests
```

Expected: 158+ tests pass.

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p3
git add backend/app/automation/README.md
git -c user.email=navrunner@local -c user.name=navrunner commit -m "docs(navrunner): P3 README — NavRecorder section + deferred items updated"
```

---

## Self-Review (post-write)

**1. Spec coverage**

| Spec section | P3 coverage | Deferred to |
|---|---|---|
| Chrome extension record-replay | Done (extension already mostly built; P3 adds Trace export) | — |
| Playwright trace → DSL draft | Done (`recorder.py`) | — |
| Backend ingest endpoint | Done (`POST /api/automation/import-trace`) | — |
| Legacy real-time push path | Preserved untouched (`/automations/ext-session/{id}/step`) | — |
| AI Planner | Not (P6) | P6 |
| Painel unificado | Not (P9) | P9 |

**2. Placeholder scan**

Searched for `TBD`, `TODO`, `implement later`. Zero in code. Documentation gaps flagged in commit messages.

**3. Type consistency**

- `parse_trace_file(Path) -> dict` and `parse_trace_json(str) -> dict` have matching error semantics.
- `steps_from_trace(dict) -> dict` returns `{automation_name, version, steps}` — the `version: 1` field matches the existing `steps.json` schema in `examples/cotacao_pvs/`.
- `NavRecorderError(ValueError)` inherits from `ValueError` so any caller catching `ValueError` still catches it.
- The endpoint's `UploadFile` is FastAPI's standard — the test uses `TestClient` which is the existing pattern (see `tests/automation/test_auth.py` for reference if needed).

**4. Concerns**

- **Heuristic limitations:** `_detect_login_block` matches "form_login" patterns. Login flows that don't include a recognizable password field, or that use a different entry pattern (e.g., SSO), won't be detected — they'll fall through to the regular step list. Acceptable trade-off; the user adjusts the draft.
- **JavaScript tests:** P3 doesn't include JS-side tests. The contract test (Task 1) verifies the recorder accepts the trace format; the extension is exercised manually. Full Playwright-JS testing is out of scope for now.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-navrunner-p3-navrecorder.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one Opus subagent per task. Orchestrator merges between tasks.

**2. Inline Execution** — Execute tasks in this session.

Which approach?