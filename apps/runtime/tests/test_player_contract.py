import asyncio
from unittest.mock import AsyncMock

from apps.runtime.runtime.player import build_run_summary
from apps.runtime.main import run_once
from apps.runtime.runtime.config import RuntimeSettings


def test_build_run_summary():
    summary = build_run_summary(steps_completed=3, total_steps=4, status="running")
    assert summary["stepsCompleted"] == 3
    assert summary["status"] == "running"


def test_run_once_executes_job_when_available():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile")
    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value={
        "id": "job-1",
        "automation_id": "auto-1",
        "run_id": "run-1",
        "mode": "gravado",
        "steps": [{"action": "navigate", "url": "https://example.com", "waitTime": 0}],
        "variables": {},
    })
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"png")

    mock_manager = AsyncMock()
    mock_manager.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_manager.close = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_manager, settings=settings)
        assert executed is True
        mock_client.ack_job.assert_called_once_with("job-1")

    asyncio.run(run())


def test_run_once_skips_when_no_job():
    settings = RuntimeSettings()
    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=None)
    mock_manager = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_manager, settings=settings)
        assert executed is False
        mock_manager.launch.assert_not_called()

    asyncio.run(run())
