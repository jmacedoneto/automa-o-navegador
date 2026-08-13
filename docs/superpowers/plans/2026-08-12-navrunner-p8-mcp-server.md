# NavRunner P8 — MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the NavRunner as a Model Context Protocol (MCP) server so any MCP client (Claude Desktop, Cursor, Cline, OpenCode) can list / create / run automations via natural language. Today the framework is only reachable through the FastAPI HTTP endpoints; P8 makes it reachable through the standard MCP tool protocol.

**Architecture:** New `app/mcp_server.py` module that wraps the existing routes / services as MCP tools. The server uses the official `mcp` Python SDK (`FastMCP`) and runs over stdio (the most common transport — Claude Desktop launches it as a subprocess). All tools are read-only against the DB except `run_automation` / `create_automation` / `trigger_webhook` — those reuse the existing dispatcher / endpoints.

**Tech Stack:** Python 3.11, `mcp` SDK (2.0.0), FastMCP (high-level), stdio transport. No frontend changes.

**Spec reference:** `docs/superpowers/specs/2026-08-12-navrunner-framework-design.md` — section "P8: MCP server".

**Predecessor plans:** P0–P3 + P5 + P6 + P9 + P7 merged.

---

## File Structure

### Files created (P8)

```
backend/app/mcp_server/
├── __init__.py
├── server.py              # FastMCP server definition
├── tools.py               # All MCP tool functions (list, create, run, plan, etc.)
└── tests.py               # In-process test client

backend/tests/
└── test_mcp_server.py

backend/scripts/
└── mcp_server_stdio.py    # Entry point: `python -m backend.scripts.mcp_server_stdio`

backend/mcp_manifest.json  # Tool schema for tool registry (informational)
```

### Files modified (P8)

- `backend/requirements.txt` — add `mcp==2.0.0`
- `backend/app/automation/README.md` — P8 confirmed

### Anti-pattern check

- `tools.py` is a thin wrapper: each tool is a 5–10 line function calling existing FastAPI / Celery / Supabase code. No business logic is duplicated.
- MCP server lives in its own module (`app/mcp_server/`) — no pollution of `app/automation/`.
- Stdio transport is the simplest; HTTP transport (SSE) can be added later in P8.1 if needed.

---

## Conventions

- TDD: failing test → impl → passing → commit.
- `_run` helper in tests, no `pytest-asyncio`.
- Commit messages: `feat(navrunner): P8 task N — <title>` etc.

---

## Task 1: MCP server scaffold + list/get tools

**Files:**
- Create: `backend/app/mcp_server/__init__.py`
- Create: `backend/app/mcp_server/tools.py`
- Create: `backend/app/mcp_server/server.py`
- Create: `backend/scripts/mcp_server_stdio.py`
- Modify: `backend/requirements.txt` (add `mcp==2.0.0`)

- [ ] **Step 1: Add `mcp` to requirements**

Append `mcp==2.0.0` to `backend/requirements.txt`.

- [ ] **Step 2: Install mcp in the worktree**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p8/backend && pip install -q mcp==2.0.0
```

- [ ] **Step 3: Write the failing test**

Create `backend/tests/test_mcp_server.py` with EXACTLY:

```python
import asyncio
import json
from unittest.mock import MagicMock, patch

from app.mcp_server.tools import (
    list_automations,
    get_automation,
    list_runs,
    get_run_status,
    plan_automation,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_list_automations_returns_summary():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
        {"id": "a-1", "name": "Cotação FIPE", "is_active": True},
        {"id": "a-2", "name": "Préboleto Mensal", "is_active": False},
    ])
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(list_automations())
    assert len(out) == 2
    assert out[0]["id"] == "a-1"
    assert out[0]["name"] == "Cotação FIPE"
    assert out[1]["is_active"] is False


