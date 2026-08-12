"""WhatsApp alerts via Evolution API.

P2 implements the failure path. The success path is out of scope (alerts on
completion can drown signal in noise).

Configuration lives in `settings` table under key `whatsapp_alert`:
    {
      "api_url": "https://evolution.suavps.com",
      "api_key": "...",
      "instance": "main",
      "to": "5511999999999"
    }

When unconfigured, `send_whatsapp_alert` is a silent no-op.
"""
from typing import Any

from app.services.integrations.whatsapp import send_whatsapp
from app.automation import credentials


def _resolve_alert_config() -> dict[str, Any]:
    """Pull the whatsapp_alert config from the settings table."""
    return credentials.resolve_credentials().get("whatsapp_alert", {}) or {}


def build_failure_alert_text(
    run_id: str,
    automation_name: str,
    step_id: str,
    error: str,
    screenshot_url: str | None = None,
) -> str:
    """Format the failure alert body."""
    text = (
        f"❌ {automation_name} #{run_id} falhou em `{step_id}`.\n\n"
        f"Error: {error}"
    )
    if screenshot_url:
        text += f"\n\nScreenshot: {screenshot_url}"
    return text


async def send_whatsapp_alert(
    run_id: str,
    automation_name: str,
    step_id: str,
    error: str,
    screenshot_url: str | None = None,
) -> None:
    """Send a WhatsApp alert via Evolution. No-op when config missing."""
    config = _resolve_alert_config()
    if not config:
        return
    text = build_failure_alert_text(
        run_id=run_id,
        automation_name=automation_name,
        step_id=step_id,
        error=error,
        screenshot_url=screenshot_url,
    )
    try:
        await send_whatsapp(config, text)
    except Exception:
        # Alerts are best-effort; never fail the run.
        pass
