# NavRunner P7 — Webhook Trigger Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing webhook trigger endpoint. Today it works (POST `/api/trigger/{id}` with optional token), but it has gaps: no tests, no input validation, no HMAC signature support, no tracking metadata. This plan fills those gaps so the endpoint is production-ready for the "CNPJ arrives via webhook" use case.

**Architecture:** Extend the existing `app/api/routes/trigger.py`. Add HMAC verification (optional, alongside the existing simple-token). Add structured response (`execution_id`, `automation_name`, `dispatched_at`). Add input validation (missing variables → 400 with the list of expected names). Add tests. No frontend changes.

**Tech Stack:** Python 3.11, FastAPI, supabase-py, hmac (stdlib).

**Spec reference:** `docs/superpowers/specs/2026-08-12-navrunner-framework-design.md` — section "P7: Webhook trigger".

**Predecessor plans:** P0–P3 + P5 + P6 + P9 merged.

---

## File Structure

### Files created (P7)

```
backend/tests/automation/
└── test_webhook_trigger.py
```

### Files modified (P7)

- `backend/app/api/routes/trigger.py` — add HMAC, structured response, input validation, error logging
- `backend/app/automation/README.md` — document P7

### Anti-pattern check

- HMAC verification is additive — if no `webhook_secret` in credentials, skip HMAC check (backward compat).
- Input validation fails fast (400) before dispatching the Celery task — no zombie runs.
- All errors logged (so the user can debug failed webhooks).

---

## Conventions

- TDD: failing test → impl → passing → commit.
- `_run` helper in tests, no `pytest-asyncio`.
- Commit messages: `feat(navrunner): P7 task N — <title>` etc.

---

## Task 1: HMAC signature verification + structured response + validation

**Files:**
- Modify: `backend/app/api/routes/trigger.py`
- Create: `backend/tests/automation/test_webhook_trigger.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/automation/test_webhook_trigger.py` with EXACTLY:

```python
import hmac
import hashlib
import json
from unittest.mock import MagicMock, patch

import os
import pytest


def _fake_automation_row(automation_id="auto-1", name="X", credentials=None, steps=None):
    return {
        "id": automation_id,
        "name": name,
        "credentials": credentials or {},
        "steps": steps or [{"id": "use_var", "fill": {"#x": "{{input.cnpj}}"}}],
    }


def test_webhook_returns_execution_id(monkeypatch):
    """A webhook call returns {execution_id, task_id, automation_name, status}."""
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row()]
    )
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "exec-123"}])
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    fake_delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr("app.workers.tasks.run_automation", MagicMock(delay=fake_delay))

    resp = client.post("/api/trigger/auto-1", json={"variables": {"cnpj": "123"}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["execution_id"] == "exec-123"
    assert body["automation_name"] == "X"
    assert body["status"] == "queued"


def test_webhook_validates_required_variables(monkeypatch):
    """If the payload is missing variables the steps need, return 400 with the list."""
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row(steps=[
            {"id": "fill_cnpj", "fill": {"#cnpj": "{{input.cnpj}}"}},
            {"id": "fill_doc",  "fill": {"#doc":  "{{input.doc}}"}},
        ])]
    )
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    resp = client.post("/api/trigger/auto-1", json={"variables": {"cnpj": "123"}})  # missing doc
    assert resp.status_code == 400
    assert "doc" in resp.text


def test_webhook_token_auth(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row(credentials={"webhook_token": "secret-abc"})]
    )
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    # No token → 401
    resp = client.post("/api/trigger/auto-1", json={})
    assert resp.status_code == 401

    # Wrong token → 401
    resp = client.post("/api/trigger/auto-1?token=wrong", json={})
    assert resp.status_code == 401


def test_webhook_hmac_signature(monkeypatch):
    """If `webhook_secret` is set, verify X-Signature header matches HMAC-SHA256 of body."""
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row(credentials={"webhook_secret": "shhh"})]
    )
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "exec-h"}])
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.run_automation", MagicMock(delay=MagicMock(return_value=MagicMock(id="t"))))

    body = {"variables": {"cnpj": "123"}}
    raw = json.dumps(body).encode()
    sig = hmac.new(b"shhh", raw, hashlib.sha256).hexdigest()

    # Bad signature → 401
    resp = client.post("/api/trigger/auto-1", json=body, headers={"X-Signature": "deadbeef"})
    assert resp.status_code == 401

    # Good signature → 200
    resp = client.post("/api/trigger/auto-1", json=body, headers={"X-Signature": sig})
    assert resp.status_code == 200


def test_webhook_returns_404_for_missing_automation(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    resp = client.post("/api/trigger/missing-id", json={})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p7/backend && python3 -m pytest tests/automation/test_webhook_trigger.py -v
```

Expected: tests fail (validation/HMAC/structured response not implemented).

- [ ] **Step 3: Update `trigger.py`**

Replace `backend/app/api/routes/trigger.py`:

