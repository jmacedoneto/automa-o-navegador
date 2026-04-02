from uuid import uuid4

from fastapi import APIRouter, status

from apps.api.app.models.execution import CreateRecordingSession

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_recording_session(payload: CreateRecordingSession):
    return {
        "id": str(uuid4()),
        "automation_id": str(payload.automation_id) if payload.automation_id else None,
        "status": "pending",
    }
