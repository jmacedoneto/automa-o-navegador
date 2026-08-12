from datetime import datetime, timezone
import sys
import types
import unittest


celery_app_stub = types.ModuleType("app.workers.celery_app")


class _CeleryStub:
    def task(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator


celery_app_stub.celery = _CeleryStub()
sys.modules.setdefault("app.workers.celery_app", celery_app_stub)

database_stub = types.ModuleType("app.core.database")
database_stub.get_db = lambda: None
sys.modules.setdefault("app.core.database", database_stub)

tasks_stub = types.ModuleType("app.workers.tasks")
tasks_stub.run_automation = types.SimpleNamespace(delay=lambda *args, **kwargs: None)
sys.modules.setdefault("app.workers.tasks", tasks_stub)

from app.workers.scheduler import _is_due


class SchedulerDueTests(unittest.TestCase):
    def test_weekly_schedule_still_fires_after_short_outage(self):
        schedule = {
            "schedule_type": "weekly",
            "time_of_day": "08:10",
            "days_of_week": [4],  # Friday
            "timezone": "America/Sao_Paulo",
            "last_run_at": None,
        }

        now_utc = datetime(2026, 4, 10, 11, 11, 49, tzinfo=timezone.utc)

        self.assertTrue(_is_due(schedule, now_utc))

    def test_weekly_schedule_does_not_fire_twice_same_day(self):
        schedule = {
            "schedule_type": "weekly",
            "time_of_day": "08:10",
            "days_of_week": [4],  # Friday
            "timezone": "America/Sao_Paulo",
            "last_run_at": "2026-04-10T11:10:49+00:00",
        }

        now_utc = datetime(2026, 4, 10, 11, 11, 49, tzinfo=timezone.utc)

        self.assertFalse(_is_due(schedule, now_utc))


if __name__ == "__main__":
    unittest.main()
