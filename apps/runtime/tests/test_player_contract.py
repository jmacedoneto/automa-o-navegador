from apps.runtime.runtime.player import build_run_summary


def test_build_run_summary():
    summary = build_run_summary(steps_completed=3, total_steps=4, status="running")
    assert summary["steps_completed"] == 3
    assert summary["status"] == "running"