```python
"""
Webhook trigger endpoint — allows external services (n8n, Zapier, etc.)
to trigger an automation via a simple POST request.

URL: POST /api/trigger/{automation_id}
      POST /api/trigger/{automation_id}?token=SECRET
      POST /api/trigger/{automation_id} (with X-Signature header for HMAC)

Auth (optional, in priority order):
  1. HMAC-SHA256 — if `webhook_secret` is set in credentials, body must
     match `X-Signature: sha256=<hex>` (header value is the hex digest).
  2. Simple token — pass `?token=SECRET` or `X-Token: SECRET`; must match
     `credentials.webhook_token` if it's set.

Body (JSON):
  {"variables": {"key": "value"}, ...}
  Any top-level key other than "variables" is also treated as a variable.
  Missing required variables → 400 with the list of expected names.
"""
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header, Query, Request

from app.core.database import get_db


log = logging.getLogger(__name__)
router = APIRouter(prefix="/trigger", tags=["trigger"])


def _extract_required_variables(steps: list) -> set[str]:
    """Walk the steps tree and pull out every `{{input.X}}` reference."""
    text = json.dumps(steps, ensure_ascii=False)
    return set(re.findall(r"\{\{\s*input\.([\w.]+)\s*\}\}", text))


@router.post("/{automation_id}")
async def webhook_trigger(
    automation_id: str,
    request: Request,
    token: str | None = Query(default=None),
    x_token: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
):
    from app.workers.tasks import run_automation

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    db = get_db()
    res = db.table("automations").select("*").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")

    automation = res.data[0]
    credentials = automation.get("credentials") or {}

    # ── Auth ───────────────────────────────────────────────────────────
    secret = credentials.get("webhook_secret", "")
    simple_token = credentials.get("webhook_token", "")

    if secret:
        if not x_signature:
            raise HTTPException(status_code=401, detail="X-Signature header required")
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        # Accept either bare hex or `sha256=<hex>`.
        provided = x_signature.removeprefix("sha256=").strip()
        if not hmac.compare_digest(expected, provided):
            raise HTTPException(status_code=401, detail="Invalid X-Signature")
    elif simple_token:
        provided = token or x_token or ""
        if provided != simple_token:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

    # ── Variable validation ───────────────────────────────────────────
    variables: dict = {}
    variables.update({k: v for k, v in payload.items() if k != "variables"})
    variables.update(payload.get("variables") or {})

    required = _extract_required_variables(automation.get("steps") or [])
    provided_basenames = {v.split(".")[0] for v in variables.keys()}
    missing = sorted(v for v in required if v.split(".")[0] not in provided_basenames)
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"missing_variables": missing, "hint": "Pass each via body or {variables: {...}}"},
        )

    # ── Dispatch ──────────────────────────────────────────────────────
    steps = automation.get("steps") or []
    try:
        log_res = db.table("execution_logs").insert({
            "automation_id": automation_id,
            "status": "queued",
            "total_steps": len(steps),
            "steps_completed": 0,
        }).execute()
        log_id = log_res.data[0]["id"]
    except Exception as e:
        log.exception("webhook: failed to create execution_log")
        raise HTTPException(status_code=500, detail=f"failed to create execution_log: {e}") from e

    try:
        task = run_automation.delay(automation_id, variables, log_id)
    except Exception as e:
        log.exception("webhook: failed to dispatch celery task")
        raise HTTPException(status_code=500, detail=f"failed to dispatch: {e}") from e

    return {
        "execution_id": log_id,
        "task_id": task.id,
        "automation_name": automation.get("name", ""),
        "status": "queued",
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
        "variables_received": list(variables.keys()),
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p7/backend && python3 -m pytest tests/automation/test_webhook_trigger.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Re-run full suite**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p7/backend && python3 -m pytest tests/automation -q 2>&1 | tail -3
```

Expected: 172 + 5 = 177 passed (no regressions).

- [ ] **Step 6: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p7
git add backend/app/api/routes/trigger.py backend/tests/automation/test_webhook_trigger.py
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P7 task 1 — webhook trigger HMAC + validation + structured response"
```

## Report

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- **Test results:** (paste last 5 lines)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p7 rev-parse HEAD`
- **Self-review findings**
- **Concerns** if any

---

## Task 2: README + final verification

- [ ] **Step 1: Update README**

In `backend/app/automation/README.md`, find the "Status: P9" header. Change to:

```markdown
## Status: P7 (webhook trigger hardened + single-pane authoring + AI Planner + auth + sandbox + concurrency)
```

Then find the "### Implemented (P0 + ..." section. Add:

```markdown
- **Webhook trigger hardened (P7)** — `POST /api/trigger/{id}` accepts variables, validates required inputs against `steps` JSON, supports HMAC-SHA256 (via `webhook_secret` + `X-Signature` header) or simple token. Returns `execution_id`, `task_id`, `automation_name`, `dispatched_at`, `variables_received`.
```

- [ ] **Step 2: Final verification**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p7/backend && python3 -m pytest tests/automation -q 2>&1 | tail -3
```

Expected: 177 passed.

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p7
git add backend/app/automation/README.md
git -c user.email=navrunner@local -c user.name=navrunner commit -m "docs(navrunner): P7 README — webhook trigger hardened confirmed"
```

## Report

- **Status:** DONE
- **Test results:** (paste last 3 lines)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p7 rev-parse HEAD`

---

## Self-Review (post-write)

**1. Spec coverage**

| Spec section | P7 coverage |
|---|---|
| Webhook trigger endpoint | Already existed (P0/P5 era) — P7 hardens it |
| Token auth | Preserved (backward-compat) |
| HMAC signature | Added (Task 1) |
| Variable validation | Added (Task 1) |
| Structured response | Added (Task 1) |

**2. Placeholder scan**

Searched for `TBD`/`TODO`. Zero in code.

**3. Type consistency**

- All types match the FastAPI handler conventions (str, int, dict).
- HMAC comparison uses `hmac.compare_digest` (constant-time).

**4. Concerns**

- **`run_automation` vs `run_automation_v2`:** the existing endpoint dispatches the legacy `run_automation`, not `run_automation_v2`. P9 already migrated the dispatcher. For full consistency, this should also call `run_automation_v2`. Out of scope for P7 (don't break the working integration); flagged for follow-up.
- **Schema check is exact-match on `input.X`** — won't catch `input.nested.path`. Good enough for MVP; P5+ can add `.` resolution if needed.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-navrunner-p7-webhook-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one Opus subagent.

**2. Inline Execution** — Execute in this session.

Which approach?
