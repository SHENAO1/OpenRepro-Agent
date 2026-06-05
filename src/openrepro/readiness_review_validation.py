"""Readiness review validation and freshness checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .readiness_review import build_readiness_review
from .utils import iso_now, read_json, safe_write_text, write_json

READINESS_REVIEW_VALIDATION_SCHEMA_VERSION = "1.21.1"


def validate_readiness_review(project_dir: Path) -> dict[str, Any]:
    """Validate reports/readiness_review.json against current project state."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    review_path = project_dir / "reports" / "readiness_review.json"
    markdown_path = project_dir / "reports" / "READINESS_REVIEW.md"
    stored = read_json(review_path, default={}) or {}
    stored = stored if isinstance(stored, dict) else {}
    current = build_readiness_review(project_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not review_path.exists():
        issues.append(_issue("readiness_review_missing", "reports/readiness_review.json is missing."))
    elif _review_fingerprint(stored) != _review_fingerprint(current):
        issues.append(
            _issue(
                "readiness_review_stale",
                "reports/readiness_review.json no longer matches current project readiness state.",
                stored_fingerprint=_review_fingerprint(stored),
                current_fingerprint=_review_fingerprint(current),
            )
        )

    if not markdown_path.exists():
        issues.append(_issue("readiness_review_markdown_missing", "reports/READINESS_REVIEW.md is missing."))

    _coherence_issues(stored, issues, warnings)
    zip_path = stored.get("zip_path")
    if zip_path and not Path(str(zip_path)).exists():
        warnings.append(_issue("readiness_review_zip_missing", f"Recorded zip_path is missing: {zip_path}"))

    valid = not issues
    result = {
        "schema_version": READINESS_REVIEW_VALIDATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "passed" if valid else "failed",
        "valid": valid,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "top_command": None if valid else f"openrepro readiness-review {project_dir} --zip",
        "review_path": str(review_path),
        "markdown_path": str(markdown_path),
        "stored_fingerprint": _review_fingerprint(stored) if stored else None,
        "current_fingerprint": _review_fingerprint(current),
        "issues": issues,
        "warnings": warnings,
        "policy": "Readiness review validation checks report freshness and internal consistency only; it does not claim scientific reproduction success.",
    }
    write_json(project_dir / "reports" / "readiness_review_validation.json", result)
    safe_write_text(project_dir / "reports" / "READINESS_REVIEW_VALIDATION.md", _render_markdown(result))
    return result


def readiness_review_validation_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing readiness review validation summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "reports" / "readiness_review_validation.json"
    markdown_path = project_dir / "reports" / "READINESS_REVIEW_VALIDATION.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "valid": bool(data.get("valid")) if path.exists() else False,
        "issue_count": int(data.get("issue_count", 0) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _review_fingerprint(review: dict[str, Any]) -> str:
    stable = _stable_review(review)
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _stable_review(review: dict[str, Any]) -> dict[str, Any]:
    summary = review.get("summary", {}) if isinstance(review.get("summary"), dict) else {}
    checks = review.get("checks", []) if isinstance(review.get("checks"), list) else []
    artifacts = review.get("artifact_links", []) if isinstance(review.get("artifact_links"), list) else []
    return {
        "schema_version": review.get("schema_version"),
        "project_name": review.get("project_name"),
        "status": review.get("status"),
        "top_command": review.get("top_command"),
        "check_count": review.get("check_count"),
        "passed_check_count": review.get("passed_check_count"),
        "blocker_count": review.get("blocker_count"),
        "open_action_count": review.get("open_action_count"),
        "summary": {
            "readiness_score": summary.get("readiness_score"),
            "acceptance_status": summary.get("acceptance_status"),
            "evidence_package_status": summary.get("evidence_package_status"),
            "freshness_status": summary.get("freshness_status"),
            "dashboard_status": summary.get("dashboard_status"),
        },
        "checks": [
            {
                "check_id": item.get("check_id"),
                "status": item.get("status"),
                "severity": item.get("severity"),
                "suggested_command": item.get("suggested_command"),
            }
            for item in checks
            if isinstance(item, dict)
        ],
        "artifact_links": [
            {
                "label": item.get("label"),
                "path": item.get("path"),
                "present": item.get("present"),
                "sha256": item.get("sha256"),
            }
            for item in artifacts
            if isinstance(item, dict)
        ],
        "policy": review.get("policy"),
    }


def _coherence_issues(stored: dict[str, Any], issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    if not stored:
        return
    checks = [item for item in stored.get("checks", []) if isinstance(item, dict)]
    passed = [item for item in checks if item.get("status") == "passed"]
    blockers = [item for item in checks if item.get("status") != "passed"]
    if stored.get("check_count") != len(checks):
        issues.append(_issue("check_count_mismatch", "check_count does not match the number of checks."))
    if stored.get("passed_check_count") != len(passed):
        issues.append(_issue("passed_check_count_mismatch", "passed_check_count does not match passed checks."))
    if stored.get("blocker_count") != len(blockers):
        issues.append(_issue("blocker_count_mismatch", "blocker_count does not match blocked checks."))
    expected_status = "ready_for_human_review" if not blockers else "needs_work"
    if stored.get("status") != expected_status:
        issues.append(_issue("status_mismatch", f"status should be {expected_status}."))
    if blockers and not stored.get("top_command"):
        issues.append(_issue("top_command_missing", "top_command is required when blocked checks exist."))
    if not blockers and stored.get("top_command"):
        warnings.append(_issue("top_command_unexpected", "top_command is set even though no blocked checks exist."))


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _render_markdown(result: dict[str, Any]) -> str:
    rows = [
        "| Type | Code | Message |",
        "| --- | --- | --- |",
    ]
    for issue in result["issues"]:
        rows.append(f"| issue | {_cell(issue['code'])} | {_cell(issue['message'])} |")
    for warning in result["warnings"]:
        rows.append(f"| warning | {_cell(warning['code'])} | {_cell(warning['message'])} |")
    return f"""# Readiness Review Validation

- schema_version: {result['schema_version']}
- created_at: {result['created_at']}
- status: {result['status']}
- valid: {result['valid']}
- issue_count: {result['issue_count']}
- warning_count: {result['warning_count']}
- top_command: {result['top_command']}
- review_path: `{result['review_path']}`
- stored_fingerprint: {result['stored_fingerprint']}
- current_fingerprint: {result['current_fingerprint']}

## Findings

{chr(10).join(rows)}

## Policy

{result['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
