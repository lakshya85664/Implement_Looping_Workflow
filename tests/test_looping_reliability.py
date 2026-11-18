
import pytest

from looping_reliability import (
    TransientCarrierError,
    CarrierTimeoutError,
    PermanentCarrierError,
    QuarantinedCarrierResponse,
    DuplicateRunError,
    RetryingCarrierAdapter,
    RunRegistry,
    IdempotencyLedger,
    FakeDeliveryNotifier,
    SequenceFailureAdapter,
)


def test_transient_error_and_timeout_retry_then_succeed():
    adapter = SequenceFailureAdapter([
        TransientCarrierError("Temporary error"),
        CarrierTimeoutError("Timeout"),
        {
            "status": "delivered",
            "location": "Destination",
        },
    ])

    retrying = RetryingCarrierAdapter(adapter, max_retries=2)

    response = retrying.poll("TRACK-001")

    assert response["status"] == "delivered"
    assert adapter.call_count == 3
    assert len(retrying.trace) == 3
    assert retrying.trace[-1]["next_action"] == "continue_workflow"


def test_retry_exhaustion_stops_after_bounded_attempts():
    adapter = SequenceFailureAdapter([
        TransientCarrierError("Error one"),
        TransientCarrierError("Error two"),
        TransientCarrierError("Error three"),
        {
            "status": "delivered",
            "location": "Destination",
        },
    ])

    retrying = RetryingCarrierAdapter(adapter, max_retries=2)

    with pytest.raises(PermanentCarrierError, match="Retry limit exhausted"):
        retrying.poll("TRACK-002")

    assert adapter.call_count == 3
    assert retrying.trace[-1]["next_action"] == "needs_review"



def test_malformed_carrier_response_is_quarantined():
    adapter = SequenceFailureAdapter([
        {
            # Missing required status field.
            "location": "Hub A",
        }
    ])

    retrying = RetryingCarrierAdapter(adapter, max_retries=2)

    with pytest.raises(QuarantinedCarrierResponse):
        retrying.poll("TRACK-003")

    assert adapter.call_count == 1
    assert retrying.trace[0]["next_action"] == "needs_review"



def test_unsupported_status_is_quarantined():
    adapter = SequenceFailureAdapter([
        {
            "status": "unknown",
            "location": "Hub A",
        }
    ])

    retrying = RetryingCarrierAdapter(adapter)

    with pytest.raises(QuarantinedCarrierResponse):
        retrying.poll("TRACK-004")

    assert adapter.call_count == 1


def test_duplicate_workflow_trigger_is_blocked():
    registry = RunRegistry()

    registry.claim("RUN-001")

    with pytest.raises(DuplicateRunError):
        registry.claim("RUN-001")


def test_idempotency_prevents_duplicate_side_effect():
    ledger = IdempotencyLedger()
    notifier = FakeDeliveryNotifier()

    key = "RUN-001:delivery_notification"

    first = ledger.execute_once(
        key,
        lambda: notifier.notify("SHIP-001"),
    )

    second = ledger.execute_once(
        key,
        lambda: notifier.notify("SHIP-001"),
    )

    assert first == second
    assert notifier.side_effect_count == 1


def test_permanent_error_is_not_retried():
    class PermanentFailureAdapter:
        def __init__(self):
            self.call_count = 0

        def poll(self, tracking_number):
            self.call_count += 1
            raise PermanentCarrierError("Invalid carrier account")

    adapter = PermanentFailureAdapter()
    retrying = RetryingCarrierAdapter(adapter, max_retries=3)

    with pytest.raises(PermanentCarrierError):
        retrying.poll("TRACK-005")

    assert adapter.call_count == 1


def test_negative_retry_limit_is_rejected():
    adapter = SequenceFailureAdapter([])

    with pytest.raises(ValueError, match="max_retries"):
        RetryingCarrierAdapter(adapter, max_retries=-1)
