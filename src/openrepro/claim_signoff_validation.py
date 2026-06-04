"""Validation checks for human claim signoffs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_evidence_binder import build_claim_evidence_binder, validate_claim_evidence_binder
from .claim_signoff import ALLOWED_CLAIM_SIGNOFF_DECISIONS, TERMINAL_CLAIM_SIGNOFF_DECISIONS, claim_signoff_summary
from .utils import iso_now, read_json, safe_write_text, write_json

CLAIM_SIGNOFF_VALIDATION_SCHEMA_VERSION = "1.14.0"


def validate_claim_signoffs(project_dir: Path) -> dict[str, Any]:
    """Validate claim signoff coverage and freshness against current binder evidence."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_signoffs.json"
    signoffs = read_json(path, default={}) or {}
    signoffs = signoffs if isinstance(signoffs, dict) else {}
    current_binder = build_claim_evidence_binder(project_dir)
    binder_validation = validate_claim_evidence_binder(project_dir)
    summary = claim_signoff_summary(project_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not path.exists():
        issues.append(_issue("signoffs_missing", "workspace/claim_signoffs.json is missing."))
    if binder_validation.get("status") != "passed":
        issues.append(
            _issue(
                "binder_validation_failed",
                "Claim evidence binder validation must pass before claim signoffs are valid.",
                binder_validation_status=binder_validation.get("status"),
                binder_validation_issue_count=binder_validation.get("issue_count"),
            )
        )
    if path.exists():
        _signoff_integrity_issues(project_dir, signoffs, current_binder, summary, issues, warnings)

    valid = not issues
    result = {
        "schema_version": CLAIM_SIGNOFF_VALIDATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "signoff_path": str(path),
        "status": "passed" if valid else "failed",
        "valid": valid,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "top_command": None if valid else _top_command(project_dir, issues, summary, binder_validation),
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "current_claim_count": int(current_binder.get("claim_count", 0) or 0),
            "signoff_claim_count": int(signoffs.get("claim_count", 0) or 0),
            "signed_claim_count": int(signoffs.get("signed_claim_count", 0) or 0),
            "open_claim_count": int(signoffs.get("open_claim_count", 0) or 0),
            "binder_validation_status": binder_validation.get("status"),
            "signoff_status": signoffs.get("status", "missing") if path.exists() else "missing",
        },
        "policy": "Claim signoff validation checks workflow decision freshness only; it does not prove scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "claim_signoff_validation.json", result)
    safe_write_text(
        project_dir / "workspace" / "CLAIM_SIGNOFF_VALIDATION.md",
        _render_markdown(result),
    )
    return result


def claim_signoff_validation_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim signoff validation summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_signoff_validation.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    signoffs = claim_signoff_summary(project_dir)
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "valid": bool(data.get("valid")) if path.exists() else False,
        "issue_count": int(data.get("issue_count", signoffs["open_claim_count"]) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details}


def _latest_signoffs(signoffs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in signoffs.get("signoffs", []):
        if isinstance(item, dict) and item.get("claim_id"):
            latest[str(item["claim_id"])] = item
    return latest


def _claim_snapshot(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": claim.get("candidate_id"),
        "kind": claim.get("kind"),
        "text": claim.get("text"),
        "source_name": claim.get("source_name"),
        "section": claim.get("section"),
        "status": claim.get("status"),
        "missing_evidence": sorted(str(value) for value in claim.get("missing_evidence", [])),
        "linked_experiment_count": len(claim.get("linked_experiments", [])),
        "linked_run_count": len(claim.get("linked_runs", [])),
        "quality_gate_status": claim.get("quality_gate_status"),
    }


def _signoff_snapshot(signoff: dict[str, Any]) -> dict[str, Any]:
    snapshot = signoff.get("claim_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    return {
        "candidate_id": snapshot.get("candidate_id"),
        "kind": snapshot.get("kind"),
        "text": snapshot.get("text"),
        "source_name": snapshot.get("source_name"),
        "section": snapshot.get("section"),
        "status": snapshot.get("status"),
        "missing_evidence": sorted(str(value) for value in snapshot.get("missing_evidence", [])),
        "linked_experiment_count": snapshot.get("linked_experiment_count"),
        "linked_run_count": snapshot.get("linked_run_count"),
        "quality_gate_status": snapshot.get("quality_gate_status"),
    }


def _signoff_integrity_issues(
    project_dir: Path,
    signoffs: dict[str, Any],
    current_binder: dict[str, Any],
    summary: dict[str, Any],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    claims = [item for item in current_binder.get("claims", []) if isinstance(item, dict)]
    claim_map = {str(item.get("claim_id")): item for item in claims if item.get("claim_id")}
    latest = _latest_signoffs(signoffs)
    if signoffs.get("status") != "complete":
        issues.append(
            _issue(
                "signoffs_incomplete",
                "Claim signoffs are not complete.",
                status=signoffs.get("status"),
                open_claim_count=signoffs.get("open_claim_count"),
                top_command=summary.get("top_command"),
            )
        )
    if int(signoffs.get("claim_count", 0) or 0) != len(claims):
        issues.append(
            _issue(
                "signoff_claim_count_mismatch",
                "Claim signoff claim_count does not match current binder claim_count.",
                signoff_claim_count=signoffs.get("claim_count"),
                current_claim_count=len(claims),
            )
        )
    for claim_id, claim in claim_map.items():
        signoff = latest.get(claim_id)
        if not signoff:
            issues.append(_issue("signoff_missing", f"Claim {claim_id} has no latest signoff.", claim_id=claim_id))
            continue
        decision = str(signoff.get("decision") or "")
        if decision not in ALLOWED_CLAIM_SIGNOFF_DECISIONS:
            issues.append(_issue("signoff_decision_invalid", f"Claim {claim_id} has an unsupported signoff decision.", claim_id=claim_id, decision=decision))
        if decision == "accepted_workflow_evidence" and claim.get("status") != "complete":
            issues.append(_issue("accepted_incomplete_claim", f"Claim {claim_id} is accepted but current binder evidence is incomplete.", claim_id=claim_id))
        if decision not in TERMINAL_CLAIM_SIGNOFF_DECISIONS:
            warnings.append(_issue("signoff_nonterminal", f"Claim {claim_id} has a non-terminal signoff decision.", claim_id=claim_id, decision=decision))
        current_snapshot = _claim_snapshot(claim)
        stored_snapshot = _signoff_snapshot(signoff)
        if stored_snapshot != current_snapshot:
            issues.append(
                _issue(
                    "signoff_snapshot_stale",
                    f"Claim {claim_id} signoff snapshot no longer matches current binder evidence.",
                    claim_id=claim_id,
                    stored_snapshot=stored_snapshot,
                    current_snapshot=current_snapshot,
                )
            )
    for claim_id in sorted(set(latest) - set(claim_map)):
        issues.append(_issue("orphan_signoff", f"Signoff references a claim that is no longer in the binder: {claim_id}", claim_id=claim_id))
    if not claims:
        issues.append(_issue("signoff_claims_missing", "Current claim evidence binder has no claims."))
    if project_dir and int(signoffs.get("orphan_signoff_count", 0) or 0) > 0 and not any(item["code"] == "orphan_signoff" for item in issues):
        warnings.append(_issue("orphan_signoff_count_present", "Claim signoffs record orphan signoffs, but none were latest decisions."))


def _top_command(
    project_dir: Path,
    issues: list[dict[str, Any]],
    summary: dict[str, Any],
    binder_validation: dict[str, Any],
) -> str | None:
    if any(item["code"] == "binder_validation_failed" for item in issues):
        return binder_validation.get("top_command") or f"openrepro validate-evidence-binder {project_dir}"
    for item in issues:
        details = item.get("details", {})
        claim_id = details.get("claim_id")
        if claim_id:
            return f"openrepro claim-signoff {project_dir} --claim-id {claim_id} --decision accepted_workflow_evidence --reviewer <name>"
    return summary.get("top_command") or f"openrepro claim-signoff {project_dir}"


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Claim Signoff Validation",
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
        lines.append("| none | No claim signoff validation issues found. |")
    lines.extend(["", "## Warnings", "", "| Code | Message |", "| --- | --- |"])
    if result["warnings"]:
        for item in result["warnings"]:
            lines.append(f"| {_cell(item['code'])} | {_cell(item['message'])} |")
    else:
        lines.append("| none | No claim signoff validation warnings found. |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
