from fastapi import APIRouter, HTTPException
from app.models.schemas import ExecuteRequest, ExecutionLogResponse
from app.core.database import get_db
from app.workers.tasks import run_automation

router = APIRouter(prefix="/executions", tags=["executions"])


def _create_job_payload(automation_id: str, trigger_type: str, mode: str, incoming_payload: dict) -> dict:
    return {
        "automation_id": automation_id,
        "trigger_type": trigger_type,
        "mode": mode,
        "payload": incoming_payload,
        "status": "queued",
    }


@router.post("/automations/{automation_id}/execute", status_code=202)
async def execute(automation_id: str, payload: ExecuteRequest):
    """Create a job+run in the database. The runtime local agent picks it up."""
    db = get_db()
    res = db.table("automations").select("id,steps").eq("id", automation_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Automation not found")

    steps = res.data.get("steps") or []

    # Create execution log (frontend listens to this)
    log_res = db.table("execution_logs").insert({
        "automation_id": automation_id,
        "status": "queued",
        "total_steps": len(steps),
        "steps_completed": 0,
    }).execute()
    log_id = log_res.data[0]["id"]

    # Create job for the runtime to pick up
    queue_payload = _create_job_payload(
        automation_id=automation_id,
        trigger_type="manual",
        mode="hibrido",
        incoming_payload=payload.variables,
    )
    job_res = db.table("execution_jobs").insert(queue_payload).execute()
    job_id = job_res.data[0]["id"]

    # Create run linked to the job
    run_res = db.table("execution_runs").insert({
        "job_id": job_id,
        "status": "queued",
        "total_steps": len(steps),
    }).execute()
    run_id = run_res.data[0]["id"]

    # Dispatch Celery task
    run_automation.apply_async(
        args=[automation_id],
        kwargs={
            "variables": payload.variables or {},
            "log_id": log_id,
            "job_id": job_id,
            "run_id": run_id,
        },
    )

    return {
        "status": "queued",
        "execution_id": log_id,
        "job_id": job_id,
        "run_id": run_id,
    }


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


@router.post("/{log_id}/cancel")
async def cancel_execution(log_id: str):
    """Signal a running execution to stop."""
    from datetime import datetime, timezone
    db = get_db()
    res = db.table("execution_logs").select("status").eq("id", log_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Execution not found")
    if res.data["status"] not in ("running", "pending"):
        return {"ok": False, "message": "Execução não está ativa"}
    db.table("execution_logs").update({
        "status": "cancelled",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "error_message": "Cancelado pelo usuário",
    }).eq("id", log_id).execute()
    return {"ok": True}