def test_get_automation_returns_full_record():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "a-1", "name": "X", "steps": [{"id": "y"}], "auth": {"type": "form_login"}}]
    )
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(get_automation("a-1"))
    assert out["id"] == "a-1"
    assert out["steps"] == [{"id": "y"}]
    assert out["auth"]["type"] == "form_login"


def test_get_automation_returns_none_for_missing():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(get_automation("missing"))
    assert out is None


def test_list_runs_returns_recent():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[
        {"id": "run-1", "automation_id": "a-1", "status": "success", "started_at": "2026-08-12T00:00:00Z"},
    ])
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(list_runs(limit=10))
    assert len(out) == 1
    assert out[0]["status"] == "success"


def test_get_run_status_returns_full_record():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "run-1", "status": "failed", "error_message": "boom"}]
    )
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(get_run_status("run-1"))
    assert out["status"] == "failed"
    assert out["error_message"] == "boom"


def test_plan_automation_returns_draft():
    fake_draft = {
        "automation_name": "ping",
        "version": 1,
        "steps": [{"id": "x", "goto": "https://x"}],
        "notes": [],
    }
    async def fake_plan(description, site_url, auth_hint="", model=None):
        return fake_draft
    with patch("app.mcp_server.tools.plan_automation", side_effect=fake_plan):
        out = _run(plan_automation(description="do a thing", site_url="https://x"))
    assert out["automation_name"] == "ping"
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p8/backend && python3 -m pytest tests/test_mcp_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.mcp_server'`

- [ ] **Step 5: Create `app/mcp_server/tools.py`**

`backend/app/mcp_server/tools.py`:

```python
"""MCP tool implementations — thin wrappers around the existing db / dispatcher.

Each tool is async (FastMCP requirement). They delegate to:
- `get_db()` for Supabase reads
- `run_automation_v2.delay()` for firing runs
- `plan_automation()` for AI Planner
- `webhook_trigger()` for the webhook path

Nothing here is new business logic — it's the bridge layer.
"""
from typing import Any

from app.core.database import get_db


# ── Read-only tools ──────────────────────────────────────────────────

async def list_automations() -> list[dict[str, Any]]:
    db = get_db()
    res = db.table("automations").select("id,name,description,is_active,created_at").order("created_at", desc=True).execute()
    return res.data or []


async def get_automation(automation_id: str) -> dict[str, Any] | None:
    db = get_db()
    res = db.table("automations").select("*").eq("id", automation_id).limit(1).execute()
    if not res.data:
        return None
    return res.data[0]


async def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    db = get_db()
    res = db.table("automation_runs").select("*").order("started_at", desc=True).limit(limit).execute()
    return res.data or []


async def get_run_status(run_id: str) -> dict[str, Any] | None:
    db = get_db()
    res = db.table("automation_runs").select("*").eq("id", run_id).limit(1).execute()
    if not res.data:
        return None
    return res.data[0]


# ── Mutation tools (dispatch) ────────────────────────────────────────

async def run_automation_now(
    automation_id: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch `run_automation_v2` for the given automation. Returns task_id."""
    from app.workers.tasks import run_automation_v2
    from app.automation.credentials import resolve_credentials

    db = get_db()
    res = db.table("automations").select("id,steps").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise ValueError(f"automation {automation_id} not found")

    steps_payload = res.data[0].get("steps") or []
    credentials = resolve_credentials()
    task = run_automation_v2.delay(
        automation_name=automation_id,
        steps_payload=steps_payload,
        inputs=variables or {},
    )
    return {"task_id": task.id, "automation_id": automation_id, "status": "queued"}


async def create_automation(
    name: str,
    steps: list[dict[str, Any]],
    description: str = "",
    auth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a new automation. `auth` is JSON-stored; the runner reads it from steps[0]."""
    db = get_db()
    body_steps = list(steps)
    if auth:
        body_steps = [{"id": "auth", "auth": auth}] + body_steps
    row = {
        "name": name,
        "description": description,
        "erp_url": "",
        "instructions": "",
        "steps": body_steps,
        "credentials": {},
        "outputs": [],
        "is_active": False,
    }
    res = db.table("automations").insert(row).execute()
    return res.data[0]


async def plan_automation(
    description: str,
    site_url: str = "",
    auth_hint: str = "",
) -> dict[str, Any]:
    """Ask GPT to produce a NavRunner DSL draft from a natural-language description."""
    from app.automation.planner import plan_automation as _plan
    return await _plan(description=description, site_url=site_url, auth_hint=auth_hint)


async def trigger_webhook(
    automation_id: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch the legacy webhook path (calls into the hardened webhook endpoint)."""
    from app.workers.tasks import run_automation
    db = get_db()
    res = db.table("automations").select("id,steps").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise ValueError(f"automation {automation_id} not found")
    log_res = db.table("execution_logs").insert({
        "automation_id": automation_id,
        "status": "queued",
        "total_steps": len(res.data[0].get("steps") or []),
        "steps_completed": 0,
    }).execute()
    log_id = log_res.data[0]["id"]
    task = run_automation.delay(automation_id, variables or {}, log_id)
    return {"execution_id": log_id, "task_id": task.id, "status": "queued"}
```

