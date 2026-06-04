"""Freshness validation for claim evidence reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_evidence_report import build_claim_evidence_report, claim_evidence_report_summary
from .utils import iso_now, read_json, safe_write_text, write_json

CLAIM_EVIDENCE_REPORT_VALIDATION_SCHEMA_VERSION = "1.14.1"


def validate_claim_evidence_report(project_dir: Path) -> dict[str, Any]:
    """Validate claim evidence report freshness and internal consistency."""
    project_dir = Path(project_dir)
    path = project_dir / "reports" / "claim_evidence_report.json"
    stored = read_json(path, default={}) or {}
    stored = stored if isinstance(stored, dict) else {}
    current = build_claim_evidence_report(project_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not path.exists():
        issues.append(_issue("report_missing", "reports/claim_evidence_report.json is missing."))
    elif _report_fingerprint(stored) != _report_fingerprint(current):
        issues.append(
            _issue(
                "report_stale",
                "reports/claim_evidence_report.json no longer matches current binder, validation, or claim signoffs.",
                stored_fingerprint=_report_fingerprint(stored),
                current_fingerprint=_report_fingerprint(current),
            )
        )
    if path.exists():
        _report_integrity_issues(stored, issues, warnings)

    valid = not issues
    result = {
        "schema_version": CLAIM_EVIDENCE_REPORT_VALIDATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "report_path": str(path),
        "status": "passed" if valid else "failed",
        "valid": valid,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "top_command": None if valid else _top_command(project_dir, issues, current),
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "stored_status": stored.get("status", "missing") if path.exists() else "missing",
            "current_status": current.get("status"),
            "stored_claim_count": int(stored.get("claim_count", 0) or 0),
            "current_claim_count": int(current.get("claim_count", 0) or 0),
            "stored_open_action_count": int(stored.get("open_action_count", 0) or 0),
            "current_open_action_count": int(current.get("open_action_count", 0) or 0),
        },
        "policy": "Claim evidence report validation checks report freshness and consistency only; it does not prove scientific reproduction.",
    }
    write_json(project_dir / "reports" / "claim_evidence_report_validation.json", result)
    safe_write_text(project_dir / "reports" / "claim_evidence_report_validation.md", _render_markdown(result))
    return result


def claim_evidence_report_validation_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim evidence report validation summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "reports" / "claim_evidence_report_validation.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    report = claim_evidence_report_summary(project_dir)
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "valid": bool(data.get("valid")) if path.exists() else False,
        "issue_count": int(data.get("issue_count", 0 if report["present"] else 1) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details}


def _report_fingerprint(report: dict[str, Any]) -> str:
    stable = {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "claim_count": report.get("claim_count"),
        "accepted_count": report.get("accepted_count"),
        "needs_more_evidence_count": report.get("needs_more_evidence_count"),
        "deferred_count": report.get("deferred_count"),
        "rejected_count": report.get("rejected_count"),
        "unsigned_claim_count": report.get("unsigned_claim_count"),
        "open_claim_count": report.get("open_claim_count"),
        "incomplete_claim_count": report.get("incomplete_claim_count"),
        "validation_status": report.get("validation_status"),
        "validation_issue_count": report.get("validation_issue_count"),
        "binder_status": report.get("binder_status"),
        "signoff_status": report.get("signoff_status"),
        "open_action_count": report.get("open_action_count"),
        "top_command": report.get("top_command"),
        "claims": sorted(
            [
                {
                    "claim_id": item.get("claim_id"),
                    "candidate_id": item.get("candidate_id"),
                    "kind": item.get("kind"),
                    "text": item.get("text"),
                    "source_name": item.get("source_name"),
                    "section": item.get("section"),
                    "evidence_status": item.get("evidence_status"),
                    "missing_evidence": sorted(str(value) for value in item.get("missing_evidence", [])),
                    "linked_experiment_ids": sorted(str(value) for value in item.get("linked_experiment_ids", [])),
                    "linked_run_ids": sorted(str(value) for value in item.get("linked_run_ids", [])),
                    "registered_data_ids": sorted(str(value) for value in item.get("registered_data_ids", [])),
                    "quality_gate_status": item.get("quality_gate_status"),
                    "protocol_covered": item.get("protocol_covered"),
                    "review_decision_ids": sorted(str(value) for value in item.get("review_decision_ids", [])),
                    "signoff_decision": item.get("signoff_decision"),
                    "signoff_reviewer": item.get("signoff_reviewer"),
                    "signoff_terminal": item.get("signoff_terminal"),
                    "signoff_note": item.get("signoff_note"),
                    "next_step": item.get("next_step"),
                }
                for item in report.get("claims", [])
                if isinstance(item, dict)
            ],
            key=lambda item: str(item.get("claim_id")),
        ),
    }
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _report_integrity_issues(
    report: dict[str, Any],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    claims = [item for item in report.get("claims", []) if isinstance(item, dict)]
    if int(report.get("claim_count", 0) or 0) != len(claims):
        issues.append(_issue("report_claim_count_mismatch", "Report claim_count does not match the claim matrix row count."))
    open_rows = [item for item in claims if item.get("next_step")]
    if int(report.get("open_action_count", 0) or 0) != len(open_rows):
        issues.append(_issue("report_open_action_count_mismatch", "Report open_action_count does not match claim rows with next steps."))
    if report.get("status") == "ready":
        if report.get("validation_status") != "passed":
            issues.append(_issue("report_ready_without_validation", "Report is ready but binder validation is not passed."))
        if report.get("signoff_status") != "complete":
            issues.append(_issue("report_ready_without_signoffs", "Report is ready but signoffs are not complete."))
        if int(report.get("open_action_count", 0) or 0) > 0:
            issues.append(_issue("report_ready_with_open_actions", "Report is ready but still lists open actions."))
    if not claims:
        warnings.append(_issue("report_has_no_claim_rows", "Claim evidence report has no claim rows."))


def _top_command(project_dir: Path, issues: list[dict[str, Any]], current: dict[str, Any]) -> str | None:
    if any(item["code"] == "report_missing" for item in issues):
        return f"openrepro claim-evidence-report {project_dir}"
    return current.get("top_command") or f"openrepro claim-evidence-report {project_dir}"


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Claim Evidence Report Validation",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- valid: {result['valid']}",
        f"- issue_count: {result['issue_count']}",
        f"- warning_count: {result['warning_count']}",
        f"- top_command: {result['top_command']}",
        "",
        "## Summary",
        "",
    ]
    for key, value in result["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Issues", "", "| Code | Message |", "| --- | --- |"])
    if result["issues"]:
        for item in result["issues"]:
            lines.append(f"| {_cell(item['code'])} | {_cell(item['message'])} |")
    else:
        lines.append("| none | No claim evidence report validation issues found. |")
    lines.extend(["", "## Warnings", "", "| Code | Message |", "| --- | --- |"])
    if result["warnings"]:
        for item in result["warnings"]:
            lines.append(f"| {_cell(item['code'])} | {_cell(item['message'])} |")
    else:
        lines.append("| none | No claim evidence report validation warnings found. |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
