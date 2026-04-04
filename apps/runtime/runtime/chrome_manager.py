from pathlib import Path

from apps.runtime.runtime.config import RuntimeSettings


def chrome_user_data_dir(base_dir: str = ".runtime-profile") -> str:
    return str(Path(base_dir).resolve())


class ChromeManager:
    def __init__(self, settings: RuntimeSettings):
        self._settings = settings
        self._playwright = None
        self._context = None
        self._page = None

    async def launch(self):
        profile_dir = chrome_user_data_dir(self._settings.chrome_profile_dir)
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        if self._playwright is None:
            from playwright.async_api import async_playwright
            pw = async_playwright()
            self._playwright = await pw.start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            profile_dir,
            headless=self._settings.chrome_headless,
            viewport={
                "width": self._settings.chrome_viewport_width,
                "height": self._settings.chrome_viewport_height,
            },
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = await self._context.new_page()
        return self._context, self._page

    async def close(self):
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None

    @property
    def page(self):
        return self._page
