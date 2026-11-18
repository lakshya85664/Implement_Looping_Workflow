
import json

from looping_runbook import (
    REQUIRED_EVIDENCE,
    validate_json_file,
    build_evidence_report,
    generate_runbook,
    generate_evidence_report,
    generate_operator_output,
)


def test_all_expected_evidence_files_are_defined():
    assert len(REQUIRED_EVIDENCE) == 5


def test_json_validator_accepts_valid_json(tmp_path):
    path = tmp_path / "valid.json"
    path.write_text('{"status": "completed"}', encoding="utf-8")

    valid, message = validate_json_file(path)

    assert valid is True
    assert message == "valid JSON"


def test_json_validator_rejects_invalid_json(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{invalid json", encoding="utf-8")

    valid, message = validate_json_file(path)

    assert valid is False
    assert message != "valid JSON"


def test_json_validator_detects_missing_file(tmp_path):
    path = tmp_path / "missing.json"

    valid, message = validate_json_file(path)

    assert valid is False
    assert message == "missing"


def test_evidence_report_has_expected_structure():
    report = build_evidence_report()

    assert report["report_name"] == "Looping Workflow Evidence Report"
    assert report["expected_evidence_count"] == 5
    assert len(report["evidence"]) == 5
    assert "evidence_complete" in report


def test_runbook_is_generated(tmp_path, monkeypatch):
    import looping_runbook

    monkeypatch.setattr(
        looping_runbook,
        "PROJECT_ROOT",
        tmp_path,
    )

    path = generate_runbook()

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Polling behavior" in content
    assert "Failure handling" in content
    assert "Operator checklist" in content


def test_evidence_report_file_is_generated(tmp_path, monkeypatch):
    import looping_runbook

    monkeypatch.setattr(
        looping_runbook,
        "PROJECT_ROOT",
        tmp_path,
    )

    path = generate_evidence_report()

    assert path.exists()

    report = json.loads(path.read_text(encoding="utf-8"))

    assert report["expected_evidence_count"] == 5
    assert len(report["evidence"]) == 5


def test_operator_output_is_generated(tmp_path, monkeypatch):
    import looping_runbook

    monkeypatch.setattr(
        looping_runbook,
        "PROJECT_ROOT",
        tmp_path,
    )

    path = generate_operator_output()

    assert path.exists()

    report = json.loads(path.read_text(encoding="utf-8"))

    assert report["report_name"] == "Looping Workflow Evidence Report"
