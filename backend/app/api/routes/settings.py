from fastapi import APIRouter, HTTPException
from app.models.schemas import SettingsPayload, SettingsResponse
from app.core.database import get_db, upsert_setting
from app.core.model_config import ALLOWED_OPENAI_MODELS, canonicalize_openai_model, coerce_openai_model

router = APIRouter(prefix="/settings", tags=["settings"])

SETTING_KEYS = [
    "browserless_url",
    "browserless_token",
    "workspace_root",
    "openai_api_key",
    "openai_model",
    "evolution_api_url",
    "evolution_api_key",
    "evolution_instance",
]


def normalize_setting_value(key: str, value: str | None) -> str:
    normalized = (value or "").strip()
    if key == "workspace_root":
        return normalized or "/root"
    if key == "openai_model":
        return coerce_openai_model(normalized)
    return normalized


def validate_openai_model(model: str | None) -> str:
    normalized = canonicalize_openai_model(model)
    if normalized not in ALLOWED_OPENAI_MODELS:
        allowed = ", ".join(ALLOWED_OPENAI_MODELS)
        raise HTTPException(status_code=400, detail=f"Modelo OpenAI inválido. Use apenas: {allowed}")
    return normalized


@router.get("", response_model=SettingsResponse)
async def get_settings():
    db = get_db()
    rows = db.table("settings").select("key,value").in_("key", SETTING_KEYS).execute()
    data = {r["key"]: normalize_setting_value(r["key"], r["value"]) for r in (rows.data or [])}
    return SettingsResponse(**data)


@router.put("", response_model=SettingsResponse)
async def save_settings(payload: SettingsPayload):
    openai_model = validate_openai_model(payload.openai_model)

    for key in SETTING_KEYS:
        raw_value = getattr(payload, key, "")
        value = openai_model if key == "openai_model" else normalize_setting_value(key, raw_value)
        await upsert_setting(key, value)

    response = {
        key: (openai_model if key == "openai_model" else normalize_setting_value(key, getattr(payload, key, "")))
        for key in SETTING_KEYS
    }
    return SettingsResponse(**response)
