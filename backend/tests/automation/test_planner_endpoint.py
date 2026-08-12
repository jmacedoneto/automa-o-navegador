from unittest.mock import MagicMock, patch


def test_endpoint_returns_dsl_draft():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_draft = {
        "automation_name": "ping",
        "version": 1,
        "steps": [{"id": "x", "goto": "https://x"}],
        "notes": [],
    }

    async def fake_plan(description, site_url, auth_hint="", model=None):
        return fake_draft

    with patch("app.api.routes.planner.plan_automation", side_effect=fake_plan):
        resp = client.post("/api/planner/plan", json={
            "description": "ping example",
            "site_url": "https://example.com",
            "auth_hint": "",
        })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["automation_name"] == "ping"
    assert isinstance(body["steps"], list)


def test_endpoint_rejects_empty_description():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/api/planner/plan", json={
        "description": "",
        "site_url": "https://x.com",
    })
    assert resp.status_code == 400


def test_endpoint_rejects_missing_description():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/api/planner/plan", json={"site_url": "https://x.com"})
    assert resp.status_code == 422


def test_endpoint_propagates_openai_errors():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    async def fake_plan(**kw):
        raise RuntimeError("openai is down")

    with patch("app.api.routes.planner.plan_automation", side_effect=fake_plan):
        resp = client.post("/api/planner/plan", json={
            "description": "x",
            "site_url": "https://x",
        })
    assert resp.status_code == 500
