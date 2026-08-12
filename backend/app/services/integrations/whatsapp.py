"""
WhatsApp integration — pluggable provider system.
Default: Evolution API. To add a new provider, implement send_message(config, to, text, file_path).
"""
import httpx
from typing import Any


async def send_via_evolution(
    api_url: str,
    api_key: str,
    instance: str,
    to: str,
    text: str,
    file_path: str | None = None,
) -> dict[str, Any]:
    base = api_url.rstrip("/")
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        if file_path:
            # Send document
            import base64, mimetypes
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            filename = file_path.split("/")[-1]
            res = await client.post(
                f"{base}/message/sendMedia/{instance}",
                headers=headers,
                json={
                    "number": to,
                    "mediatype": "document",
                    "mimetype": mime,
                    "caption": text,
                    "media": encoded,
                    "fileName": filename,
                },
            )
        else:
            res = await client.post(
                f"{base}/message/sendText/{instance}",
                headers=headers,
                json={"number": to, "text": text},
            )

    return {"status_code": res.status_code, "body": res.text}


async def send_whatsapp(config: dict[str, Any], text: str, file_path: str | None = None) -> dict[str, Any]:
    """
    config keys:
      provider    — "evolution" (default) or any future provider
      api_url     — Evolution API base URL
      api_key     — Evolution API key
      instance    — Evolution instance name
      to          — recipient phone number (e.g. 5511999999999)
    """
    provider = config.get("provider", "evolution")

    if provider == "evolution":
        return await send_via_evolution(
            api_url=config["api_url"],
            api_key=config["api_key"],
            instance=config["instance"],
            to=config["to"],
            text=text,
            file_path=file_path,
        )

    raise ValueError(f"Unsupported WhatsApp provider: {provider}")
