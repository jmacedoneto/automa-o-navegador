import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.runtime.runtime.client import ApiClient


def test_poll_next_job_returns_job_when_available():
    client = ApiClient(base_url="http://localhost:8000")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "id": "job-1",
        "automation_id": "auto-1",
        "trigger_type": "manual",
        "mode": "hibrido",
        "payload": {},
        "steps": [{"action": "navigate", "url": "https://example.com"}],
    })
    mock_response.raise_for_status = MagicMock()

    async def run():
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            job = await client.poll_next_job()
            assert job is not None
            assert job["id"] == "job-1"
            instance.get.assert_called_once_with(f"{client.base_url}/api/jobs/next")

    asyncio.run(run())


def test_poll_next_job_returns_none_when_empty():
    client = ApiClient(base_url="http://localhost:8000")

    mock_response = AsyncMock()
    mock_response.status_code = 204
    mock_response.raise_for_status = MagicMock()

    async def run():
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            job = await client.poll_next_job()
            assert job is None

    asyncio.run(run())


def test_report_run_status():
    client = ApiClient(base_url="http://localhost:8000")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def run():
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.patch = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await client.report_run_status("run-1", status="running", steps_completed=2)
            instance.patch.assert_called_once()
            call_kwargs = instance.patch.call_args
            assert "run-1" in call_kwargs[0][0]
            assert call_kwargs[1]["json"]["status"] == "running"

    asyncio.run(run())
