import asyncio
from unittest.mock import AsyncMock, MagicMock

from apps.runtime.runtime.step_executor import StepExecutor


def _mock_page():
    page = AsyncMock()
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.select_option = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake-png")
    page.evaluate = AsyncMock(return_value=None)
    page.wait_for_load_state = AsyncMock()
    page.keyboard = AsyncMock()
    page.mouse = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.inner_text = AsyncMock(return_value="")
    page.hover = AsyncMock()
    return page


def test_execute_navigate_step():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "navigate", "url": "https://example.com", "waitTime": 0})
        assert result["success"] is True
        page.goto.assert_called_once_with("https://example.com", wait_until="domcontentloaded", timeout=30000)

    asyncio.run(run())


def test_execute_click_step():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "click", "selector": "#btn", "waitTime": 0})
        assert result["success"] is True
        page.click.assert_called_once_with("#btn", timeout=10000)

    asyncio.run(run())


def test_execute_type_step():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "type", "selector": "#name", "value": "test", "waitTime": 0})
        assert result["success"] is True
        page.fill.assert_called_once_with("#name", "test", timeout=10000)

    asyncio.run(run())


def test_execute_unknown_action_skips():
    page = _mock_page()

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "unknown_thing", "waitTime": 0})
        assert result["success"] is True
        assert result["skipped"] is True

    asyncio.run(run())


def test_execute_step_captures_error():
    page = _mock_page()
    page.click = AsyncMock(side_effect=Exception("Element not found"))

    async def run():
        executor = StepExecutor(page)
        result = await executor.execute_step({"action": "click", "selector": "#gone", "waitTime": 0})
        assert result["success"] is False
        assert "Element not found" in result["error"]

    asyncio.run(run())
