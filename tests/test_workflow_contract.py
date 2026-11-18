
import pytest

from looping_workflow import (
    ShipmentInput,
    WorkflowRun,
    WorkflowState,
    transition,
)


def create_test_run():
    shipment = ShipmentInput(
        shipment_id="SHIP-TEST-001",
        carrier="TestCarrier",
        tracking_number="TEST-TRACK-001",
        max_attempts=3
    )

    return WorkflowRun(
        run_id="RUN-TEST-001",
        shipment=shipment
    )


def test_legal_start_transition():
    run = create_test_run()

    transition(run, "start")

    assert run.state == WorkflowState.RUNNING
    assert len(run.events) == 1
    assert len(run.traces) == 1


def test_illegal_transition_is_rejected():
    run = create_test_run()

    with pytest.raises(ValueError, match="Illegal transition"):
        transition(run, "delivered")


def test_wait_and_resume_transitions():
    run = create_test_run()

    transition(run, "start")
    transition(run, "wait")

    assert run.state == WorkflowState.WAITING

    transition(run, "resume")

    assert run.state == WorkflowState.RUNNING


def test_terminal_states_are_defined():
    terminal_states = {
        WorkflowState.COMPLETED,
        WorkflowState.DELAYED,
        WorkflowState.MAX_ATTEMPTS_REACHED,
        WorkflowState.NEEDS_REVIEW,
    }

    assert len(terminal_states) == 4


def test_invalid_shipment_input():
    with pytest.raises(ValueError):
        ShipmentInput(
            shipment_id="",
            carrier="TestCarrier",
            tracking_number="TEST-TRACK-001",
            max_attempts=3
        )


def test_attempt_limit_must_be_positive():
    with pytest.raises(ValueError):
        ShipmentInput(
            shipment_id="SHIP-TEST-002",
            carrier="TestCarrier",
            tracking_number="TEST-TRACK-002",
            max_attempts=0
        )
