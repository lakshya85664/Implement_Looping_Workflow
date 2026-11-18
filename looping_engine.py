
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, Any

from pydantic import BaseModel, Field

from looping_workflow import (
    ShipmentInput,
    WorkflowRun,
    WorkflowState,
    WorkflowResult,
    transition,
)


# ---------------------------------------------------------
# 1. Validate carrier responses
# ---------------------------------------------------------

class CarrierResponse(BaseModel):
    tracking_number: str = Field(min_length=1)
    status: str
    location: str = "Unknown"
    message: str = ""


VALID_CARRIER_STATUSES = {
    "in_transit",
    "delivered",
    "delayed",
}


# ---------------------------------------------------------
# 2. External carrier adapter contract
# ---------------------------------------------------------

class CarrierAdapter(Protocol):
    def poll(self, tracking_number: str) -> dict[str, Any]:
        ...


# ---------------------------------------------------------
# 3. Deterministic fake carrier
# ---------------------------------------------------------

class FakeCarrierAdapter:
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = responses
        self.call_count = 0

    def poll(self, tracking_number: str) -> dict[str, Any]:
        self.call_count += 1

        index = self.call_count - 1

        if index >= len(self.responses):
            return {
                "tracking_number": tracking_number,
                "status": "in_transit",
                "location": "Last known hub",
                "message": "No new carrier update",
            }

        response = dict(self.responses[index])
        response.setdefault("tracking_number", tracking_number)

        return response


# ---------------------------------------------------------
# 4. Main looping workflow
# ---------------------------------------------------------

def execute_looping_workflow(
    shipment: ShipmentInput,
    carrier: CarrierAdapter,
) -> tuple[WorkflowRun, WorkflowResult]:

    run = WorkflowRun(
        run_id=f"RUN-{shipment.shipment_id}",
        shipment=shipment,
    )

    transition(run, "start")

    run.record_event(
        "workflow.started",
        shipment_id=shipment.shipment_id,
        max_attempts=shipment.max_attempts,
    )

    while run.state == WorkflowState.RUNNING:

        # Hard loop limit: no more than max_attempts polls.
        if run.attempts >= shipment.max_attempts:
            transition(run, "limit_reached")
            break

        run.attempts += 1

        run.record_event(
            "poll.started",
            attempt=run.attempts,
        )

        run.record_trace(
            "carrier_poll_started",
            tracking_number=shipment.tracking_number,
        )

        # Call the injected carrier dependency.
        raw_response = carrier.poll(shipment.tracking_number)

        # Validate the external response before using it.
        response = CarrierResponse.model_validate(raw_response)

        if response.status not in VALID_CARRIER_STATUSES:
            raise ValueError(
                f"Unsupported carrier status: {response.status}"
            )

        run.record_event(
            "poll.completed",
            attempt=run.attempts,
            carrier_status=response.status,
            location=response.location,
        )

        run.record_trace(
            "carrier_poll_completed",
            carrier_status=response.status,
            location=response.location,
        )

        if response.status == "delivered":
            transition(run, "delivered")
            break

        if response.status == "delayed":
            transition(run, "delayed")
            break

        # Shipment is still in transit.
        if run.attempts >= shipment.max_attempts:
            transition(run, "limit_reached")
            break

        # Pause and resume to represent the next polling cycle.
        transition(run, "wait")
        transition(run, "resume")

    delivered = run.state == WorkflowState.COMPLETED

    if run.state == WorkflowState.COMPLETED:
        message = "Shipment delivered successfully."
    elif run.state == WorkflowState.DELAYED:
        message = "Carrier reported a shipment delay."
    elif run.state == WorkflowState.MAX_ATTEMPTS_REACHED:
        message = "Maximum polling attempts reached."
    else:
        message = "Workflow requires operator review."

    result = WorkflowResult(
        shipment_id=shipment.shipment_id,
        status=run.state,
        attempts=run.attempts,
        message=message,
        delivered=delivered,
    )

    run.result = result

    run.record_event(
        "workflow.finished",
        final_status=run.state.value,
        attempts=run.attempts,
    )

    run.record_trace(
        "workflow_finished",
        final_status=run.state.value,
        delivered=delivered,
    )

    return run, result


# ---------------------------------------------------------
# 5. JSON evidence generation
# ---------------------------------------------------------

def save_happy_path_evidence(
    run: WorkflowRun,
    result: WorkflowResult,
) -> Path:

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / "task2_looping_workflow.json"

    evidence = {
        "run_id": run.run_id,
        "shipment": run.shipment.model_dump(mode="json"),
        "final_state": run.state.value,
        "attempts": run.attempts,
        "result": result.model_dump(mode="json"),
        "events": [
            event.model_dump(mode="json")
            for event in run.events
        ],
        "traces": [
            trace.model_dump(mode="json")
            for trace in run.traces
        ],
    }

    output_path.write_text(
        json.dumps(evidence, indent=4),
        encoding="utf-8",
    )

    return output_path


# ---------------------------------------------------------
# 6. Runnable deterministic happy path
# ---------------------------------------------------------

def run_happy_path() -> None:

    shipment = ShipmentInput(
        shipment_id="SHIP-2001",
        carrier="DemoCarrier",
        tracking_number="TRACK-2001",
        max_attempts=5,
        polling_interval_seconds=10,
    )

    fake_carrier = FakeCarrierAdapter(
        responses=[
            {
                "status": "in_transit",
                "location": "Jaipur Hub",
                "message": "Shipment is moving",
            },
            {
                "status": "in_transit",
                "location": "Udaipur Hub",
                "message": "Shipment is out for delivery",
            },
            {
                "status": "delivered",
                "location": "Customer Address",
                "message": "Shipment delivered",
            },
        ]
    )

    run, result = execute_looping_workflow(
        shipment,
        fake_carrier,
    )

    output_path = save_happy_path_evidence(run, result)

    print("=" * 60)
    print("TASK 2 - LOOPING WORKFLOW EXECUTION")
    print("=" * 60)
    print(f"Run ID: {run.run_id}")
    print(f"Shipment ID: {shipment.shipment_id}")
    print(f"Final state: {run.state.value}")
    print(f"Polling attempts: {run.attempts}")
    print(f"Carrier calls: {fake_carrier.call_count}")
    print(f"Delivered: {result.delivered}")
    print(f"Message: {result.message}")
    print(f"Evidence saved: {output_path}")

    print("\nFinal result:")
    print(json.dumps(result.model_dump(mode="json"), indent=4))


if __name__ == "__main__":
    run_happy_path()
