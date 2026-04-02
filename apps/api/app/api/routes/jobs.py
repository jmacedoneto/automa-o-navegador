from fastapi import APIRouter, status

from apps.api.app.models.execution import CreateExecutionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateExecutionJob):
    return {
        "id": "job-local-1",
        "automation_id": payload.automation_id,
        "status": "queued",
    }
