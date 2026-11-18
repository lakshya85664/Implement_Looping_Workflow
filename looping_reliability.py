
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from looping_engine import (
    CarrierAdapter,
    CarrierResponse,
    VALID_CARRIER_STATUSES,
)


# ---------------------------------------------------------
# 1. Error classification
# ---------------------------------------------------------

class TransientCarrierError(Exception):
    """An error that may succeed if the request is retried."""


class PermanentCarrierError(Exception):
    """An error that should not be retried."""


class CarrierTimeoutError(TransientCarrierError):
    """The carrier did not respond within the allowed time."""


class QuarantinedCarrierResponse(Exception):
    """The carrier response failed validation."""


# ---------------------------------------------------------
# 2. Retrying carrier adapter
# ---------------------------------------------------------

class RetryingCarrierAdapter:
    def __init__(
        self,
        adapter: CarrierAdapter,
        max_retries: int = 2,
    ):
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.adapter = adapter
        self.max_retries = max_retries
        self.trace: list[dict[str, Any]] = []

    def poll(self, tracking_number: str) -> dict[str, Any]:

        total_attempts = self.max_retries + 1

        for attempt in range(1, total_attempts + 1):

            try:
                raw_response = self.adapter.poll(tracking_number)

                # Validate the response before returning it.
                response = CarrierResponse.model_validate(raw_response)

                if response.status not in VALID_CARRIER_STATUSES:
                    raise QuarantinedCarrierResponse(
                        f"Unsupported status: {response.status}"
                    )

                self.trace.append({
                    "event": "carrier_poll_succeeded",
                    "attempt": attempt,
                    "outcome": "success",
                    "next_action": "continue_workflow",
                })

                return response.model_dump()

            except (TransientCarrierError, TimeoutError) as exc:

                final_attempt = attempt == total_attempts

                self.trace.append({
                    "event": "carrier_poll_retry",
                    "attempt": attempt,
                    "outcome": "timeout" if isinstance(
                        exc, TimeoutError
                    ) else "transient_error",
                    "error_type": type(exc).__name__,
                    "next_action": (
                        "needs_review"
                        if final_attempt
                        else "retry"
                    ),
                })

                if final_attempt:
                    raise PermanentCarrierError(
                        f"Retry limit exhausted: {exc}"
                    ) from exc

            except QuarantinedCarrierResponse as exc:
                self.trace.append({
                    "event": "carrier_response_quarantined",
                    "attempt": attempt,
                    "outcome": "invalid_response",
                    "error_type": type(exc).__name__,
                    "next_action": "needs_review",
                })
                raise

            except ValidationError as exc:
                self.trace.append({
                    "event": "carrier_response_quarantined",
                    "attempt": attempt,
                    "outcome": "malformed_response",
                    "error_type": type(exc).__name__,
                    "next_action": "needs_review",
                })
                raise QuarantinedCarrierResponse(
                    "Carrier returned a malformed response"
                ) from exc

            except PermanentCarrierError as exc:
                self.trace.append({
                    "event": "carrier_poll_failed",
                    "attempt": attempt,
                    "outcome": "permanent_error",
                    "error_type": type(exc).__name__,
                    "next_action": "needs_review",
                })
                raise

        raise PermanentCarrierError("Unexpected retry termination")


# ---------------------------------------------------------
# 3. Duplicate run protection
# ---------------------------------------------------------

class DuplicateRunError(Exception):
    pass


class RunRegistry:
    def __init__(self):
        self.claimed_runs: set[str] = set()

    def claim(self, run_id: str) -> None:
        if run_id in self.claimed_runs:
            raise DuplicateRunError(
                f"Duplicate workflow trigger blocked: {run_id}"
            )

        self.claimed_runs.add(run_id)


# ---------------------------------------------------------
# 4. Idempotency ledger for protected side effects
# ---------------------------------------------------------

class IdempotencyLedger:
    def __init__(self):
        self.results: dict[str, Any] = {}

    def execute_once(
        self,
        idempotency_key: str,
        action: Callable[[], Any],
    ) -> Any:

        if idempotency_key in self.results:
            return self.results[idempotency_key]

        result = action()
        self.results[idempotency_key] = result

        return result


