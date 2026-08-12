import io
import json


def test_import_trace_returns_dsl_draft():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    trace = {
        "title": "smoke",
        "actions": [
            {"type": "navigate", "url": "https://app.apvs.vc/home"},
            {"type": "click", "selector": "ion-button:has-text(\"SOU CONSULTOR APVS\")"},
            {"type": "type", "selector": "input[type=text]", "value": "user"},
            {"type": "type", "selector": "input[type=password]", "value": "pass"},
            {"type": "click", "selector": "ion-button:has-text(\"Entrar\")"},
            {"type": "wait_for", "selector": ".dashboard"},
            {"type": "click", "selector": "button.continue"},
        ],
    }
    files = {"trace_file": ("trace.json", io.BytesIO(json.dumps(trace).encode()), "application/json")}
    resp = client.post("/api/automation/import-trace", files=files)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["automation_name"] == "smoke"
    assert isinstance(body["steps"], list)
    kinds = [list(s.keys()) for s in body["steps"]]
    assert any("login_block" in k for k in kinds)
    assert any("click" in k for k in kinds)


def test_import_trace_rejects_missing_file():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/api/automation/import-trace")
    assert resp.status_code == 422


def test_import_trace_rejects_bad_json():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    files = {"trace_file": ("trace.json", io.BytesIO(b"not json"), "application/json")}
    resp = client.post("/api/automation/import-trace", files=files)
    assert resp.status_code == 400
    assert "invalid" in resp.text.lower()