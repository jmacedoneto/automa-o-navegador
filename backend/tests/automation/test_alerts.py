import asyncio
from unittest.mock import AsyncMock

from app.automation.alerts import (
    build_failure_alert_text,
    send_whatsapp_alert,
    _resolve_alert_config,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_build_failure_alert_text_includes_run_id():
    text = build_failure_alert_text(
        run_id="r-1",
        automation_name="cotacao_pvs",
        step_id="extract_plano",
        error="plan not found",
        screenshot_url="https://s3/shot.png",
    )
    assert "cotacao_pvs" in text
    assert "r-1" in text
    assert "extract_plano" in text
    assert "plan not found" in text
    assert "https://s3/shot.png" in text


def test_build_failure_alert_text_no_screenshot():
    text = build_failure_alert_text(
        run_id="r-1",
        automation_name="auto",
        step_id="x",
        error="err",
    )
    assert "Screenshot" not in text


def test_resolve_alert_config_returns_empty_when_no_config(monkeypatch):
    monkeypatch.setattr("app.automation.credentials.resolve_credentials", lambda: {})
    config = _resolve_alert_config()
    assert config == {}


def test_resolve_alert_config_pulls_from_settings(monkeypatch):
    monkeypatch.setattr(
        "app.automation.credentials.resolve_credentials",
        lambda: {"whatsapp_alert": {
            "api_url": "https://evolution.suavps.com",
            "api_key": "abc",
            "instance": "main",
            "to": "5511999999999",
        }},
    )
    config = _resolve_alert_config()
    assert config["api_url"] == "https://evolution.suavps.com"
    assert config["to"] == "5511999999999"


def test_send_whatsapp_alert_sends_message(monkeypatch):
    fake_send = AsyncMock(return_value={"status_code": 200, "body": "ok"})
    monkeypatch.setattr("app.automation.alerts.send_whatsapp", fake_send)
    monkeypatch.setattr(
        "app.automation.credentials.resolve_credentials",
        lambda: {"whatsapp_alert": {
            "api_url": "https://evolution.suavps.com",
            "api_key": "abc",
            "instance": "main",
            "to": "5511999999999",
        }},
    )
    _run(send_whatsapp_alert(
        run_id="r-1",
        automation_name="cotacao_pvs",
        step_id="extract",
        error="boom",
    ))
    fake_send.assert_called_once()
    args = fake_send.call_args.args
    assert args[0]["to"] == "5511999999999"
    assert "cotacao_pvs" in args[1]


def test_send_whatsapp_alert_silent_when_unconfigured(monkeypatch):
    fake_send = AsyncMock()
    monkeypatch.setattr("app.automation.alerts.send_whatsapp", fake_send)
    monkeypatch.setattr("app.automation.credentials.resolve_credentials", lambda: {})
    _run(send_whatsapp_alert(
        run_id="r-1",
        automation_name="auto",
        step_id="x",
        error="err",
    ))
    fake_send.assert_not_called()
