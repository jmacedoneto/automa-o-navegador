from fastapi import APIRouter

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: str):
    return {"id": run_id, "status": "queued"}
