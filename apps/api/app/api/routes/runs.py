from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: UUID):
    raise HTTPException(
        status_code=404,
        detail=f"Run {run_id} not found in placeholder orchestrator state",
    )
