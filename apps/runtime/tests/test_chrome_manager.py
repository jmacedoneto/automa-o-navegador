import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.runtime.runtime.chrome_manager import ChromeManager
from apps.runtime.runtime.config import RuntimeSettings


def test_launch_creates_persistent_context():
    settings = RuntimeSettings(chrome_profile_dir="/tmp/test-profile")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=AsyncMock())
    mock_context.close = AsyncMock()

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

    async def run():
        manager = ChromeManager(settings)
        manager._playwright = mock_playwright
        ctx, page = await manager.launch()
        assert ctx is mock_context
        mock_playwright.chromium.launch_persistent_context.assert_called_once()
        call_kwargs = mock_playwright.chromium.launch_persistent_context.call_args
        assert call_kwargs[0][0] == "/tmp/test-profile"
        assert call_kwargs[1]["headless"] is False
        assert call_kwargs[1]["viewport"] == {"width": 1280, "height": 720}

    asyncio.run(run())


def test_close_shuts_down_context():
    mock_context = AsyncMock()

    async def run():
        settings = RuntimeSettings()
        manager = ChromeManager(settings)
        manager._context = mock_context
        await manager.close()
        mock_context.close.assert_called_once()

    asyncio.run(run())
