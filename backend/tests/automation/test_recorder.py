import json
from pathlib import Path

import pytest

from app.automation.recorder import (
    parse_trace_file,
    parse_trace_json,
    steps_from_trace,
    NavRecorderError,
)


# A minimal Playwright trace that covers goto, click, fill, change, screenshot.
SAMPLE_TRACE = {
    "title": "cotacao_pvs sample trace",
    "startTime": "2026-08-12T10:00:00.000Z",
    "actions": [
        {"type": "navigate", "url": "https://app.apvs.vc/home"},
        {"type": "click", "selector": "ion-button:has-text(\"SOU CONSULTOR APVS\")"},
        {"type": "type", "selector": "input[type=text]", "value": "19.186.569/0001-11"},
        {"type": "type", "selector": "input[type=password]", "value": "Macedo020589#"},
        {"type": "click", "selector": "ion-button:has-text(\"Entrar\")"},
        {"type": "wait_for", "selector": ".dashboard"},
    ],
}


def _write_trace(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "trace.json"
    p.write_text(json.dumps(payload))
    return p


def test_parse_trace_json_returns_actions(tmp_path):
    p = _write_trace(tmp_path, SAMPLE_TRACE)
    parsed = parse_trace_file(p)
    assert parsed["title"] == SAMPLE_TRACE["title"]
    assert len(parsed["actions"]) == 6


def test_parse_trace_file_raises_on_missing(tmp_path):
    with pytest.raises(NavRecorderError, match="not found"):
        parse_trace_file(tmp_path / "missing.json")


def test_parse_trace_file_raises_on_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json at all")
    with pytest.raises(NavRecorderError, match="invalid JSON"):
        parse_trace_file(p)


def test_steps_from_trace_basic_actions():
    out = steps_from_trace(SAMPLE_TRACE)
    steps = out["steps"]
    assert len(steps) >= 1
    # The login block is now top-level, not a step.
    assert "login_block" not in steps[0]


def test_steps_from_trace_detects_login_block():
    """The first sequence of navigate -> click(button with CONSULTOR) -> 2 fills ->
    click(button Entrar) -> wait_for dashboard is detected as form_login auth."""
    out = steps_from_trace(SAMPLE_TRACE)
    assert "auth" in out
    auth = out["auth"]
    assert auth["credentials_ref"].startswith("apvs_login")
    assert auth["success_assert"]["selector"] == ".dashboard"


def test_steps_from_trace_includes_wait_for():
    out = steps_from_trace(SAMPLE_TRACE)
    wait_steps = [s for s in out["steps"] if "wait_for" in s]
    assert any(w["id"].startswith("wait_") for w in wait_steps)


def test_steps_from_trace_handles_empty():
    out = steps_from_trace({"actions": []})
    assert out["steps"] == []
    assert out["automation_name"]  # some default


def test_steps_from_trace_normalizes_clicks():
    trace = {"actions": [
        {"type": "navigate", "url": "https://x.com"},
        {"type": "click", "selector": "button.go"},
    ]}
    out = steps_from_trace(trace)
    click_steps = [s for s in out["steps"] if "click" in s and "wait_for" not in s]
    assert len(click_steps) == 1
    assert click_steps[0]["click"]["selector"] == "button.go"


def test_steps_from_trace_groups_fill_actions():
    trace = {"actions": [
        {"type": "navigate", "url": "https://x.com"},
        {"type": "type", "selector": "#a", "value": "1"},
        {"type": "type", "selector": "#b", "value": "2"},
        {"type": "type", "selector": "#c", "value": "3"},
    ]}
    out = steps_from_trace(trace)
    fill_steps = [s for s in out["steps"] if "fill" in s]
    assert len(fill_steps) >= 1
    if len(fill_steps) == 1:
        assert "#a" in fill_steps[0]["fill"]
        assert "#b" in fill_steps[0]["fill"]
        assert "#c" in fill_steps[0]["fill"]


def test_steps_from_trace_extracts_title_as_automation_name():
    trace = {"title": "cotacao_pvs", "actions": [{"type": "navigate", "url": "x"}]}
    out = steps_from_trace(trace)
    assert out["automation_name"] == "cotacao_pvs"
    assert "steps" in out


def test_steps_from_trace_default_automation_name_from_url():
    trace = {"actions": [{"type": "navigate", "url": "https://app.apvs.vc/dashboard"}]}
    out = steps_from_trace(trace)
    assert out["automation_name"] == "app_apvs_vc"
