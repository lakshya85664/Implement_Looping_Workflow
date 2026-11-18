
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from looping_engine import CarrierAdapter


# ---------------------------------------------------------
# 1. Secret redaction
# ---------------------------------------------------------

SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "token",
    "password",
    "secret",
}


def redact_secrets(value: Any) -> Any:
    """Return a copy with sensitive values redacted."""

    if isinstance(value, dict):
        cleaned = {}

        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = redact_secrets(item)

        return cleaned

    if isinstance(value, list):
        return [redact_secrets(item) for item in value]

    return value


# ---------------------------------------------------------
# 2. Observable carrier adapter
# ---------------------------------------------------------

class ObservableCarrierAdapter:
    def __init__(self, adapter: CarrierAdapter):
        self.adapter = adapter
        self.traces: list[dict[str, Any]] = []

        self.metrics = {
            "poll_count": 0,
            "poll_success_count": 0,
            "poll_error_count": 0,
            "total_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "attempt_count": 0,
        }

        self.status_by_tracking: dict[str, dict[str, Any]] = {}

    def poll(self, tracking_number: str) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        started_clock = time.perf_counter()

        self.metrics["poll_count"] += 1
        self.metrics["attempt_count"] += 1

        try:
            response = self.adapter.poll(tracking_number)

            elapsed_ms = (
                time.perf_counter() - started_clock
            ) * 1000

            self.metrics["poll_success_count"] += 1
            self._record_latency(elapsed_ms)

            safe_response = redact_secrets(response)

            self.status_by_tracking[tracking_number] = {
                "status": safe_response.get("status", "unknown"),
                "location": safe_response.get("location", "unknown"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            self.traces.append({
                "timestamp": started_at.isoformat(),
                "event": "carrier_poll_succeeded",
                "tracking_number": tracking_number,
                "outcome": "success",
                "latency_ms": round(elapsed_ms, 3),
                "details": safe_response,
                "next_action": "continue_workflow",
            })

            return response

        except Exception as exc:
            elapsed_ms = (
                time.perf_counter() - started_clock
            ) * 1000

            self.metrics["poll_error_count"] += 1
            self._record_latency(elapsed_ms)

            self.traces.append({
                "timestamp": started_at.isoformat(),
                "event": "carrier_poll_failed",
                "tracking_number": tracking_number,
                "outcome": "error",
                "error_type": type(exc).__name__,
                "latency_ms": round(elapsed_ms, 3),
                "next_action": "retry_or_review",
            })

            raise

    def _record_latency(self, elapsed_ms: float) -> None:
        self.metrics["total_latency_ms"] += elapsed_ms
        self.metrics["max_latency_ms"] = max(
            self.metrics["max_latency_ms"],
            elapsed_ms,
        )

    def get_status(self, tracking_number: str) -> dict[str, Any]:
        return self.status_by_tracking.get(
            tracking_number,
            {
                "status": "not_found",
                "location": None,
                "updated_at": None,
            },
        )

    def get_measurement_report(
        self,
        queue_age_ms: float = 0.0,
        state_durations_ms: dict[str, float] | None = None,
    ) -> dict[str, Any]:

        count = self.metrics["poll_count"]

        average_latency = (
            self.metrics["total_latency_ms"] / count
            if count else 0.0
        )

        success_rate = (
            self.metrics["poll_success_count"] / count
            if count else 0.0
        )

        return {
            **self.metrics,
            "average_latency_ms": round(average_latency, 3),
            "max_latency_ms": round(
                self.metrics["max_latency_ms"], 3
            ),
            "success_rate": round(success_rate, 4),
            "queue_age_ms": round(queue_age_ms, 3),
            "state_durations_ms": state_durations_ms or {},
        }


# ---------------------------------------------------------
# 3. Evidence generation
# ---------------------------------------------------------

def save_observability_evidence(
    adapter: ObservableCarrierAdapter,
    measurement_report: dict[str, Any],
) -> tuple[Path, Path]:

    output_dir = Path("outputs")
    trace_dir = Path("traces")

    output_dir.mkdir(exist_ok=True)
    trace_dir.mkdir(exist_ok=True)

    trace_path = trace_dir / "task4_looping_observability.json"
    measurement_path = (
        output_dir / "task4_looping_measurements.json"
    )

    safe_traces = redact_secrets(adapter.traces)

    trace_path.write_text(
        json.dumps(safe_traces, indent=4),
        encoding="utf-8",
    )

    measurement_path.write_text(
        json.dumps(measurement_report, indent=4),
        encoding="utf-8",
    )

    return trace_path, measurement_path


# ---------------------------------------------------------
# 4. Runnable observability demonstration
# ---------------------------------------------------------

def run_observability_demo() -> None:

    from looping_engine import FakeCarrierAdapter

    fake_carrier = FakeCarrierAdapter(
        responses=[
            {
                "status": "in_transit",
                "location": "Jaipur Hub",
                "api_key": "demo-secret-not-for-logs",
            },
            {
                "status": "delivered",
                "location": "Udaipur",
                "authorization": "Bearer demo-token",
            },
        ]
    )

    observable = ObservableCarrierAdapter(fake_carrier)

    first = observable.poll("TRACK-OBS-001")
    second = observable.poll("TRACK-OBS-001")

    status = observable.get_status("TRACK-OBS-001")

    measurements = observable.get_measurement_report(
        queue_age_ms=12.5,
        state_durations_ms={
            "running": 18.2,
            "waiting": 10.0,
            "completed": 1.1,
        },
    )

    trace_path, measurement_path = save_observability_evidence(
        observable,
        measurements,
    )

    print("=" * 60)
    print("TASK 4 - LOOPING WORKFLOW OBSERVABILITY")
    print("=" * 60)
    print(f"First carrier status: {first['status']}")
    print(f"Second carrier status: {second['status']}")
    print(f"Status lookup: {json.dumps(status)}")
    print(f"Poll count: {measurements['poll_count']}")
    print(f"Success count: {measurements['poll_success_count']}")
    print(f"Error count: {measurements['poll_error_count']}")
    print(f"Success rate: {measurements['success_rate']}")
    print(f"Average latency: {measurements['average_latency_ms']} ms")
    print(f"Queue age: {measurements['queue_age_ms']} ms")
    print(f"Trace saved: {trace_path}")
    print(f"Measurements saved: {measurement_path}")

    print("\nRedacted traces:")
    print(json.dumps(observable.traces, indent=4))

    assert "demo-secret-not-for-logs" not in json.dumps(
        observable.traces
    )
    assert "Bearer demo-token" not in json.dumps(
        observable.traces
    )


if __name__ == "__main__":
    run_observability_demo()
