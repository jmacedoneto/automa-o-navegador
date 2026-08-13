"""MCP tool implementations — thin wrappers around the existing db / dispatcher.

Each tool is async (FastMCP requirement). They delegate to:
- `get_db()` for Supabase reads
- `run_automation_v2.delay()` for firing runs
- `plan_automation()` for AI Planner
- `run_automation` for the webhook path

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
