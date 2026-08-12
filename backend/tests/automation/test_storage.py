from app.automation.storage import build_screenshot_key, build_screenshot_url


def test_build_screenshot_key_default_phase():
    key = build_screenshot_key("run-123", "submit")
    assert key == "automation-screenshots/run-123/submit_after.png"


def test_build_screenshot_key_on_fail_phase():
    key = build_screenshot_key("run-123", "submit", "on_fail")
    assert key == "automation-screenshots/run-123/submit_on_fail.png"


def test_build_screenshot_key_before_phase():
    key = build_screenshot_key("run-123", "submit", "before")
    assert key == "automation-screenshots/run-123/submit_before.png"


def test_build_screenshot_key_sanitizes_slashes_in_ids():
    key = build_screenshot_key("run/with/slashes", "step/id")
    # Slashes in ids become underscores (one level deep; we keep MinIO keys flat)
    assert key == "automation-screenshots/run_with_slashes/step_id_after.png"


def test_build_screenshot_url():
    assert build_screenshot_url("https://s3.x.com/", "x/y.png") == "https://s3.x.com/x/y.png"
    assert build_screenshot_url("https://s3.x.com", "x/y.png") == "https://s3.x.com/x/y.png"