import hmac
import hashlib
import json
from unittest.mock import MagicMock


def _fake_automation_row(automation_id="auto-1", name="X", credentials=None, steps=None):
    return {
        "id": automation_id,
        "name": name,
        "credentials": credentials or {},
        "steps": steps or [{"id": "use_var", "fill": {"#x": "{{input.cnpj}}"}}],
    }


def test_webhook_returns_execution_id(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row()]
    )
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "exec-123"}])
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    fake_delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr("app.workers.tasks.run_automation", MagicMock(delay=fake_delay))

    resp = client.post("/api/trigger/auto-1", json={"variables": {"cnpj": "123"}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["execution_id"] == "exec-123"
    assert body["automation_name"] == "X"
    assert body["status"] == "queued"


def test_webhook_validates_required_variables(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row(steps=[
            {"id": "fill_cnpj", "fill": {"#cnpj": "{{input.cnpj}}"}},
            {"id": "fill_doc",  "fill": {"#doc":  "{{input.doc}}"}},
        ])]
    )
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    resp = client.post("/api/trigger/auto-1", json={"variables": {"cnpj": "123"}})  # missing doc
    assert resp.status_code == 400
    assert "doc" in resp.text


def test_webhook_token_auth(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row(credentials={"webhook_token": "secret-abc"})]
    )
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    # No token → 401
    resp = client.post("/api/trigger/auto-1", json={})
    assert resp.status_code == 401

    # Wrong token → 401
    resp = client.post("/api/trigger/auto-1?token=wrong", json={})
    assert resp.status_code == 401


def test_webhook_hmac_signature(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_fake_automation_row(credentials={"webhook_secret": "shhh"})]
    )
    fake_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "exec-h"}])
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)
    monkeypatch.setattr("app.workers.tasks.run_automation", MagicMock(delay=MagicMock(return_value=MagicMock(id="t"))))

    body = {"variables": {"cnpj": "123"}}
    raw = json.dumps(body).encode()
    sig = hmac.new(b"shhh", raw, hashlib.sha256).hexdigest()

    # Bad signature → 401
    resp = client.post("/api/trigger/auto-1", json=body, headers={"X-Signature": "deadbeef"})
    assert resp.status_code == 401

    # Good signature → 200
    resp = client.post("/api/trigger/auto-1", json=body, headers={"X-Signature": sig})
    assert resp.status_code == 200


def test_webhook_returns_404_for_missing_automation(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    fake_db = MagicMock()
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    fake_db.table.return_value = fake_table
    monkeypatch.setattr("app.api.routes.trigger.get_db", lambda: fake_db)

    resp = client.post("/api/trigger/missing-id", json={})
    assert resp.status_code == 404
