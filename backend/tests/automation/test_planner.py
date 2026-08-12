import json
from unittest.mock import AsyncMock, MagicMock

from app.automation.planner import plan_automation


def _run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


def _fake_response(steps_dict):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message = MagicMock()
    r.choices[0].message.content = json.dumps(steps_dict)
    return r


def test_plan_automation_returns_dsl_draft(monkeypatch):
    """The auth block is steps[0] (runner convention)."""
    draft = {
        "automation_name": "cotar_carro",
        "version": 1,
        "steps": [
            {
                "id": "auth",
                "auth": {
                    "type": "form_login",
                    "url": "https://app.apvs.vc",
                    "credentials_ref": "apvs_login",
                    "selectors": {"user": "input[type=text]", "pass": "input[type=password]", "submit": "button"},
                    "success_assert": {"selector": ".dashboard", "timeout_ms": 30000},
                },
            },
            {"id": "open_app", "goto": "https://app.apvs.vc/dashboard"},
            {"id": "fill_cnpj", "fill": {"#cnpj": "{{input.cnpj}}"}},
        ],
        "notes": [],
    }
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Automatize cotação de carro",
        site_url="https://app.apvs.vc",
        auth_hint="login with CNPJ + password",
    ))
    assert out["automation_name"] == "cotar_carro"
    assert isinstance(out["steps"], list)
    # First step is the auth envelope.
    assert out["steps"][0]["id"] == "auth"
    assert out["steps"][0]["auth"]["type"] == "form_login"
    # Second step is the real navigation.
    assert out["steps"][1]["goto"] == "https://app.apvs.vc/dashboard"


def test_plan_automation_handles_no_auth(monkeypatch):
    draft = {
        "automation_name": "ping",
        "version": 1,
        "steps": [{"id": "ping", "goto": "https://example.com"}],
        "notes": [],
    }
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Visit example.com",
        site_url="https://example.com",
        auth_hint="no auth",
    ))
    assert "auth" not in out
    assert out["steps"][0]["goto"] == "https://example.com"


def test_plan_automation_includes_notes_for_unknown(monkeypatch):
    draft = {
        "automation_name": "thing",
        "version": 1,
        "steps": [{"id": "x", "fill": {"#input": ""}}],
        "notes": ["Could not determine the value for #input — fill in manually."],
    }
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Do a thing",
        site_url="https://example.com",
        auth_hint="",
    ))
    assert len(out["notes"]) == 1
    assert "manually" in out["notes"][0]


def test_plan_automation_normalizes_strings(monkeypatch):
    draft = {"automation_name": "Foo Bar Baz", "version": 1, "steps": [], "notes": []}
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="Foo Bar Baz",
        site_url="https://example.com",
        auth_hint="",
    ))
    assert out["automation_name"] == "foo_bar_baz"


def test_plan_automation_defaults_version_to_one(monkeypatch):
    draft = {"automation_name": "x", "steps": []}
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response(draft))
    monkeypatch.setattr("app.automation.planner._get_openai_client", lambda: fake_client)

    out = _run(plan_automation(
        description="x",
        site_url="https://example.com",
        auth_hint="",
    ))
    assert out["version"] == 1
    assert out["notes"] == []


def test_plan_automation_handles_empty_description():
    import asyncio, pytest
    with pytest.raises(ValueError, match="description"):
        asyncio.run(plan_automation(description="", site_url="https://x", auth_hint=""))