- [ ] **Step 6: Create `app/mcp_server/server.py`**

`backend/app/mcp_server/server.py`:

```python
"""MCP server factory — wraps the tools as an MCP server.

Uses FastMCP (the high-level mcp SDK).
"""
from app.mcp_server.tools import (
    create_automation,
    get_automation,
    get_run_status,
    list_automations,
    list_runs,
    plan_automation,
    run_automation_now,
    trigger_webhook,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore[assignment]


def build_server() -> "FastMCP":
    if FastMCP is None:
        raise RuntimeError("mcp package not installed — run `pip install mcp==2.0.0`")
    mcp = FastMCP("navrunner")

    mcp.add_tool(
        list_automations,
        name="list_automations",
        description="List all automations registered in NavRunner. Returns id, name, description, is_active, created_at.",
    )
    mcp.add_tool(
        get_automation,
        name="get_automation",
        description="Fetch a single automation by id, including its steps and auth block.",
    )
    mcp.add_tool(
        list_runs,
        name="list_runs",
        description="List recent automation runs (most recent first).",
    )
    mcp.add_tool(
        get_run_status,
        name="get_run_status",
        description="Fetch a single run by id, including status, error_message, screenshot_urls, bindings.",
    )
    mcp.add_tool(
        run_automation_now,
        name="run_automation_now",
        description="Dispatch an automation immediately (Celery task). Returns task_id.",
    )
    mcp.add_tool(
        create_automation,
        name="create_automation",
        description="Persist a new automation with name + steps array. `auth` is a sibling dict (not a step).",
    )
    mcp.add_tool(
        plan_automation,
        name="plan_automation",
        description="Ask GPT to convert a natural-language description into a NavRunner DSL draft.",
    )
    mcp.add_tool(
        trigger_webhook,
        name="trigger_webhook",
        description="Trigger the legacy webhook path. Returns execution_id and task_id.",
    )

    return mcp
```

- [ ] **Step 7: Create `app/mcp_server/__init__.py`**

`backend/app/mcp_server/__init__.py`:

```python
"""MCP server wrapper for the NavRunner framework.

Exposes NavRunner as Model Context Protocol tools so any MCP client
(Claude Desktop, Cursor, OpenCode, etc.) can list/create/run automations.
"""
from app.mcp_server.server import build_server

__all__ = ["build_server"]
```

- [ ] **Step 8: Create the stdio entry point**

`backend/scripts/mcp_server_stdio.py`:

