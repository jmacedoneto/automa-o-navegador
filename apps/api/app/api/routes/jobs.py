from uuid import uuid4

from fastapi import APIRouter, Response, status

from apps.api.app.models.execution import CreateExecutionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateExecutionJob):
    return {
        "id": str(uuid4()),
        "automation_id": str(payload.automation_id),
        "status": "queued",
    }


@router.get("/next")
def poll_next_job(response: Response):
    # Placeholder: in production this queries execution_jobs WHERE status='queued' ORDER BY created_at LIMIT 1
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.post("/{job_id}/ack")
def ack_job(job_id: str):
    # Placeholder: in production this sets status='running' on the job
    return {"id": job_id, "status": "running"}
