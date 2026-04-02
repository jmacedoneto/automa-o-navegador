from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.schemas import ExecuteRequest, ExecutionLogResponse
from app.core.database import get_db
from app.workers.tasks import run_automation
from apps.api.app.services.job_service import create_job_payload

router = APIRouter(prefix="/executions", tags=["executions"])


@router.post("/automations/{automation_id}/execute", status_code=202)
async def execute(automation_id: str, payload: ExecuteRequest):
    """Queue automation for async execution via Celery."""
    db = get_db()
    res = db.table("automations").select("id,steps").eq("id", automation_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")

    # Pre-create execution log so the frontend can subscribe to real-time updates
    steps = res.data.get("steps") or []
    log_res = db.table("execution_logs").insert({
        "automation_id": automation_id,
        "status": "queued",
        "total_steps": len(steps),
        "steps_completed": 0,
    }).execute()
    log_id = log_res.data[0]["id"]

    queue_payload = create_job_payload(
        automation_id=automation_id,
        trigger_type="manual",
        mode="hibrido",
        incoming_payload=payload.variables,
    )
    db.table("execution_jobs").insert(queue_payload).execute()

    task = run_automation.delay(queue_payload["automation_id"], queue_payload["payload"], log_id)
    return {"task_id": task.id, "status": queue_payload["status"], "execution_id": log_id}


@router.get("", response_model=list[ExecutionLogResponse])
async def list_executions(automation_id: str | None = None, limit: int = 50):
    db = get_db()
    query = db.table("execution_logs").select("*").order("started_at", desc=True).limit(limit)
    if automation_id:
        query = query.eq("automation_id", automation_id)
    res = query.execute()
    return res.data or []


@router.delete("/pending")
async def delete_pending_executions():
    """Delete all executions stuck in 'running' or 'queued' status."""
    db = get_db()
    res = db.table("execution_logs").delete().in_("status", ["running", "queued"]).execute()
    return {"deleted": len(res.data or [])}


@router.delete("/{log_id}")
async def delete_execution(log_id: str):
    """Delete a specific execution log."""
    db = get_db()
    res = db.table("execution_logs").delete().eq("id", log_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"deleted": True}


@router.get("/{log_id}", response_model=ExecutionLogResponse)
async def get_execution(log_id: str):
    db = get_db()
    res = db.table("execution_logs").select("*").eq("id", log_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Execution log not found")
    return res.data