```python
"""Stdin/stdout entry point for the NavRunner MCP server.

Run it via:
    python -m backend.scripts.mcp_server_stdio

Or in a Claude Desktop config:
    {
      "mcpServers": {
        "navrunner": {
          "command": "python",
          "args": ["-m", "backend.scripts.mcp_server_stdio"],
          "cwd": "/root/navegador/automa-o-navegador/backend"
        }
      }
    }
"""
from app.mcp_server import build_server


def main() -> None:
    server = build_server()
    # stdio transport — the default for FastMCP().run() with no args.
    server.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Modify `__init__.py` to be a package**

Create `backend/app/mcp_server/__init__.py` (already done in step 7).

- [ ] **Step 10: Run test to verify it passes**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p8/backend && python3 -m pytest tests/test_mcp_server.py -v
```

Expected: 6 passed.

- [ ] **Step 11: Verify the server starts (manual smoke)**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p8/backend && timeout 3 python -m backend.scripts.mcp_server_stdio 2>&1 | head -20
```

Expected: server starts, prints the tool list, then exits on timeout (stdio JSON-RPC). If it exits with `ImportError: mcp`, install `mcp==2.0.0` first.

- [ ] **Step 12: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p8
git add backend/app/mcp_server/ backend/scripts/ backend/tests/test_mcp_server.py backend/requirements.txt
git -c user.email=navrunner@local -c user.name=navrunner commit -m "feat(navrunner): P8 task 1 — MCP server scaffold + 8 tools"
```

## Report

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- **Test results:** (paste last 5 lines)
- **Manual smoke output:** (paste first 10 lines of the stdio server's output)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p8 rev-parse HEAD`
- **Self-review findings**
- **Concerns** if any

---

## Task 2: README + final verification

- [ ] **Step 1: Update README**

In `backend/app/automation/README.md`, find the "Status: P7" header. Replace with:

```markdown
## Status: P8 (MCP server + webhook trigger hardened + single-pane authoring + AI Planner + auth + sandbox + concurrency)
```

Append a new bullet:

```markdown
- **MCP server (P8)** — Run as `python -m backend.scripts.mcp_server_stdio`. Exposes 8 tools: `list_automations`, `get_automation`, `list_runs`, `get_run_status`, `run_automation_now`, `create_automation`, `plan_automation`, `trigger_webhook`. Use from Claude Desktop / Cursor / any MCP client.
```

- [ ] **Step 2: Final verification**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p8/backend && python3 -m pytest tests/automation tests -q 2>&1 | tail -3
```

Expected: 177 + 6 = 183 passed (no regressions).

- [ ] **Step 3: Commit**

```bash
cd /root/navegador/automa-o-navegador/.worktrees/navrunner-p8
git add backend/app/automation/README.md
git -c user.email=navrunner@local -c user.name=navrunner commit -m "docs(navrunner): P8 README — MCP server confirmed"
```

## Report

- **Status:** DONE
- **Test results:** (paste last 3 lines)
- **Commit SHA:** `git -C /root/navegador/automa-o-navegador/.worktrees/navrunner-p8 rev-parse HEAD`

---

## Self-Review (post-write)

**1. Spec coverage**

| Spec section | P8 coverage |
|---|---|
| MCP server wraps framework | Done |
| list / get / create / run tools | Done |
| Stdio transport | Done (HTTP transport — follow-up if needed) |
| Plan automation via GPT | Done (`plan_automation` tool) |
| Webhook trigger | Done (`trigger_webhook` tool) |

**2. Placeholder scan**

Searched for `TBD`/`TODO`. Zero in code.

**3. Type consistency**

- All tools return `dict[str, Any] | list[dict[str, Any]]` — MCP-friendly.
- FastMCP handles schema generation from the function signatures.

**4. Concerns**

- **No SSE/HTTP transport** — only stdio. Claude Desktop uses stdio; if you want a remote MCP server, add `mcp.run(transport="sse")` later.
- **No auth on the MCP server** — anyone who can spawn the process can use the tools. Adequate for a local dev tool; if you expose it remotely, wrap with token auth like the webhook.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-navrunner-p8-mcp-server.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch one Opus subagent.

**2. Inline Execution** — Execute in this session.

Which approach?
