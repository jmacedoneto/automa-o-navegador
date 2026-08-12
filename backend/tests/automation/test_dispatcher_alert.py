"""Test that the dispatcher fires WhatsApp alerts on failure."""
from unittest.mock import MagicMock, patch


def test_dispatcher_imports_alerts():
    """Smoke test — alerts module is importable."""
    from app.automation import alerts
    assert callable(alerts.send_whatsapp_alert)


def test_run_automation_v2_fires_alert_on_failure(monkeypatch):
    """When the run fails, send_whatsapp_alert is called with the right args."""
    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "r-1"}])
    fake_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.workers.tasks.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.resolve_credentials", lambda: {"apvs_login": {"user": "x", "pass": "y"}})
    monkeypatch.setattr("app.workers.tasks.settings", MagicMock(BROWSERLESS_URL="ws://x"))

    sent_alerts = []
    def fake_sync_alert(**kw):
        sent_alerts.append(kw)
    # The dispatcher wraps async calls in _run. We mock the dispatcher-side
    # call so the test runs in sync land.
    fake_async = MagicMock()
    def fake_async_alert(**kw):
        async def _inner():
            sent_alerts.append(kw)
        return _inner()
    monkeypatch.setattr("app.workers.tasks.send_whatsapp_alert", fake_async_alert)

    # Fake the runner to return a failed result.
    fake_result = MagicMock()
    fake_result.status = "failed"
    fake_result.errors = ["extract_plano: ValueError: bad response"]
    fake_result.bindings = {}
    fake_result.screenshot_keys = []
    fake_result.screenshot_urls = {}

    async def fake_run_steps(steps, inputs, credentials=None, auth=None):
        return fake_result

    fake_runner = MagicMock()
    fake_runner.run_steps = fake_run_steps
    monkeypatch.setattr("app.workers.tasks.NavRunner", lambda cfg: fake_runner)

    from app.workers.tasks import run_automation_v2
    run_automation_v2(
        automation_name="cotacao_pvs",
        steps_payload=[{"id": "extract_plano", "run_ai": {"schema": "ResultadoCotacao", "instruction": "x"}}],
        inputs={},
    )
    assert len(sent_alerts) == 1, f"expected exactly one alert, got {sent_alerts}"
    assert sent_alerts[0]["automation_name"] == "cotacao_pvs"
    assert sent_alerts[0]["step_id"] == "extract_plano"
    assert "bad response" in sent_alerts[0]["error"]
