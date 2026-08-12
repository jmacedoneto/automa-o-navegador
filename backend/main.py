import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import settings, automations, executions, schedules, ai, trigger, recording, health, scrape
from app.core.config import settings as app_settings
from app.core.database import get_db


async def _seed_settings_from_env():
    """On startup, write env-var values into the settings table if not already set.
    This pre-configures Browserless (and any other infra already wired via docker-compose)
    so the user never has to manually fill those fields."""
    seeds = {
        "browserless_url": app_settings.BROWSERLESS_URL,
        "browserless_token": app_settings.BROWSERLESS_TOKEN,
        "openai_api_key": app_settings.OPENAI_API_KEY,
        "evolution_api_url": app_settings.EVOLUTION_API_URL,
        "evolution_api_key": app_settings.EVOLUTION_API_KEY,
        "evolution_instance": app_settings.EVOLUTION_INSTANCE,
    }
    try:
        db = get_db()
        existing = db.table("settings").select("key,value").execute()
        existing_map = {r["key"]: r["value"] for r in (existing.data or [])}
        upserts = [
            {"key": k, "value": v}
            for k, v in seeds.items()
            if v and not existing_map.get(k)  # only seed when env has a value and DB is empty
        ]
        if upserts:
            db.table("settings").upsert(upserts, on_conflict="key").execute()
            print(f"[startup] Seeded {len(upserts)} settings from env vars: {[u['key'] for u in upserts]}")
    except Exception as e:
        print(f"[startup] Could not seed settings: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed_settings_from_env()
    yield


app = FastAPI(title="AutoPilot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes under /api ──────────────────────────────────────────────────
api = FastAPI(title="AutoPilot API")
api.include_router(settings.router)
api.include_router(automations.router)
api.include_router(executions.router)
api.include_router(schedules.router)
api.include_router(ai.router)
api.include_router(trigger.router)
api.include_router(recording.router)
api.include_router(health.router)
api.include_router(scrape.router)

app.mount("/api", api)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Serve React SPA (only when dist/ exists — i.e. in production) ──────────
dist_dir = os.path.join(os.path.dirname(__file__), "dist")
if os.path.isdir(dist_dir):
    # Static assets (JS, CSS, images)
    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Serve chrome extension zip
    ext_zip = os.path.join(os.path.dirname(__file__), "chrome-extension-v2.zip")
    if os.path.isfile(ext_zip):
        @app.get("/chrome-extension-v2.zip")
        async def serve_extension():
            return FileResponse(ext_zip, media_type="application/zip", filename="chrome-extension-v2.zip")

    # SPA fallback — all unknown paths return index.html
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        normalized = full_path.lstrip("/").lower()
        if normalized in {".env", ".git", ".git/config"} or normalized.startswith(".git/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(os.path.join(dist_dir, "index.html"))
