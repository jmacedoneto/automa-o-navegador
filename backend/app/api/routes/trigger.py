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
