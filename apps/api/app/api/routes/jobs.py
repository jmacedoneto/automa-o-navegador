from uuid import uuid4

from fastapi import APIRouter, Response, status

from apps.api.app.models.execution import CreateExecutionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_db():
    from app.core.database import get_db
    return get_db()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateExecutionJob):
    return {
        "id": str(uuid4()),
        "automation_id": str(payload.automation_id),
        "status": "queued",
    }


@router.get("/next")
def poll_next_job(response: Response):
    try:
        db = _get_db()
        res = (
            db.table("execution_jobs")
            .select("*, automations(steps, credentials, erp_url, name)")
            .eq("status", "queued")
            .order("created_at")
            .limit(1)
            .execute()
        )
        if not res.data:
            response.status_code = status.HTTP_204_NO_CONTENT
            return None

        job = res.data[0]
        automation = job.pop("automations", {}) or {}
        steps = automation.get("steps") or []
        credentials = automation.get("credentials") or {}
        erp_url = (automation.get("erp_url") or "").strip()

        # Auto-prepend navigate step if erp_url set but no navigate step exists
        has_navigate = any(
            (s.get("action") == "navigate" or s.get("type") == "navigate")
            and (s.get("url") or s.get("value"))
            for s in steps
        )
        if erp_url and not has_navigate:
            steps = [{"action": "navigate", "url": erp_url, "waitTime": 1000}] + steps

        # Find associated run
        run_res = (
            db.table("execution_runs")
            .select("id")
            .eq("job_id", job["id"])
            .eq("status", "queued")
            .limit(1)
            .execute()
        )
        run_id = run_res.data[0]["id"] if run_res.data else None

        return {
            "id": job["id"],
            "automation_id": job["automation_id"],
            "trigger_type": job.get("trigger_type", "manual"),
            "mode": job.get("mode", "gravado"),
            "payload": job.get("payload", {}),
            "steps": steps,
            "variables": {**credentials, **job.get("payload", {})},
            "run_id": run_id,
        }
    except Exception:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None


@router.post("/{job_id}/ack")
def ack_job(job_id: str):
    try:
        db = _get_db()
        db.table("execution_jobs").update({"status": "running"}).eq("id", job_id).execute()
    except Exception:
        pass
    return {"id": job_id, "status": "running"}
