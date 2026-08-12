"""
Google Sheets integration via Service Account credentials.
Credentials are stored as JSON in the settings table (key: google_service_account).
"""
import json
from typing import Any

import httpx


SCOPES = "https://www.googleapis.com/auth/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"


async def _get_access_token(service_account_json: dict) -> str:
    import time, base64, hashlib, hmac
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend

    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": service_account_json["client_email"],
        "scope": SCOPES,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=")

    signing_input = header + b"." + payload
    private_key = serialization.load_pem_private_key(
        service_account_json["private_key"].encode(),
        password=None,
        backend=default_backend(),
    )
    signature = base64.urlsafe_b64encode(
        private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    ).rstrip(b"=")

    jwt = (signing_input + b"." + signature).decode()

    async with httpx.AsyncClient() as client:
        res = await client.post(TOKEN_URL, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt,
        })
        return res.json()["access_token"]


async def append_row(
    service_account_json: dict,
    spreadsheet_id: str,
    sheet: str,
    row: list[Any],
) -> dict:
    token = await _get_access_token(service_account_json)
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet}!A1:append"
    async with httpx.AsyncClient() as client:
        res = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"valueInputOption": "USER_ENTERED"},
            json={"values": [row]},
        )
    return {"status_code": res.status_code, "body": res.text}


async def update_range(
    service_account_json: dict,
    spreadsheet_id: str,
    range_: str,
    values: list[list[Any]],
) -> dict:
    token = await _get_access_token(service_account_json)
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
    async with httpx.AsyncClient() as client:
        res = await client.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"valueInputOption": "USER_ENTERED"},
            json={"range": range_, "values": values},
        )
    return {"status_code": res.status_code, "body": res.text}
