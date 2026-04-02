from uuid import uuid4

from fastapi import APIRouter, status

from apps.api.app.models.execution import CreateExecutionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateExecutionJob):
    return {
        "id": str(uuid4()),
        "automation_id": str(payload.automation_id),
        "status": "queued",
    }
