from apps.runtime.runtime.player import build_delivery_payload


def test_build_delivery_payload():
    payload = build_delivery_payload(run_id="run-1", destination="webhook", extracted_data={"rows": 2})
    assert payload["destination"] == "webhook"
    assert payload["run_id"] == "run-1"
