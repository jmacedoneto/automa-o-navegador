from fastapi import APIRouter, status

from apps.api.app.models.execution import CreateRecordingSession

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_recording_session(payload: CreateRecordingSession):
    return {
        "id": "rec-local-1",
        "automation_id": payload.automation_id,
        "status": "pending",
    }
