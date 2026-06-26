"""
System health check endpoint.
Returns status of API, Browserless, OpenAI key, and Celery workers.
"""
import asyncio
import time
import httpx
from fastapi import APIRouter
from app.core.database import get_setting
from app.core.config import settings as app_settings

router = APIRouter(prefix="/health", tags=["health"])

# Cache para não bater as verificações externas a cada request
_cache: dict = {"ts": 0.0, "result": None}
_CACHE_TTL = 20  # segundos


async def _check_browserless(url: str) -> bool:
    if not url:
        return False
    url = url.rstrip("/")
    # Testa apenas o primeiro path com timeout curto
    for path in ("/json/version", "/json", "/"):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{url}{path}")
                return r.status_code < 500
        except Exception:
            continue
    return False


async def _check_celery() -> bool:
    try:
        from app.workers.celery_app import celery
        loop = asyncio.get_event_loop()
        inspect = celery.control.inspect(timeout=1.0)
        active = await asyncio.wait_for(
            loop.run_in_executor(None, inspect.ping),
            timeout=1.5
        )
        return bool(active)
    except Exception:
        return False


@router.get("/status")
async def system_status():
    global _cache

    # Retorna cache se ainda válido
    if _cache["result"] and (time.monotonic() - _cache["ts"]) < _CACHE_TTL:
        return _cache["result"]

    # Lê configurações do DB em paralelo
    api_key, browserless_url = await asyncio.gather(
        get_setting("openai_api_key"),
        get_setting("browserless_url"),
    )

    api_key = api_key or app_settings.OPENAI_API_KEY
    browserless_url = browserless_url or app_settings.BROWSERLESS_URL or ""

    # Verifica Browserless e Celery em paralelo
    browserless_ok, celery_ok = await asyncio.gather(
        _check_browserless(browserless_url),
        _check_celery(),
    )

    result = {
        "api": True,
        "browserless": browserless_ok,
        "openai_key": bool(api_key),
        "celery": celery_ok,
    }

    _cache = {"ts": time.monotonic(), "result": result}
    return result
