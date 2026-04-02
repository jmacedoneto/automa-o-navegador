from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_get_run_returns_queued_status_for_uuid():
    run_id = "22222222-2222-2222-2222-222222222222"
    response = client.get(f"/api/runs/{run_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == f"Run {run_id} not found in placeholder orchestrator state"


def test_get_run_rejects_invalid_uuid():
    response = client.get("/api/runs/not-a-uuid")

    assert response.status_code == 422
