"""
End-to-end scenario: simulates the full runtime cycle.
1. Client polls a job
2. Chrome manager launches (mocked)
3. Player executes steps (mocked page)
4. Client reports success

No real browser. Validates the full wiring between components.
"""
import asyncio
from unittest.mock import AsyncMock

from apps.runtime.main import run_once
from apps.runtime.runtime.config import RuntimeSettings


def _mock_page():
    page = AsyncMock()
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.select_option = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake-png")
    page.evaluate = AsyncMock(return_value=None)
    page.keyboard = AsyncMock()
    page.mouse = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.inner_text = AsyncMock(return_value="text")
    page.hover = AsyncMock()
    return page


def test_full_e2e_navigate_click_type():
    """Simulate a 3-step automation: navigate -> click -> type."""
    settings = RuntimeSettings(chrome_profile_dir="/tmp/e2e-test")

    job = {
        "id": "job-e2e",
        "automation_id": "auto-e2e",
        "run_id": "run-e2e",
        "mode": "gravado",
        "steps": [
            {"action": "navigate", "url": "https://erp.example.com/login", "waitTime": 0},
            {"action": "type", "selector": "#user", "value": "admin", "waitTime": 0},
            {"action": "click", "selector": "#submit", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=job)
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = _mock_page()
    mock_chrome = AsyncMock()
    mock_chrome.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_chrome.close = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_chrome, settings=settings)
        assert executed is True

        mock_client.ack_job.assert_called_once_with("job-e2e")

        mock_page.goto.assert_called_once_with(
            "https://erp.example.com/login",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        mock_page.fill.assert_called_once_with("#user", "admin", timeout=10000)
        mock_page.click.assert_called_once_with("#submit", timeout=10000)

        last_call = mock_client.report_run_status.call_args
        assert last_call[1]["status"] == "success"
        assert last_call[1]["steps_completed"] == 3

    asyncio.run(run())


def test_full_e2e_with_variables():
    """Simulate automation with {{variable}} substitution."""
    settings = RuntimeSettings(chrome_profile_dir="/tmp/e2e-vars")

    job = {
        "id": "job-vars",
        "automation_id": "auto-vars",
        "run_id": "run-vars",
        "mode": "gravado",
        "steps": [
            {"action": "navigate", "url": "https://erp.example.com", "waitTime": 0},
            {"action": "type", "selector": "#user", "value": "{{username}}", "waitTime": 0},
            {"action": "type", "selector": "#pass", "value": "{{password}}", "waitTime": 0},
        ],
        "variables": {"username": "admin", "password": "secret123"},
    }

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=job)
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = _mock_page()
    mock_chrome = AsyncMock()
    mock_chrome.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_chrome.close = AsyncMock()

    async def run():
        await run_once(client=mock_client, chrome=mock_chrome, settings=settings)

        calls = mock_page.fill.call_args_list
        assert calls[0][0] == ("#user", "admin")
        assert calls[1][0] == ("#pass", "secret123")

    asyncio.run(run())


def test_full_e2e_failure_reports_error():
    """When a step fails past fallback limit, run reports failed."""
    settings = RuntimeSettings(chrome_profile_dir="/tmp/e2e-fail", max_fallback_attempts=1)

    job = {
        "id": "job-fail",
        "automation_id": "auto-fail",
        "run_id": "run-fail",
        "mode": "gravado",
        "steps": [
            {"action": "click", "selector": "#nonexistent", "waitTime": 0},
        ],
        "variables": {},
    }

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=job)
    mock_client.ack_job = AsyncMock()
    mock_client.report_run_status = AsyncMock()

    mock_page = _mock_page()
    mock_page.click = AsyncMock(side_effect=Exception("Element not found"))

    mock_chrome = AsyncMock()
    mock_chrome.launch = AsyncMock(return_value=(AsyncMock(), mock_page))
    mock_chrome.close = AsyncMock()

    async def run():
        await run_once(client=mock_client, chrome=mock_chrome, settings=settings)

        last_call = mock_client.report_run_status.call_args
        assert last_call[1]["status"] == "failed"
        assert "Element not found" in last_call[1]["error"]

    asyncio.run(run())


def test_no_job_does_nothing():
    """When no job is available, run_once returns False without launching Chrome."""
    settings = RuntimeSettings()

    mock_client = AsyncMock()
    mock_client.poll_next_job = AsyncMock(return_value=None)

    mock_chrome = AsyncMock()

    async def run():
        executed = await run_once(client=mock_client, chrome=mock_chrome, settings=settings)
        assert executed is False
        mock_chrome.launch.assert_not_called()

    asyncio.run(run())
