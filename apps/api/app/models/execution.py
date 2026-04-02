from pydantic import BaseModel


class CreateExecutionJob(BaseModel):
    automation_id: str
    trigger_type: str
    mode: str
    payload: dict


class CreateRecordingSession(BaseModel):
    automation_id: str | None = None
