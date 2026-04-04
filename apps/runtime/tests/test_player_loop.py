import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.runtime.runtime.player import play_job
from apps.runtime.runtime.config import RuntimeSettings


def test_play_job_executes_steps_and_reports_success():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile")

    job = {
        "id": "job-1",
        "automation_id": "auto-1",
        "run_id": "run-1",
        "mode": "gravado",
        "steps": [
            {"action": "navigate", "url": "https://example.com", "waitTime": 0},
            {"action": "click", "selector": "#btn", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"png")
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_page.fill = AsyncMock()
    mock_page.keyboard = AsyncMock()
    mock_page.mouse = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html></html>")
    mock_page.inner_text = AsyncMock(return_value="")

    async def run():
        result = await play_job(job=job, page=mock_page, client=mock_client, settings=settings)
        assert result["status"] == "success"
        assert result["steps_completed"] == 2
        assert mock_client.report_run_status.call_count >= 2

    asyncio.run(run())


def test_play_job_reports_failure_on_step_error():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile", max_fallback_attempts=1)

    job = {
        "id": "job-1",
        "automation_id": "auto-1",
        "run_id": "run-1",
        "mode": "gravado",
        "steps": [
            {"action": "click", "selector": "#missing", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_page = AsyncMock()
    mock_page.click = AsyncMock(side_effect=Exception("Timeout"))
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"png")

    async def run():
        result = await play_job(job=job, page=mock_page, client=mock_client, settings=settings)
        assert result["status"] == "failed"
        last_call = mock_client.report_run_status.call_args
        assert last_call[1]["status"] == "failed"

    asyncio.run(run())
