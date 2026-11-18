# Looping Workflow — Operator Runbook

## 1. Purpose

This project implements a shipment-tracking workflow that repeatedly
polls a carrier until the shipment is delivered, delayed, or the
maximum polling attempt limit is reached.

The implementation uses an injectable carrier adapter and deterministic
fake carrier responses for local testing.

## 2. Workflow states

| State | Meaning | Terminal |
|---|---|---|
| created | Workflow initialized | No |
| running | Carrier polling is active | No |
| waiting | Waiting between polling cycles | No |
| completed | Shipment delivered | Yes |
| delayed | Carrier reported a delay | Yes |
| max_attempts_reached | Polling limit exhausted | Yes |
| needs_review | Operator intervention required | Yes |

## 3. Execution commands

Activate the virtual environment:

```cmd
.venv\Scripts\activate
```

Run the workflow contract:

```cmd
python looping_workflow.py
```

Run the looping workflow:

```cmd
python looping_engine.py
```

Run failure and replay recovery:

```cmd
python looping_reliability.py
```

Run observability:

```cmd
python looping_observability.py
```

Run all tests:

```cmd
python -m pytest -v
```

## 4. Polling behavior

1. A shipment run starts in the created state.
2. The workflow transitions to running.
3. The carrier adapter is called.
4. The response is validated.
5. An in-transit response allows another polling cycle.
6. A delivered response completes the workflow.
7. A delayed response terminates the workflow as delayed.
8. The maximum attempt limit stops further polling.

The polling interval is represented in the shipment input model.
The local deterministic demonstration does not sleep between polls.

## 5. Failure handling

- Transient carrier errors may be retried.
- Timeouts are treated as retryable errors.
- Retry attempts are bounded by max_retries.
- Retry exhaustion requires operator review.
- Permanent errors are not retried.
- Malformed or unsupported responses are quarantined.

## 6. Duplicate and replay safety

The run registry blocks duplicate workflow run identifiers.

The idempotency ledger caches the result of a protected action.
A repeated request with the same idempotency key returns the cached
result rather than repeating the side effect.

The included implementation uses in-memory registries and ledgers.
A production deployment would require durable shared storage.

## 7. Integration and observability

The carrier adapter is injected through an adapter contract.

Structured traces record poll outcomes, latency, and next actions.
Metrics include poll count, success count, error count, average
latency, maximum latency, success rate, queue age, and state durations.

Status lookup returns the latest observed carrier status for a
tracking number.

Sensitive values such as API keys, authorization values, tokens,
passwords, and secrets are redacted from structured trace details.

## 8. Evidence files

- outputs/task2_looping_workflow.json
- outputs/task3_failure_recovery.json
- outputs/task4_looping_measurements.json
- traces/task3_recovery_trace.json
- traces/task4_looping_observability.json
- reports/evidence_report.json

## 9. Operator checklist

- [ ] Confirm shipment and tracking identifiers.
- [ ] Confirm the maximum polling attempt limit.
- [ ] Check the final workflow state.
- [ ] Review retry and recovery traces.
- [ ] Confirm duplicate triggers were blocked.
- [ ] Verify idempotent side-effect behavior.
- [ ] Review carrier poll metrics.
- [ ] Confirm sensitive values are redacted.
- [ ] Validate all expected evidence files.

## 10. Known limitations

- The carrier adapter is a local fake implementation.
- Polling delays are not physically simulated.
- Run registry and idempotency ledger are in-memory.
- No real carrier credentials or external network calls are used.
- Production deployment would require persistent storage,
  authentication, monitoring, and a real carrier integration.
