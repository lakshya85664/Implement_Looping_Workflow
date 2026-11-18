# Implement Looping Workflow in Code

## Project Overview
This project implements a shipment-tracking workflow that repeatedly polls a carrier adapter until the shipment is delivered, reported delayed, or the maximum polling-attempt limit is reached. It uses Python, Pydantic, pytest, and deterministic fake carrier adapters so the workflow can be tested locally without a live carrier API.

## Objectives
- Define typed shipment, workflow run, task, event, result, and trace models.
- Enforce explicit workflow states and legal transitions.
- Implement bounded polling with delivered, delayed, and attempt-limit outcomes.
- Handle transient errors, timeouts, permanent errors, and malformed carrier responses.
- Prevent duplicate run triggers and protect side effects with idempotency keys.
- Add an injectable carrier boundary, structured traces, metrics, status lookup, and secret redaction.
- Generate an operator runbook and validate required evidence files.

## Workflow States
| State | Meaning | Terminal |
|---|---|---|
| created | Workflow initialized | No |
| running | Carrier polling is active | No |
| waiting | Waiting between polling cycles | No |
| completed | Shipment delivered | Yes |
| delayed | Carrier reported a delay | Yes |
| max_attempts_reached | Polling limit exhausted | Yes |
| needs_review | Operator intervention required | Yes |

## Project Structure
```text
Implement_Looping_Workflow/
├── looping_workflow.py
├── looping_engine.py
├── looping_reliability.py
├── looping_observability.py
├── looping_runbook.py
├── tests/
├── docs/
├── outputs/
├── traces/
└── reports/
```

## Setup
```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run the Demonstrations
```cmd
python looping_workflow.py
python looping_engine.py
python looping_reliability.py
python looping_observability.py
python looping_runbook.py
python -m pytest -v
```

## Implementation Details

### Task 1 — Workflow contract and state model
Pydantic models validate shipment inputs and represent workflow runs, polling tasks, events, results, and traces. A transition table controls legal state changes. Invalid transitions raise `ValueError`.

### Task 2 — Looping workflow
The engine repeatedly calls an injected carrier adapter. An in-transit response permits another polling cycle; delivered and delayed responses terminate the loop. The configured maximum attempt count prevents unbounded polling. The deterministic demonstration writes `outputs/task2_looping_workflow.json`.

### Task 3 — Failure, retry, and replay safety
Transient errors and timeouts receive bounded retries. Permanent failures are not retried, while malformed or unsupported responses are quarantined. A run registry blocks duplicate run identifiers. An idempotency ledger caches protected action results so replay does not repeat the side effect.

### Task 4 — Integration and observability
The carrier dependency is isolated behind an adapter contract. Structured traces capture poll outcomes, timing, and next actions. Metrics include poll counts, successes, errors, average and maximum latency, success rate, queue age, and state durations. Status lookup exposes the latest observed status. Sensitive fields such as API keys and authorization values are redacted in trace details.

### Task 5 — Operator runbook and evidence
The runbook documents workflow states, execution commands, polling behavior, failure handling, replay safety, observability, evidence locations, operator checks, and known limitations. The evidence validator checks five required JSON artifacts and records whether each exists and parses successfully.

## Evidence Artifacts
- `outputs/task2_looping_workflow.json`
- `outputs/task3_failure_recovery.json`
- `outputs/task4_looping_measurements.json`
- `outputs/task5_operator_report.json`
- `traces/task3_recovery_trace.json`
- `traces/task4_looping_observability.json`
- `reports/OPERATOR_RUNBOOK.md`
- `reports/evidence_report.json`

Evidence validation result: 5 expected files, 5 found files, 5 valid JSON files, and `evidence_complete: true`.

## Verification Results
| Task | Tests passed |
|---|---:|
| Task 1 — Workflow contract | 6 |
| Task 2 — Looping workflow | 6 |
| Task 3 — Failure and replay safety | 8 |
| Task 4 — Integration and observability | 8 |
| Task 5 — Operator runbook | 8 |
| **Total** | **36** |

Final command: `python -m pytest -q`  
Verified result: **36 passed in 0.30s**.

## Known Limitations
- Carrier interactions use a deterministic fake adapter; no live carrier API is connected.
- The local demonstration does not physically sleep for the configured polling interval.
- Run registry and idempotency ledger are in-memory and are not durable across process restarts.
- Production use would require persistent shared storage, secure credentials, authentication, operational monitoring, and a real carrier integration.

## Reflection
This project helped me understand how a looping workflow differs from a one-time workflow execution. A shipment may remain in transit across several carrier checks, so the workflow needs a controlled loop, clear exit conditions, and a maximum attempt limit. Modeling workflow states and legal transitions first made execution behavior easier to reason about and test.

I also learned why external integrations should be isolated behind adapters. The fake carrier made it possible to test different responses deterministically without depending on a network service. The reliability task demonstrated the importance of distinguishing transient failures from permanent failures, bounding retries, validating external responses, and preventing duplicate triggers. The idempotency ledger showed how a repeated request can return an earlier result instead of repeating a protected side effect.

The observability work connected workflow execution with operational support. Structured traces, metrics, status lookup, and secret redaction make it easier to understand what happened during a run while avoiding exposure of sensitive values. Finally, the runbook and evidence validator provided a repeatable way to verify that project artifacts were generated correctly.

The main production lesson is that an in-memory demonstration is not yet a durable distributed workflow. A production implementation would need persistent run state and idempotency records, a real carrier integration, secure credential handling, and monitoring. Overall, this assessment strengthened my understanding of workflow state management, looping execution, fault handling, replay safety, and operational evidence.
