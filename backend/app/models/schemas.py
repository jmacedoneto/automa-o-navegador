from pydantic import BaseModel
from typing import Any
from app.core.model_config import DEFAULT_OPENAI_MODEL


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsPayload(BaseModel):
    # Browserless
    browserless_url: str = ""
    browserless_token: str = ""
    workspace_root: str = "/root"
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = DEFAULT_OPENAI_MODEL
    # Evolution API (WhatsApp)
    evolution_api_url: str = ""
    evolution_api_key: str = ""
    evolution_instance: str = ""


class SettingsResponse(SettingsPayload):
    pass


# ── Automation ────────────────────────────────────────────────────────────────

class AutomationCreate(BaseModel):
    name: str
    description: str = ""
    erp_url: str = ""
    instructions: str = ""
    steps: list[dict[str, Any]] = []
    credentials: dict[str, Any] = {}
    outputs: list[dict[str, Any]] = []   # webhook, whatsapp, sheets configs


class AutomationUpdate(AutomationCreate):
    is_active: bool = True


class AutomationResponse(AutomationUpdate):
    id: str
    created_at: str
    updated_at: str
    last_execution_at: str | None = None
    last_execution_status: str | None = None


# ── Execution ─────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    variables: dict[str, Any] = {}   # runtime variable overrides
    live_preview: bool = False


class ExecutionLogResponse(BaseModel):
    id: str
    automation_id: str
    started_at: str
    finished_at: str | None = None
    status: str
    error_message: str | None = None
    steps_completed: int
    total_steps: int
    extracted_data: dict[str, Any] = {}
    screenshots: list[str] = []


# ── Schedule ──────────────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    automation_id: str
    schedule_type: str = "once"   # once | daily | weekly | monthly | interval | cron
    cron_expression: str = ""     # NOT NULL no banco — usa "" quando não for cron
    interval_minutes: int | None = None
    days_of_week: list[int] | None = None
    time_of_day: str | None = None        # "HH:MM"
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True


class ScheduleResponse(ScheduleCreate):
    id: str
    next_run_at: str | None = None
    last_run_at: str | None = None
    created_at: str
