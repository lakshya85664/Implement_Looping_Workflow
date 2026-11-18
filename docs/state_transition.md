
# Looping Workflow — State Transition Model

## Workflow States

| State | Description | Terminal |
|---|---|---|
| created | Workflow has been initialized | No |
| running | Carrier polling is in progress | No |
| waiting | Workflow is waiting before the next poll | No |
| completed | Shipment has been delivered | Yes |
| delayed | Carrier has reported a shipment delay | Yes |
| max_attempts_reached | Maximum polling attempts have been exhausted | Yes |
| needs_review | An unrecoverable error requires operator attention | Yes |

## Legal Transitions

| Current State | Event | Next State |
|---|---|---|
| created | start | running |
| running | poll | running |
| running | wait | waiting |
| waiting | resume | running |
| running | delivered | completed |
| running | delayed | delayed |
| running | limit_reached | max_attempts_reached |
| running | fail | needs_review |
| waiting | fail | needs_review |

## State Diagram

```text
                 start
    CREATED ----------------> RUNNING
                                  |
                     +------------+------------+
                     |            |            |
                    poll         wait       delivered
                     |            |            |
                     v            v            v
                  RUNNING      WAITING     COMPLETED
                                  |
                                resume
                                  |
                                  v
                                RUNNING

RUNNING -- delayed ------> DELAYED
RUNNING -- limit_reached -> MAX_ATTEMPTS_REACHED
RUNNING -- fail ----------> NEEDS_REVIEW
WAITING -- fail ----------> NEEDS_REVIEW
```

## Design Notes

- The workflow begins in the `created` state.
- The `start` event activates carrier polling.
- The `poll` event allows another polling cycle.
- The `wait` and `resume` events represent the pause between polling cycles.
- Delivered, delayed, and maximum-attempt outcomes are terminal.
- Invalid transitions raise a ValueError.
- Events and traces record state changes for auditability.
