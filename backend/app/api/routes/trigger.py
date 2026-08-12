"""
Webhook trigger endpoint — allows external services (n8n, Zapier, etc.)
to trigger an automation via a simple POST request.

URL: POST /api/trigger/{automation_id}
     POST /api/trigger/{automation_id}?token=SECRET

Auth (optional): pass token as ?token= query param OR X-Token header.
If the automation has a `webhook_token` key in its credentials dict,
the provided token must match. If no webhook_token is set, the endpoint
is open (no auth required).

Body (optional JSON):
  { "variables": { "key": "value" } }
  Any top-level key that is not "variables" is also treated as a variable.
"""
from fastapi import APIRouter, HTTPException, Header, Query
from app.core.database import get_db

router = APIRouter(prefix="/trigger", tags=["trigger"])


@router.post("/{automation_id}")
async def webhook_trigger(
    automation_id: str,
    payload: dict = {},
    token: str | None = Query(default=None),
    x_token: str | None = Header(default=None),
):
    from app.workers.tasks import run_automation

    db = get_db()
    res = db.table("automations").select("*").eq("id", automation_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")

    automation = res.data[0]

    # Optional token auth
    webhook_token = (automation.get("credentials") or {}).get("webhook_token", "")
    provided_token = token or x_token or ""
    if webhook_token and provided_token != webhook_token:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    # Build variables: explicit "variables" key takes precedence, rest merged on top
    variables: dict = {}
    if isinstance(payload, dict):
        variables = {k: v for k, v in payload.items() if k != "variables"}
        variables.update(payload.get("variables") or {})

    # Pre-create execution log
    steps = automation.get("steps") or []
    log_res = db.table("execution_logs").insert({
        "automation_id": automation_id,
        "status": "queued",
        "total_steps": len(steps),
        "steps_completed": 0,
    }).execute()
    log_id = log_res.data[0]["id"]

    task = run_automation.delay(automation_id, variables, log_id)

    return {
        "task_id": task.id,
        "execution_id": log_id,
        "status": "queued",
        "automation": automation["name"],
    }
