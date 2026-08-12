"""
Celery Beat scheduler — polls the schedules table every minute
and queues automations that are due to run.
"""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.workers.celery_app import celery
from app.core.database import get_db
from app.workers.tasks import run_automation


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _is_due(schedule: dict, now_utc: datetime) -> bool:
    """Return True if this schedule should fire right now."""
    tz = ZoneInfo(schedule.get("timezone") or "America/Sao_Paulo")
    now_local = now_utc.astimezone(tz)
    last_run_local = None
    last_run = _parse_dt(schedule.get("last_run_at"))
    if last_run:
        last_run_local = last_run.astimezone(tz)

    stype = schedule.get("schedule_type", "once")

    if stype == "once":
        next_run = schedule.get("next_run_at")
        if not next_run:
            return False
        next_dt = _parse_dt(next_run).astimezone(timezone.utc)
        return now_utc >= next_dt

    if stype == "interval":
        minutes = schedule.get("interval_minutes") or 0
        if not minutes:
            return False
        if not last_run:
            return True  # never ran, run now
        last_dt = last_run.astimezone(timezone.utc)
        return now_utc >= last_dt + timedelta(minutes=minutes)

    if stype in ("daily", "weekly", "monthly"):
        time_str = schedule.get("time_of_day")  # "HH:MM"
        if not time_str:
            return False
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        scheduled_local = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
        if now_local < scheduled_local:
            return False

        if stype == "daily":
            pass

        if stype == "weekly":
            days = schedule.get("days_of_week") or []
            if now_local.weekday() not in days:
                return False

        if stype == "monthly":
            # Fire on the same day-of-month as next_run_at
            next_run = schedule.get("next_run_at")
            if next_run:
                target_day = _parse_dt(next_run).day
                if now_local.day != target_day:
                    return False
            elif now_local.day != 1:
                return False

        if last_run_local and last_run_local >= scheduled_local:
            return False
        return True

    if stype == "cron":
        # Basic cron: check next_run_at set by user/API
        next_run = schedule.get("next_run_at")
        if not next_run:
            return False
        next_dt = _parse_dt(next_run).astimezone(timezone.utc)
        return now_utc >= next_dt

    return False


@celery.task(name="app.workers.scheduler.poll_schedules")
def poll_schedules():
    """Check all active schedules and queue automations that are due."""
    db = get_db()
    now = datetime.now(timezone.utc)

    try:
        res = db.table("schedules").select("*").eq("is_active", True).execute()
    except Exception as e:
        print(f"[poll_schedules] Supabase unavailable, skipping: {e}")
        return {"checked": 0, "fired": 0, "error": str(e)}
    schedules = res.data or []

    fired = 0
    for schedule in schedules:
        if not _is_due(schedule, now):
            continue

        automation_id = schedule["automation_id"]
        run_automation.delay(automation_id)

        # Update last_run_at
        db.table("schedules").update({
            "last_run_at": now.isoformat(),
        }).eq("id", schedule["id"]).execute()

        fired += 1

    return {"checked": len(schedules), "fired": fired}
