from fastapi import APIRouter, HTTPException
from app.models.schemas import ScheduleCreate, ScheduleResponse
from app.core.database import get_db

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(automation_id: str | None = None):
    db = get_db()
    query = db.table("schedules").select("*").order("created_at", desc=True)
    if automation_id:
        query = query.eq("automation_id", automation_id)
    res = query.execute()
    return res.data or []


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(payload: ScheduleCreate):
    db = get_db()
    res = db.table("schedules").insert(payload.model_dump()).execute()
    return res.data[0]


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: str, payload: ScheduleCreate):
    db = get_db()
    res = db.table("schedules").update(payload.model_dump()).eq("id", schedule_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return res.data[0]


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str):
    db = get_db()
    db.table("schedules").delete().eq("id", schedule_id).execute()


@router.patch("/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: str):
    db = get_db()
    current = db.table("schedules").select("is_active").eq("id", schedule_id).maybe_single().execute()
    if not current.data:
        raise HTTPException(status_code=404, detail="Schedule not found")
    new_state = not current.data["is_active"]
    db.table("schedules").update({"is_active": new_state}).eq("id", schedule_id).execute()
    return {"is_active": new_state}
