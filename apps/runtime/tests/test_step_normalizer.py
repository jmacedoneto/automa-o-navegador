from apps.runtime.runtime.recorder import normalize_event


def test_normalize_click_event():
    step = normalize_event({"type": "click", "selector": "#submit"})
    assert step["action"] == "click"
    assert step["selector"] == "#submit"


def test_normalize_event_preserves_runtime_metadata():
    step = normalize_event(
        {
            "type": "navigate",
            "url": "https://example.com",
            "metadata": {"source": "chrome"},
        }
    )

    assert step["url"] == "https://example.com"
    assert step["metadata"] == {"source": "chrome"}
