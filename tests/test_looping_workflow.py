
import pytest

from pydantic import ValidationError

from looping_workflow import (
    ShipmentInput,
    WorkflowState,
)

from looping_engine import (
    CarrierResponse,
    FakeCarrierAdapter,
    execute_looping_workflow,
)


def create_shipment(max_attempts=5):
    return ShipmentInput(
        shipment_id="SHIP-TEST-2001",
        carrier="TestCarrier",
        tracking_number="TRACK-TEST-2001",
        max_attempts=max_attempts,
        polling_interval_seconds=1,
    )


def test_happy_path_delivers_after_multiple_polls():
    shipment = create_shipment()

    carrier = FakeCarrierAdapter(
        responses=[
            {
                "status": "in_transit",
                "location": "Jaipur",
            },
            {
                "status": "in_transit",
                "location": "Udaipur",
            },
            {
                "status": "delivered",
                "location": "Customer Address",
            },
        ]
    )

    run, result = execute_looping_workflow(shipment, carrier)

    assert run.state == WorkflowState.COMPLETED
    assert result.delivered is True
    assert run.attempts == 3
    assert carrier.call_count == 3
    assert result.status == WorkflowState.COMPLETED


def test_maximum_attempt_limit_is_enforced():
    shipment = create_shipment(max_attempts=2)

    carrier = FakeCarrierAdapter(
        responses=[
            {"status": "in_transit", "location": "Hub A"},
            {"status": "in_transit", "location": "Hub B"},
            {"status": "delivered", "location": "Destination"},
        ]
    )

    run, result = execute_looping_workflow(shipment, carrier)

    assert run.state == WorkflowState.MAX_ATTEMPTS_REACHED
    assert run.attempts == 2
    assert carrier.call_count == 2
    assert result.delivered is False


def test_delayed_status_is_terminal():
    shipment = create_shipment()

    carrier = FakeCarrierAdapter(
        responses=[
            {
                "status": "delayed",
                "location": "Jaipur Hub",
                "message": "Weather disruption",
            }
        ]
    )

    run, result = execute_looping_workflow(shipment, carrier)

    assert run.state == WorkflowState.DELAYED
    assert run.attempts == 1
    assert result.delivered is False


def test_invalid_carrier_response_is_rejected():
    with pytest.raises(ValidationError):
        CarrierResponse.model_validate(
            {
                "status": "in_transit",
                "location": "Jaipur",
            }
        )


def test_unsupported_carrier_status_is_rejected():
    shipment = create_shipment()

    carrier = FakeCarrierAdapter(
        responses=[
            {
                "status": "unknown_status",
                "location": "Unknown Hub",
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match="Unsupported carrier status",
    ):
        execute_looping_workflow(shipment, carrier)


def test_zero_attempt_limit_is_rejected():
    with pytest.raises(ValidationError):
        create_shipment(max_attempts=0)
