from uuid import UUID

from pydantic import BaseModel


class CreateExecutionJob(BaseModel):
    automation_id: UUID
    trigger_type: str
    mode: str
    payload: dict


class CreateRecordingSession(BaseModel):
    automation_id: UUID | None = None
