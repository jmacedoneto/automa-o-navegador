"""Playwright trace → NavRunner DSL steps.json draft converter.

P3 implements the offline path. The extension records actions in the user's
browser, exports a Playwright trace JSON file, and `steps_from_trace`
converts it to a `steps.json` draft that the user then edits in the painel.

This module is PURE PYTHON — no Playwright dependency. The trace format is
documented JSON, so we just parse it.

Heuristics applied (kept deliberately conservative):
- Login detection: a leading sequence of `navigate -> click('CONSULTOR' or
  similar role) -> 2 type actions (one is password) -> click('Entrar') ->
  wait_for(dashboard)` adds a `login_block` step at the top of the steps
  list. The individual actions are still emitted as their own steps so the
  user can fine-tune the result in the painel.
- Consecutive `type` actions with different selectors become a single
  `fill` step with a dict payload (so P0's `fill` handler renders it).
- Each non-collapsed action becomes its own step with a stable `id`.
"""
import json
import re
from pathlib import Path
from typing import Any


class NavRecorderError(ValueError):
    """Raised when a trace file is missing, malformed, or unparseable."""


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
_STRIPPABLE_SUBDOMAINS = ("www", "app")


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


def _detect_login_block(actions: list[dict]) -> dict | None:
    """If the prefix of `actions` looks like a login flow, return a
    `login_block` dict describing it. Returns None otherwise.

    Does NOT consume actions — the caller still emits every action as its
    own step. The login_block is an annotation prepended to the steps list.

    Heuristic:
      navigate -> click(login-entry) -> [N type] (>=2, exactly one password)
                  -> click(submit) -> [wait_for]
    """
    if len(actions) < 5:
        return None, actions
    a = actions
    if a[0].get("type") != "navigate":
        return None, actions
    if a[1].get("type") != "click" or not _is_login_entry_click(a[1].get("selector", "")):
        return None, actions
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
    if i >= len(a) or a[i].get("type") != "click" or not _is_submit_click(a[i].get("selector", "")):
        return None, actions
    submit = a[i]
    i += 1
    # wait_for is optional — if present, use its selector as success_assert
    success_selector = ".dashboard"
    timeout_ms = 15000
    if i < len(a) and a[i].get("type") == "wait_for":
        success_selector = a[i].get("selector", ".dashboard")
        timeout_ms = int(a[i].get("timeout_ms", 15000))

    user_sel = next(
        (t["selector"] for t in type_block if not _is_password_input(t["selector"], t["value"])),
        None,
    )
    pass_sel = next(
        (t["selector"] for t in type_block if _is_password_input(t["selector"], t["value"])),
        None,
    )

    return {
        "type": "form_login",
        "url": a[0]["url"],
        "credentials_ref": _credentials_ref_from_url(a[0]["url"]),
        "selectors": {
            "user": user_sel or "input[type=text]",
            "pass": pass_sel or "input[type=password]",
            "submit": submit.get("selector", "button[type=submit]"),
        },
        "success_assert": {"selector": success_selector, "timeout_ms": timeout_ms},
    }, a[i:]


def _credentials_ref_from_url(url: str) -> str:
    """Extract a stable credential ref name from a URL.

    Strips common subdomain prefixes (www, app) and the TLD. For
    `https://app.apvs.vc/home` → `apvs_login`. For
    `https://www.example.com/` → `example_login`.
    """
    m = re.search(r"https?://([^/]+)", url or "")
    host = (m.group(1) if m else "default").split(":")[0]
    parts = host.split(".")
    while parts and parts[0] in _STRIPPABLE_SUBDOMAINS:
        parts.pop(0)
    if len(parts) > 1:
        parts.pop()
    name = "_".join(parts) if parts else "default"
    return f"{name}_login"


def _automation_name_from_title_or_url(payload: dict) -> str:
    title = payload.get("title") or ""
    if title:
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
        return None
    if t == "select" or t == "selectOption":
        sel = action.get("selector", "")
        return {
            "id": f"select_{_slug(sel)[:50]}_{idx:03d}",
            "click": {"selector": sel},
        }
    return None


def _group_consecutive_fills(steps: list[dict]) -> list[dict]:
    """Merge consecutive `fill` steps into one with a multi-key fill payload."""
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

# Notes that surface to the painel so the user knows what to fix in the draft.
# These are non-fatal — the recorder is best-effort; the user reviews anyway.
_DEFAULT_NOTES: list[str] = [
    "Draft output — review and edit before saving. "
    "Add `credentials_ref`, `inputs`, `outputs`, and an `inputs_schema` JSON.",
    "If a `login_block` step is present, lift it to a top-level `auth` field "
    "(the runner's auth handler reads `auth`, not a step). "
    "The `auth` runner wires in P5.",
]


def steps_from_trace(payload: dict) -> dict[str, Any]:
    actions = payload.get("actions") or []
    login_block, remaining = _detect_login_block(actions)

    steps: list[dict[str, Any]] = []
    idx = 0
    notes: list[str] = list(_DEFAULT_NOTES)
    if login_block is not None:
        steps.append({
            "id": "login_block",
            "login_block": login_block,
        })
        idx += 1
    unknown_count = 0
    for action in remaining:
        built = _build_step(action, idx)
        if built is None:
            unknown_count += 1
            continue
        steps.append(built)
        idx += 1
    if unknown_count:
        notes.append(
            f"{unknown_count} unsupported action(s) were skipped "
            f"(e.g. drag, scroll, keypress). Add them manually if needed."
        )
    steps = _group_consecutive_fills(steps)

    return {
        "automation_name": _automation_name_from_title_or_url(payload),
        "version": 1,
        "steps": steps,
        "notes": notes,
    }
