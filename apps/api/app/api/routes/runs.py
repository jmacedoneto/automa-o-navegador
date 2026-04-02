from uuid import UUID

from fastapi import APIRouter

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: UUID):
    return {"id": str(run_id), "status": "queued"}