# ---------------------------------------------------------
# 5. Fake protected delivery notification
# ---------------------------------------------------------

class FakeDeliveryNotifier:
    def __init__(self):
        self.side_effect_count = 0

    def notify(self, shipment_id: str) -> dict[str, str]:
        self.side_effect_count += 1

        return {
            "shipment_id": shipment_id,
            "notification": "delivery_confirmed",
            "status": "sent",
        }


# ---------------------------------------------------------
# 6. Save recovery evidence
# ---------------------------------------------------------

def save_recovery_evidence(
    trace: list[dict[str, Any]],
    side_effect_count: int,
    final_status: str,
) -> Path:

    output_dir = Path("outputs")
    trace_dir = Path("traces")

    output_dir.mkdir(exist_ok=True)
    trace_dir.mkdir(exist_ok=True)

    evidence = {
        "final_status": final_status,
        "trace_entries": len(trace),
        "trace": trace,
        "protected_side_effect_count": side_effect_count,
    }

    output_path = output_dir / "task3_failure_recovery.json"
    trace_path = trace_dir / "task3_recovery_trace.json"

    output_path.write_text(
        json.dumps(evidence, indent=4),
        encoding="utf-8",
    )

    trace_path.write_text(
        json.dumps(trace, indent=4),
        encoding="utf-8",
    )

    return output_path


# ---------------------------------------------------------
# 7. Demonstration of retry and replay safety
# ---------------------------------------------------------

class SequenceFailureAdapter:
    """Fake adapter that raises configured outcomes in sequence."""

    def __init__(self, outcomes: list[Any]):
        self.outcomes = outcomes
        self.call_count = 0

    def poll(self, tracking_number: str) -> dict[str, Any]:
        outcome = self.outcomes[self.call_count]
        self.call_count += 1

        if isinstance(outcome, Exception):
            raise outcome

        return {
            "tracking_number": tracking_number,
            **outcome,
        }


def run_recovery_demo() -> None:

    fake_adapter = SequenceFailureAdapter([
        TransientCarrierError("Temporary carrier connection issue"),
        CarrierTimeoutError("Carrier response timed out"),
        {
            "status": "delivered",
            "location": "Customer Address",
        },
    ])

    retrying_adapter = RetryingCarrierAdapter(
        fake_adapter,
        max_retries=2,
    )

    response = retrying_adapter.poll("TRACK-RECOVERY-001")

    registry = RunRegistry()
    registry.claim("RUN-RECOVERY-001")

    try:
        registry.claim("RUN-RECOVERY-001")
    except DuplicateRunError as exc:
        print(f"Duplicate trigger blocked: {exc}")

    ledger = IdempotencyLedger()
    notifier = FakeDeliveryNotifier()

    notification_key = "RUN-RECOVERY-001:delivery_notification"

    first_result = ledger.execute_once(
        notification_key,
        lambda: notifier.notify("SHIP-RECOVERY-001"),
    )

    replay_result = ledger.execute_once(
        notification_key,
        lambda: notifier.notify("SHIP-RECOVERY-001"),
    )

    assert first_result == replay_result
    assert notifier.side_effect_count == 1

    output_path = save_recovery_evidence(
        retrying_adapter.trace,
        notifier.side_effect_count,
        response["status"],
    )

    print("=" * 60)
    print("TASK 3 - FAILURE AND REPLAY RECOVERY")
    print("=" * 60)
    print(f"Carrier calls: {fake_adapter.call_count}")
    print(f"Carrier status: {response['status']}")
    print(f"Retry trace entries: {len(retrying_adapter.trace)}")
    print(f"Notification side effects: {notifier.side_effect_count}")
    print(f"Replay returned cached result: {replay_result == first_result}")
    print(f"Evidence saved: {output_path}")

    print("\nRecovery trace:")
    print(json.dumps(retrying_adapter.trace, indent=4))


if __name__ == "__main__":
    run_recovery_demo()
