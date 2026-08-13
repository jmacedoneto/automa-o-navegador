import asyncio
import json
from unittest.mock import MagicMock, patch

from app.mcp_server.tools import (
    list_automations,
    get_automation,
    list_runs,
    get_run_status,
    plan_automation,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_list_automations_returns_summary():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
        {"id": "a-1", "name": "Cotação FIPE", "is_active": True},
        {"id": "a-2", "name": "Préboleto Mensal", "is_active": False},
    ])
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(list_automations())
    assert len(out) == 2
    assert out[0]["id"] == "a-1"
    assert out[0]["name"] == "Cotação FIPE"
    assert out[1]["is_active"] is False


def test_get_automation_returns_full_record():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "a-1", "name": "X", "steps": [{"id": "y"}], "auth": {"type": "form_login"}}]
    )
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(get_automation("a-1"))
    assert out["id"] == "a-1"
    assert out["steps"] == [{"id": "y"}]
    assert out["auth"]["type"] == "form_login"


def test_get_automation_returns_none_for_missing():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(get_automation("missing"))
    assert out is None


def test_list_runs_returns_recent():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[
        {"id": "run-1", "automation_id": "a-1", "status": "success", "started_at": "2026-08-12T00:00:00Z"},
    ])
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(list_runs(limit=10))
    assert len(out) == 1
    assert out[0]["status"] == "success"


def test_get_run_status_returns_full_record():
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "run-1", "status": "failed", "error_message": "boom"}]
    )
    fake_db.table.return_value = fake_table
    with patch("app.mcp_server.tools.get_db", lambda: fake_db):
        out = _run(get_run_status("run-1"))
    assert out["status"] == "failed"
    assert out["error_message"] == "boom"


def test_plan_automation_returns_draft():
    fake_draft = {
        "automation_name": "ping",
        "version": 1,
        "steps": [{"id": "x", "goto": "https://x"}],
        "notes": [],
    }
    async def fake_plan(description, site_url, auth_hint="", model=None):
        return fake_draft
    with patch("app.automation.planner.plan_automation", side_effect=fake_plan):
        out = _run(plan_automation(description="do a thing", site_url="https://x"))
    assert out["automation_name"] == "ping"
