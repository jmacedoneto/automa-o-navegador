"""MinIO screenshot helpers.

P0 declared the key shape. P1a adds the actual upload (when env vars are set)
and a presigned URL formatter. Unconfigured calls return `None` so callers
fall back to local paths.
"""
import os
from pathlib import Path
from typing import Literal

from minio import Minio  # module-level so tests can patch app.automation.storage.Minio

Phase = Literal["before", "after", "on_fail"]


def _flatten(s: str) -> str:
    return s.replace("/", "_")


def build_screenshot_key(
    run_id: str,
    step_id: str,
    phase: Phase | str = "after",
) -> str:
    return f"automation-screenshots/{_flatten(run_id)}/{_flatten(step_id)}_{phase}.png"


def build_screenshot_url(bucket_endpoint: str, key: str) -> str:
    return f"{bucket_endpoint.rstrip('/')}/{key}"


def _minio_configured() -> bool:
    return all([
        os.environ.get("MINIO_ENDPOINT"),
        os.environ.get("MINIO_ACCESS_KEY"),
        os.environ.get("MINIO_SECRET_KEY"),
        os.environ.get("MINIO_BUCKET"),
    ])


def upload_to_minio(
    local_path: Path,
    run_id: str,
    step_id: str,
    phase: Phase | str = "after",
) -> str | None:
    """Upload the local screenshot to MinIO and return a presigned URL.

    Returns None when MinIO is not configured (caller falls back to local path)
    or when the upload fails (best-effort).
    """
    if not _minio_configured():
        return None
    try:
        client = Minio(
            os.environ["MINIO_ENDPOINT"],
            access_key=os.environ["MINIO_ACCESS_KEY"],
            secret_key=os.environ["MINIO_SECRET_KEY"],
            secure=os.environ.get("MINIO_SECURE", "true").lower() == "true",
        )
        key = build_screenshot_key(run_id, step_id, phase)
        data = local_path.read_bytes()
        from io import BytesIO
        client.put_object(
            bucket_name=os.environ["MINIO_BUCKET"],
            object_name=key,
            data=BytesIO(data),
            length=len(data),
            content_type="image/png",
        )
        return client.presigned_get_object(
            bucket_name=os.environ["MINIO_BUCKET"],
            object_name=key,
            expires=24 * 60 * 60,  # 24h presigned URL
        )
    except Exception:
        # Best-effort: caller falls back to local path.
        return None
