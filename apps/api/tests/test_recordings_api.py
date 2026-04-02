from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_create_recording_session_returns_201():
    response = client.post("/api/recordings", json={"automation_id": "auto-1"})
    assert response.status_code == 201
