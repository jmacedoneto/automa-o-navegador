from uuid import UUID

from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_create_recording_session_returns_201():
    automation_id = "11111111-1111-1111-1111-111111111111"
    response = client.post("/api/recordings", json={"automation_id": automation_id})

    assert response.status_code == 201
    UUID(response.json()["id"])
    assert response.json()["automation_id"] == automation_id
    assert response.json()["status"] == "pending"


def test_create_recording_session_accepts_null_automation_id():
    response = client.post("/api/recordings", json={})

    assert response.status_code == 201
    UUID(response.json()["id"])
    assert response.json()["automation_id"] is None
    assert response.json()["status"] == "pending"
