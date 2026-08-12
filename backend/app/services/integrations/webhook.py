import asyncio
import httpx
from typing import Any


async def send_webhook(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    retries: int = 3,
) -> dict:
    """POST payload to URL with exponential backoff retry (default 3 attempts)."""
    headers = headers or {}
    headers.setdefault("Content-Type", "application/json")

    last_err: Exception = RuntimeError("No attempts made")
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code >= 400:
                    raise ValueError(f"HTTP {response.status_code}: {response.text[:300]}")
                return {"status_code": response.status_code, "body": response.text}
        except Exception as exc:
            last_err = exc
            if attempt < retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"[webhook] attempt {attempt + 1} failed ({exc}), retrying in {wait}s…")
                await asyncio.sleep(wait)

    raise last_err
