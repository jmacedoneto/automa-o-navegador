import asyncio
import signal

from apps.runtime.runtime.config import RuntimeSettings
from apps.runtime.runtime.chrome_manager import ChromeManager
from apps.runtime.runtime.client import ApiClient
from apps.runtime.runtime.player import play_job


async def run_once(client: ApiClient, chrome: ChromeManager, settings: RuntimeSettings) -> bool:
    job = await client.poll_next_job()
    if job is None:
        return False

    await client.ack_job(job["id"])

    _ctx, page = await chrome.launch()
    try:
        await play_job(job=job, page=page, client=client, settings=settings)
    finally:
        await chrome.close()

    return True


async def run_loop(settings: RuntimeSettings | None = None):
    settings = settings or RuntimeSettings()
    client = ApiClient(base_url=settings.api_base_url)
    chrome = ChromeManager(settings)

    stop = asyncio.Event()

    def _handle_signal():
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    print(f"[runtime] polling {settings.api_base_url} every {settings.poll_interval_seconds}s")

    while not stop.is_set():
        try:
            executed = await run_once(client=client, chrome=chrome, settings=settings)
            if not executed:
                await asyncio.sleep(settings.poll_interval_seconds)
        except Exception as exc:
            print(f"[runtime] error: {exc}")
            await asyncio.sleep(settings.poll_interval_seconds)

    print("[runtime] shutting down")


def main():
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
