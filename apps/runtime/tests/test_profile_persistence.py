import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from apps.runtime.runtime.chrome_manager import ChromeManager, chrome_user_data_dir
from apps.runtime.runtime.config import RuntimeSettings


def test_chrome_user_data_dir_resolves_path():
    result = chrome_user_data_dir("/tmp/my-profile")
    assert result == "/tmp/my-profile"


def test_chrome_user_data_dir_relative_resolves_to_absolute():
    result = chrome_user_data_dir(".my-profile")
    assert Path(result).is_absolute()


def test_profile_dir_created_on_launch():
    with tempfile.TemporaryDirectory() as tmp:
        profile_path = f"{tmp}/new-profile"
        settings = RuntimeSettings(chrome_profile_dir=profile_path)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=AsyncMock())

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        async def run():
            manager = ChromeManager(settings)
            manager._playwright = mock_playwright
            await manager.launch()
            assert Path(profile_path).exists()

        asyncio.run(run())


def test_persistent_context_uses_same_dir_across_calls():
    with tempfile.TemporaryDirectory() as tmp:
        profile_path = f"{tmp}/stable-profile"
        settings = RuntimeSettings(chrome_profile_dir=profile_path)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=AsyncMock())
        mock_context.close = AsyncMock()

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        async def run():
            manager = ChromeManager(settings)
            manager._playwright = mock_playwright

            await manager.launch()
            call1 = mock_playwright.chromium.launch_persistent_context.call_args[0][0]
            await manager.close()

            await manager.launch()
            call2 = mock_playwright.chromium.launch_persistent_context.call_args[0][0]

            assert call1 == call2
            assert call1 == profile_path

        asyncio.run(run())
