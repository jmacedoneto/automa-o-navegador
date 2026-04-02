from fastapi import FastAPI

from apps.api.app.api.routes.jobs import router as jobs_router
from apps.api.app.api.routes.recordings import router as recordings_router
from apps.api.app.api.routes.runs import router as runs_router

app = FastAPI(title="AutoPilot Orchestrator")
app.include_router(jobs_router, prefix="/api")
app.include_router(recordings_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
