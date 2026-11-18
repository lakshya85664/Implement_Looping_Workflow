
import json

import pytest

from looping_engine import FakeCarrierAdapter

from looping_observability import (
    ObservableCarrierAdapter,
    redact_secrets,
    save_observability_evidence,
)


def test_successful_poll_creates_structured_trace():
    fake = FakeCarrierAdapter([
        {
            "status": "in_transit",
            "location": "Jaipur",
        }
    ])

    observable = ObservableCarrierAdapter(fake)

    response = observable.poll("TRACK-OBS-001")

    assert response["status"] == "in_transit"
    assert len(observable.traces) == 1
    assert observable.traces[0]["event"] == "carrier_poll_succeeded"
    assert observable.traces[0]["next_action"] == "continue_workflow"


def test_poll_failure_is_traced_and_reraised():
    class FailingCarrier:
        def poll(self, tracking_number):
            raise TimeoutError("Carrier timeout")

    observable = ObservableCarrierAdapter(FailingCarrier())

    with pytest.raises(TimeoutError):
        observable.poll("TRACK-OBS-002")

    assert observable.metrics["poll_error_count"] == 1
    assert observable.traces[0]["outcome"] == "error"
    assert observable.traces[0]["next_action"] == "retry_or_review"


def test_metrics_report_counts_and_latency():
    fake = FakeCarrierAdapter([
        {"status": "in_transit", "location": "Hub A"},
        {"status": "delivered", "location": "Destination"},
    ])

    observable = ObservableCarrierAdapter(fake)

    observable.poll("TRACK-OBS-003")
    observable.poll("TRACK-OBS-003")

    report = observable.get_measurement_report(
        queue_age_ms=15.0,
        state_durations_ms={"running": 20.0},
    )

    assert report["poll_count"] == 2
    assert report["poll_success_count"] == 2
    assert report["poll_error_count"] == 0
    assert report["success_rate"] == 1.0
    assert report["average_latency_ms"] >= 0
    assert report["queue_age_ms"] == 15.0
    assert report["state_durations_ms"]["running"] == 20.0


def test_status_lookup_returns_latest_carrier_status():
    fake = FakeCarrierAdapter([
        {"status": "in_transit", "location": "Jaipur"},
        {"status": "delivered", "location": "Udaipur"},
    ])

    observable = ObservableCarrierAdapter(fake)

    observable.poll("TRACK-OBS-004")
    observable.poll("TRACK-OBS-004")

    status = observable.get_status("TRACK-OBS-004")

    assert status["status"] == "delivered"
    assert status["location"] == "Udaipur"


def test_unknown_tracking_number_returns_not_found():
    observable = ObservableCarrierAdapter(
        FakeCarrierAdapter([])
    )

    status = observable.get_status("UNKNOWN")

    assert status["status"] == "not_found"


def test_secret_redaction_is_recursive():
    data = {
        "api_key": "secret-value",
        "details": {
            "authorization": "Bearer token",
            "status": "delivered",
        },
        "items": [
            {"password": "hidden"},
        ],
    }

    cleaned = redact_secrets(data)

    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["details"]["authorization"] == "[REDACTED]"
    assert cleaned["details"]["status"] == "delivered"
    assert cleaned["items"][0]["password"] == "[REDACTED]"


def test_trace_does_not_expose_secrets():
    fake = FakeCarrierAdapter([
        {
            "status": "delivered",
            "location": "Destination",
            "api_key": "do-not-log-this",
        }
    ])

    observable = ObservableCarrierAdapter(fake)
    observable.poll("TRACK-OBS-005")

    trace_text = json.dumps(observable.traces)

    assert "do-not-log-this" not in trace_text
    assert "[REDACTED]" in trace_text


def test_evidence_files_are_generated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    fake = FakeCarrierAdapter([
        {"status": "delivered", "location": "Destination"}
    ])

    observable = ObservableCarrierAdapter(fake)
    observable.poll("TRACK-OBS-006")

    report = observable.get_measurement_report()

    trace_path, measurement_path = save_observability_evidence(
        observable,
        report,
    )

    assert trace_path.exists()
    assert measurement_path.exists()

    saved_trace = json.loads(trace_path.read_text(encoding="utf-8"))
    saved_metrics = json.loads(
        measurement_path.read_text(encoding="utf-8")
    )

    assert len(saved_trace) == 1
    assert saved_metrics["poll_count"] == 1
