import pytest

from app.automation.credentials import resolve_credentials, _flatten_settings, _env_overrides


def test_resolve_credentials_from_settings(monkeypatch):
    fake_settings = {
        "app_login": {"user": "123", "pass": "secret"},
        "evolution_api_key": "abc",
    }
    monkeypatch.setattr("app.automation.credentials._load_settings", lambda: fake_settings)
    creds = resolve_credentials()
    assert creds == fake_settings


def test_resolve_credentials_env_override_scalar(monkeypatch):
    monkeypatch.setenv("NAVRUNNER_EVOLUTION_API_KEY", "from-env")
    fake_settings = {"evolution_api_key": "from-db"}
    monkeypatch.setattr("app.automation.credentials._load_settings", lambda: fake_settings)
    creds = resolve_credentials()
    assert creds["evolution_api_key"] == "from-env"


def test_resolve_credentials_env_override_nested(monkeypatch):
    monkeypatch.setenv("NAVRUNNER_APP_LOGIN__USER", "from-env")
    fake_settings = {"app_login": {"user": "from-db", "pass": "secret"}}
    monkeypatch.setattr("app.automation.credentials._load_settings", lambda: fake_settings)
    creds = resolve_credentials()
    assert creds["app_login"]["user"] == "from-env"
    assert creds["app_login"]["pass"] == "secret"


def test_resolve_credentials_env_overrides_with_only_env_creates_dict(monkeypatch):
    """When env var defines a nested override but settings has no entry, the dict is created."""
    monkeypatch.setenv("NAVRUNNER_APP_LOGIN__USER", "from-env")
    monkeypatch.setattr("app.automation.credentials._load_settings", lambda: {})
    creds = resolve_credentials()
    assert creds["app_login"]["user"] == "from-env"


def test_flatten_settings_keeps_nested_dicts():
    settings = {"app_login": {"user": "u", "pass": "p"}, "evolution_api_key": "k"}
    out = _flatten_settings(settings)
    assert out == settings


def test_flatten_settings_raises_on_unsupported_type():
    with pytest.raises(TypeError, match="Unsupported"):
        _flatten_settings({"x": object()})


def test_env_overrides_ignores_unrelated_env_vars(monkeypatch):
    monkeypatch.setenv("PATH", "/foo")
    monkeypatch.setenv("HOME", "/bar")
    settings = {"app_login": {"user": "u"}}
    out = _env_overrides(settings)
    assert "PATH" not in out
    assert "HOME" not in out
    assert out["app_login"]["user"] == "u"