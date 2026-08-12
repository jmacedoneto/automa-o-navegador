"""Test that the dispatcher honors a top-level `auth` block."""
from unittest.mock import MagicMock


def test_dispatcher_strips_auth_block_from_steps(monkeypatch):
    """When steps_payload[0] is an auth block, the runner's step list is the rest."""
    fake_result = MagicMock(status="success", errors=[], bindings={}, screenshot_keys=[], screenshot_urls={})

    async def fake_run_steps(steps=None, inputs=None, credentials=None, auth=None):
        return fake_result

    fake_runner = MagicMock()
    fake_runner.run_steps = MagicMock(side_effect=fake_run_steps)
    monkeypatch.setattr("app.workers.tasks.NavRunner", lambda cfg: fake_runner)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "r-1"}])
    fake_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.workers.tasks.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.resolve_credentials", lambda: {"apvs_login": {"user": "x", "pass": "y"}})
    monkeypatch.setattr("app.workers.tasks.settings", MagicMock(BROWSERLESS_URL="ws://x"))

    auth_block = {
        "type": "form_login",
        "url": "https://x",
        "credentials_ref": "apvs_login",
        "selectors": {"user": "input", "pass": "input", "submit": "button"},
        "success_assert": {"selector": ".ok", "timeout_ms": 5000},
    }
    body_block = {"id": "click_x", "click": {"selector": "button"}}

    from app.workers.tasks import run_automation_v2
    run_automation_v2(
        automation_name="login_only",
        steps_payload=[{"auth": auth_block}, body_block],
        inputs={},
    )

    fake_runner.run_steps.assert_called_once()
    call = fake_runner.run_steps.call_args
    kwargs = call.kwargs
    steps_seen = kwargs.get("steps") or call.args[0]
    assert auth_block not in steps_seen
    assert getattr(steps_seen[0], "id", None) == "click_x"
    # The auth spec is passed through.
    assert kwargs.get("auth") is not None
    assert kwargs["auth"].type == "form_login"


def test_dispatcher_no_auth_block_unchanged(monkeypatch):
    """When there's no auth block, the dispatcher behaves as before."""
    fake_result = MagicMock(status="success", errors=[], bindings={}, screenshot_keys=[], screenshot_urls={})

    async def fake_run_steps(steps=None, inputs=None, credentials=None, auth=None):
        return fake_result

    fake_runner = MagicMock()
    fake_runner.run_steps = MagicMock(side_effect=fake_run_steps)
    monkeypatch.setattr("app.workers.tasks.NavRunner", lambda cfg: fake_runner)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "r-1"}])
    fake_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.workers.tasks.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.resolve_credentials", lambda: {})
    monkeypatch.setattr("app.workers.tasks.settings", MagicMock(BROWSERLESS_URL="ws://x"))

    from app.workers.tasks import run_automation_v2
    run_automation_v2(
        automation_name="no_auth",
        steps_payload=[{"id": "x", "click": {"selector": "button"}}],
        inputs={},
    )
    fake_runner.run_steps.assert_called_once()
    call = fake_runner.run_steps.call_args
    kwargs = call.kwargs
    assert kwargs.get("auth") is None