"""
Smart scrape endpoint — generic browser scraping driven by natural language.

An external AI agent (n8n, LangChain, custom GPT, etc.) can call:

  POST /api/scrape
  {
    "url": "https://www.facebook.com/ads/library/?q=Nike",
    "instructions": "extraia todos os textos e imagens dos anúncios",
    "variables": {}   // optional extra vars
  }

The endpoint will:
  1. Use GPT to generate browser automation steps from the instructions + url
  2. Execute the steps in the browser (Browserless / Playwright)
  3. Return the extracted data (texts, tables, images as base64, screenshots)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from app.core.database import get_setting
from app.core.model_config import normalize_openai_model
from app.services.ai_agent import generate_steps
from app.services.browser_executor import execute_automation

router = APIRouter(prefix="/scrape", tags=["scrape"])


class ScrapeRequest(BaseModel):
    url: str
    instructions: str
    variables: dict[str, Any] = {}


class ScrapeResponse(BaseModel):
    steps_generated: list[dict]
    extracted_data: dict[str, Any]
    screenshots: list[str]
    steps_completed: int


@router.post("", response_model=ScrapeResponse)
async def smart_scrape(payload: ScrapeRequest):
    """
    Generic scrape endpoint. Accepts a URL + natural language instructions,
    generates browser steps via GPT, executes them, and returns extracted data.
    """
    api_key = await get_setting("openai_api_key")
    model = normalize_openai_model(await get_setting("openai_model"))
    browserless_url = await get_setting("browserless_url")
    browserless_token = await get_setting("browserless_token") or ""

    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured in Settings")
    if not browserless_url:
        raise HTTPException(status_code=400, detail="Browserless URL not configured in Settings")

    # Build full instructions including the target URL
    full_instructions = (
        f"Target URL: {payload.url}\n\n"
        f"Instructions: {payload.instructions}\n\n"
        "IMPORTANT: The first step must be a 'navigate' to the target URL. "
        "Use extractText, extractImages, extractTable, evaluate or screenshot as needed. "
        "Always finish with a screenshot step."
    )

    # Step 1 — generate steps from natural language
    steps = await generate_steps(
        instructions=full_instructions,
        api_key=api_key,
        model=model,
    )

    if not steps:
        raise HTTPException(status_code=500, detail="AI failed to generate automation steps")

    # Step 2 — execute in browser
    result = await execute_automation(
        steps=steps,
        variables=payload.variables,
        browserless_url=browserless_url,
        browserless_token=browserless_token,
    )

    return ScrapeResponse(
        steps_generated=steps,
        extracted_data=result.get("extracted_data", {}),
        screenshots=result.get("screenshots", []),
        steps_completed=result.get("steps_completed", 0),
    )
