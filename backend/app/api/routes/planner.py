"""POST /api/planner/plan — accept a description, return a NavRunner DSL draft."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.automation.planner import plan_automation


router = APIRouter(prefix="/planner", tags=["planner"])


class PlanRequest(BaseModel):
    description: str
    site_url: str = ""
    auth_hint: str = ""


@router.post("/plan")
async def plan(req: PlanRequest) -> dict:
    """Accept a description; return a NavRunner DSL draft."""
    try:
        draft = await plan_automation(
            description=req.description,
            site_url=req.site_url,
            auth_hint=req.auth_hint,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"planner failed: {e}") from e
    return draft