from uuid import UUID

from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_create_execution_job_returns_202():
    automation_id = "11111111-1111-1111-1111-111111111111"
    response = client.post(
        "/api/jobs",
        json={
            "automation_id": automation_id,
            "trigger_type": "manual",
            "mode": "hibrido",
            "payload": {"lead_id": "123"},
        },
    )

    assert response.status_code == 202
    UUID(response.json()["id"])
    assert response.json()["automation_id"] == automation_id
    assert response.json()["status"] == "queued"
