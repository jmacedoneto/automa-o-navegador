import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.automation.storage import upload_to_minio, _minio_configured


def test_minio_configured_when_all_env_set(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "s3.x.com")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
    monkeypatch.setenv("MINIO_BUCKET", "automation-screenshots")
    assert _minio_configured() is True


def test_minio_not_configured_when_missing(monkeypatch):
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    monkeypatch.delenv("MINIO_BUCKET", raising=False)
    assert _minio_configured() is False


def test_minio_partial_env_not_configured(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "s3.x.com")
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    assert _minio_configured() is False


def test_upload_to_minio_skips_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    fake = MagicMock()
    fake.put_object = MagicMock()
    with patch("app.automation.storage.Minio", return_value=fake):
        url = upload_to_minio(tmp_path / "x.png", "run-1", "step", "after")
    assert url is None
    assert fake.put_object.called is False


def test_upload_to_minio_uploads_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "s3.x.com")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
    monkeypatch.setenv("MINIO_BUCKET", "automation-screenshots")
    fake_local = tmp_path / "shot.png"
    fake_local.write_bytes(b"PNG-DATA")
    fake_client = MagicMock()
    fake_url = "https://s3.x.com/automation-screenshots/run-1/step_after.png"
    fake_client.presigned_get_object = MagicMock(return_value=fake_url)
    with patch("app.automation.storage.Minio", return_value=fake_client):
        url = upload_to_minio(fake_local, "run-1", "step", "after")
    assert fake_client.put_object.called
    assert url == fake_url


def test_upload_to_minio_handles_upload_error_gracefully(tmp_path, monkeypatch):
    """A failed upload should not propagate — caller (runner) catches and continues."""
    monkeypatch.setenv("MINIO_ENDPOINT", "s3.x.com")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
    monkeypatch.setenv("MINIO_BUCKET", "automation-screenshots")
    fake_local = tmp_path / "shot.png"
    fake_local.write_bytes(b"PNG-DATA")
    fake_client = MagicMock()
    fake_client.put_object = MagicMock(side_effect=RuntimeError("network down"))
    with patch("app.automation.storage.Minio", return_value=fake_client):
        # Returns None on failure (runner can fall back to local path).
        url = upload_to_minio(fake_local, "run-1", "step", "after")
    assert url is None
