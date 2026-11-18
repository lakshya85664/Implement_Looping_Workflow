
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent

REQUIRED_EVIDENCE = [
    "outputs/task2_looping_workflow.json",
    "outputs/task3_failure_recovery.json",
    "outputs/task4_looping_measurements.json",
    "traces/task3_recovery_trace.json",
    "traces/task4_looping_observability.json",
]


def validate_json_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"

    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True, "valid JSON"
    except (json.JSONDecodeError, OSError) as exc:
        return False, str(exc)


def build_evidence_report() -> dict[str, Any]:
    evidence_items = []

    for relative_path in REQUIRED_EVIDENCE:
        full_path = PROJECT_ROOT / relative_path
        valid, message = validate_json_file(full_path)

        evidence_items.append({
            "path": relative_path,
            "exists": full_path.exists(),
            "valid": valid,
            "message": message,
        })

    found_count = sum(
        item["exists"] for item in evidence_items
    )

    valid_count = sum(
        item["valid"] for item in evidence_items
    )

    return {
        "report_name": "Looping Workflow Evidence Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_evidence_count": len(REQUIRED_EVIDENCE),
        "found_evidence_count": found_count,
        "valid_json_count": valid_count,
        "evidence_complete": (
            found_count == len(REQUIRED_EVIDENCE)
            and valid_count == len(REQUIRED_EVIDENCE)
        ),
        "evidence": evidence_items,
    }


def generate_runbook() -> Path:
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    content = """# Looping Workflow — Operator Runbook

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
.venv\\Scripts\\activate
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
"""

    runbook_path = reports_dir / "OPERATOR_RUNBOOK.md"
    runbook_path.write_text(content, encoding="utf-8")

    return runbook_path


def generate_evidence_report() -> Path:
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    report = build_evidence_report()

    report_path = reports_dir / "evidence_report.json"
    report_path.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    return report_path


def generate_operator_output() -> Path:
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    report = build_evidence_report()

    output_path = PROJECT_ROOT / "outputs" / "task5_operator_report.json"
    output_path.parent.mkdir(exist_ok=True)

    output_path.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    return output_path


def main() -> None:
    runbook_path = generate_runbook()
    evidence_path = generate_evidence_report()
    operator_path = generate_operator_output()

    report = build_evidence_report()

    print("=" * 60)
    print("TASK 5 - OPERATOR RUNBOOK AND EVIDENCE")
    print("=" * 60)
    print(f"Expected evidence files: {report['expected_evidence_count']}")
    print(f"Found evidence files: {report['found_evidence_count']}")
    print(f"Valid JSON files: {report['valid_json_count']}")
    print(f"Evidence complete: {report['evidence_complete']}")

    for item in report["evidence"]:
        print(
            f"- {item['path']}: "
            f"{'OK' if item['valid'] else 'MISSING/INVALID'}"
        )

    print(f"\nRunbook generated: {runbook_path}")
    print(f"Evidence report generated: {evidence_path}")
    print(f"Operator output generated: {operator_path}")


if __name__ == "__main__":
    main()
