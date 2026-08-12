from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any
import httpx
from openai import AsyncOpenAI
from app.core.database import get_setting
from app.core.model_config import filter_allowed_openai_models, normalize_openai_model
from app.services.ai_agent import generate_steps, fill_variables

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/models")
async def list_models(key: str | None = None):
    """Fetch available models from OpenAI. Accepts an optional ?key= param (for live testing before save)."""
    api_key = key or await get_setting("openai_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured in Settings")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if not resp.is_success:
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {resp.status_code}")
    data = resp.json()
    models = filter_allowed_openai_models(m["id"] for m in data.get("data", []) if m.get("id"))
    return {"models": models}


class GenerateStepsRequest(BaseModel):
    instructions: str
    context: str = ""


class FillVariablesRequest(BaseModel):
    placeholders: list[str]
    context_data: dict[str, Any]
    instructions: str = ""


@router.post("/generate-steps")
async def api_generate_steps(payload: GenerateStepsRequest):
    api_key = await get_setting("openai_api_key")
    model = normalize_openai_model(await get_setting("openai_model"))
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured in Settings")
    steps = await generate_steps(payload.instructions, api_key, model, payload.context)
    return {"steps": steps}


@router.post("/fill-variables")
async def api_fill_variables(payload: FillVariablesRequest):
    api_key = await get_setting("openai_api_key")
    model = normalize_openai_model(await get_setting("openai_model"))
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured in Settings")
    resolved = await fill_variables(
        payload.placeholders, payload.context_data, payload.instructions, api_key, model
    )
    return {"resolved": resolved}


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribe audio using OpenAI Whisper. Accepts webm/ogg/mp3/wav."""
    api_key = await get_setting("openai_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured in Settings")
    content = await audio.read()
    filename = audio.filename or "audio.webm"
    mime = audio.content_type or "audio/webm"
    client = AsyncOpenAI(api_key=api_key)
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, content, mime),
        response_format="text",
        language="pt",
    )
    return {"text": str(transcript).strip()}
