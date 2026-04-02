from apps.runtime.runtime.recorder import normalize_event


def test_normalize_click_event():
    step = normalize_event({"type": "click", "selector": "#submit"})
    assert step["action"] == "click"
    assert step["selector"] == "#submit"
