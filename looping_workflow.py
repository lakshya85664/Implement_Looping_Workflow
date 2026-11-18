
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------
# 1. Workflow states
# ---------------------------------------------------------

class WorkflowState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    DELAYED = "delayed"
    MAX_ATTEMPTS_REACHED = "max_attempts_reached"
    NEEDS_REVIEW = "needs_review"


# ---------------------------------------------------------
# 2. Shipment input model
# ---------------------------------------------------------

class ShipmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str = Field(min_length=1)
    carrier: str = Field(min_length=1)
    tracking_number: str = Field(min_length=1)
    max_attempts: int = Field(default=5, ge=1, le=100)
    polling_interval_seconds: int = Field(default=10, ge=1)


# ---------------------------------------------------------
# 3. Event model
# ---------------------------------------------------------

class WorkflowEvent(BaseModel):
    event_id: str
    event_type: str
    run_id: str
    state: WorkflowState
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------
# 4. Task model
# ---------------------------------------------------------

class PollingTask(BaseModel):
    task_id: str
    task_type: str = "carrier_poll"
    attempt: int = Field(default=0, ge=0)
    status: str = "pending"
    owner: str = "workflow_engine"
    result: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------
# 5. Result model
# ---------------------------------------------------------

class WorkflowResult(BaseModel):
    shipment_id: str
    status: WorkflowState
    attempts: int
    message: str
    delivered: bool = False


# ---------------------------------------------------------
# 6. Trace model
# ---------------------------------------------------------

class WorkflowTrace(BaseModel):
    run_id: str
    shipment_id: str
    event_type: str
    state: WorkflowState
    attempt: int
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------
# 7. Workflow run model
# ---------------------------------------------------------

class WorkflowRun(BaseModel):
    run_id: str
    shipment: ShipmentInput
    state: WorkflowState = WorkflowState.CREATED
    attempts: int = 0
    current_task: PollingTask | None = None
    events: list[WorkflowEvent] = Field(default_factory=list)
    traces: list[WorkflowTrace] = Field(default_factory=list)
    result: WorkflowResult | None = None

    def record_event(
        self,
        event_type: str,
        **details: Any
    ) -> None:
        event = WorkflowEvent(
            event_id=f"EVT-{len(self.events) + 1:04d}",
            event_type=event_type,
            run_id=self.run_id,
            state=self.state,
            details=details
        )
        self.events.append(event)

    def record_trace(
        self,
        event_type: str,
        **details: Any
    ) -> None:
        trace = WorkflowTrace(
            run_id=self.run_id,
            shipment_id=self.shipment.shipment_id,
            event_type=event_type,
            state=self.state,
            attempt=self.attempts,
            details=details
        )
        self.traces.append(trace)


# ---------------------------------------------------------
# 8. Legal state transitions
# ---------------------------------------------------------

LEGAL_TRANSITIONS = {
    (WorkflowState.CREATED, "start"): WorkflowState.RUNNING,

    (WorkflowState.RUNNING, "poll"): WorkflowState.RUNNING,
    (WorkflowState.RUNNING, "wait"): WorkflowState.WAITING,
    (WorkflowState.WAITING, "resume"): WorkflowState.RUNNING,

    (WorkflowState.RUNNING, "delivered"): WorkflowState.COMPLETED,
    (WorkflowState.RUNNING, "delayed"): WorkflowState.DELAYED,
    (WorkflowState.RUNNING, "limit_reached"):
        WorkflowState.MAX_ATTEMPTS_REACHED,

    (WorkflowState.RUNNING, "fail"): WorkflowState.NEEDS_REVIEW,
    (WorkflowState.WAITING, "fail"): WorkflowState.NEEDS_REVIEW,
}


# ---------------------------------------------------------
# 9. State transition function
# ---------------------------------------------------------

def transition(
    run: WorkflowRun,
    event: str
) -> WorkflowRun:

    next_state = LEGAL_TRANSITIONS.get((run.state, event))

    if next_state is None:
        raise ValueError(
            f"Illegal transition: {run.state.value} + {event}"
        )

    previous_state = run.state
    run.state = next_state

    run.record_event(
        event,
        previous_state=previous_state.value,
        next_state=next_state.value
    )

    run.record_trace(
        "state_transition",
        event=event,
        previous_state=previous_state.value,
        next_state=next_state.value
    )

    return run


# ---------------------------------------------------------
# 10. Runnable Task 1 fixture
# ---------------------------------------------------------

def run_topic_fixture() -> dict[str, Any]:

    shipment = ShipmentInput(
        shipment_id="SHIP-1001",
        carrier="DemoCarrier",
        tracking_number="TRACK-1001",
        max_attempts=5,
        polling_interval_seconds=10
    )

    run = WorkflowRun(
        run_id="RUN-LOOP-001",
        shipment=shipment
    )

    transition(run, "start")
    run.record_event(
        "topic.started",
        topic="Implement Looping Workflow"
    )

    return {
        "run_id": run.run_id,
        "shipment_id": shipment.shipment_id,
        "state": run.state.value,
        "attempts": run.attempts,
        "events": [
            event.model_dump(mode="json")
            for event in run.events
        ],
        "traces": [
            trace.model_dump(mode="json")
            for trace in run.traces
        ]
    }


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("TOPIC 6 - LOOPING WORKFLOW CONTRACT")
    print("=" * 60)

    print(json.dumps(run_topic_fixture(), indent=4))
