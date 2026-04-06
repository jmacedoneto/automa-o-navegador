"""
System health check endpoint.
Returns status of API, Browserless, OpenAI key, and Celery workers.
"""
import asyncio
import httpx
from fastapi import APIRouter
from app.core.database import get_setting
from app.core.config import settings as app_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/status")
async def system_status():
    results = {
        "api": True,
        "browserless": False,
        "openai_key": False,
        "celery": False,
    }

    # Check OpenAI key — DB setting takes priority, fallback to env var
    api_key = await get_setting("openai_api_key") or app_settings.OPENAI_API_KEY
    results["openai_key"] = bool(api_key)

    # Resolve Browserless URL — DB setting takes priority, fallback to env var
    browserless_url = (
        await get_setting("browserless_url") or app_settings.BROWSERLESS_URL or ""
    ).rstrip("/")

    if browserless_url:
        for path in ("/", "/json", "/json/version"):
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(f"{browserless_url}{path}")
                    results["browserless"] = r.status_code < 500
                    break
            except Exception:
                continue

    # Check Celery workers
    try:
        from app.workers.celery_app import celery
        loop = asyncio.get_event_loop()
        inspect = celery.control.inspect(timeout=1.5)
        active = await loop.run_in_executor(None, inspect.ping)
        results["celery"] = bool(active)
    except Exception:
        pass

    return results
