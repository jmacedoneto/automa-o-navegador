from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_db():
    from app.core.database import get_db
    return get_db()


class UpdateRunStatus(BaseModel):
    status: str
    steps_completed: int = 0
    total_steps: int = 0
    error_message: str = ""
    extracted_data: dict | None = None


@router.get("/{run_id}")
def get_run(run_id: UUID):
    try:
        db = _get_db()
        res = db.table("execution_runs").select("*").eq("id", str(run_id)).maybe_single().execute()
        if res.data:
            return res.data
    except Exception:
        pass
    raise HTTPException(
        status_code=404,
        detail=f"Run {run_id} not found in placeholder orchestrator state",
    )


@router.patch("/{run_id}")
def update_run(run_id: str, payload: UpdateRunStatus):
    update: dict = {
        "status": payload.status,
        "steps_completed": payload.steps_completed,
        "total_steps": payload.total_steps,
    }
    if payload.error_message:
        update["error_message"] = payload.error_message
    if payload.extracted_data:
        update["extracted_data"] = payload.extracted_data
    if payload.status in ("success", "failed"):
        update["finished_at"] = datetime.now(timezone.utc).isoformat()

    try:
        db = _get_db()
        db.table("execution_runs").update(update).eq("id", run_id).execute()

        # Also update the execution_logs entry if it exists (for frontend compatibility)
        run_res = db.table("execution_runs").select("job_id").eq("id", run_id).maybe_single().execute()
        if run_res.data:
            job_id = run_res.data["job_id"]
            job_res = db.table("execution_jobs").select("automation_id").eq("id", job_id).maybe_single().execute()
            if job_res.data:
                automation_id = job_res.data["automation_id"]
                # Update execution_logs
                log_update = {
                    "status": payload.status,
                    "steps_completed": payload.steps_completed,
                }
                if payload.status in ("success", "failed"):
                    log_update["finished_at"] = datetime.now(timezone.utc).isoformat()
                if payload.error_message:
                    log_update["error_message"] = payload.error_message
                if payload.extracted_data:
                    log_update["extracted_data"] = payload.extracted_data
                db.table("execution_logs").update(log_update).eq("automation_id", automation_id).eq("status", "running").execute()

                # Update automation last status
                if payload.status in ("success", "failed"):
                    db.table("automations").update({
                        "last_execution_at": datetime.now(timezone.utc).isoformat(),
                        "last_execution_status": payload.status,
                    }).eq("id", automation_id).execute()

                    # Mark job as done
                    db.table("execution_jobs").update({"status": payload.status}).eq("id", job_id).execute()
    except Exception:
        pass

    return {"id": run_id, "status": payload.status}
