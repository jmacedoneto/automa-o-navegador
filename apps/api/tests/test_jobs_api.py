from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_create_execution_job_returns_202():
    response = client.post(
        "/api/jobs",
        json={
            "automation_id": "auto-1",
            "trigger_type": "manual",
            "mode": "hibrido",
            "payload": {"lead_id": "123"},
        },
    )
    assert response.status_code == 202
