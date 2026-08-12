from celery import Celery
from app.core.config import settings

celery = Celery(
    "autopilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks", "app.workers.scheduler"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        # Runs every minute to check for due schedules
        "poll-schedules": {
            "task": "app.workers.scheduler.poll_schedules",
            "schedule": 60.0,
        },
    },
)
