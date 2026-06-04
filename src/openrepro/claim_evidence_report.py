"""Reviewer-facing report for claim evidence, validation, and signoffs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_evidence_binder import generate_claim_evidence_binder, validate_claim_evidence_binder
from .claim_signoff import generate_claim_signoffs
from .utils import iso_now, read_json, safe_write_text, write_json

CLAIM_EVIDENCE_REPORT_SCHEMA_VERSION = "1.13.1"


def generate_claim_evidence_report(project_dir: Path) -> dict[str, Any]:
    """Write reports/claim_evidence_report.json and Markdown."""
    project_dir = Path(project_dir)
    binder = generate_claim_evidence_binder(project_dir)
    validation = validate_claim_evidence_binder(project_dir)
    signoffs = generate_claim_signoffs(project_dir)
    rows = _claim_rows(binder, signoffs)
    open_actions = [row for row in rows if row["next_step"]]
    result = {
        "schema_version": CLAIM_EVIDENCE_REPORT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": _report_status(binder, validation, signoffs),
        "claim_count": len(rows),
        "accepted_count": int(signoffs.get("accepted_count", 0) or 0),
        "needs_more_evidence_count": int(signoffs.get("needs_more_evidence_count", 0) or 0),
        "deferred_count": int(signoffs.get("deferred_count", 0) or 0),
        "rejected_count": int(signoffs.get("rejected_count", 0) or 0),
        "unsigned_claim_count": int(signoffs.get("unsigned_claim_count", 0) or 0),
        "open_claim_count": int(signoffs.get("open_claim_count", 0) or 0),
        "incomplete_claim_count": int(binder.get("incomplete_claim_count", 0) or 0),
        "validation_status": validation.get("status"),
        "validation_issue_count": int(validation.get("issue_count", 0) or 0),
        "binder_status": binder.get("status"),
        "signoff_status": signoffs.get("status"),
        "open_action_count": len(open_actions),
        "top_command": _top_command(binder, validation, signoffs),
        "claims": rows,
        "source_artifacts": {
            "binder": str(project_dir / "workspace" / "claim_evidence_binder.json"),
            "binder_validation": str(project_dir / "workspace" / "claim_evidence_binder_validation.json"),
            "claim_signoffs": str(project_dir / "workspace" / "claim_signoffs.json"),
        },
        "policy": "Claim evidence reports summarize workflow evidence, validation, and human signoffs only; they do not prove scientific reproduction.",
    }
    write_json(project_dir / "reports" / "claim_evidence_report.json", result)
    safe_write_text(project_dir / "reports" / "claim_evidence_report.md", _render_markdown(result))
    return result


def claim_evidence_report_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim evidence report status without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "reports" / "claim_evidence_report.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "claim_count": int(data.get("claim_count", 0) or 0),
        "open_action_count": int(data.get("open_action_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _report_status(binder: dict[str, Any], validation: dict[str, Any], signoffs: dict[str, Any]) -> str:
    if int(binder.get("claim_count", 0) or 0) <= 0:
        return "needs_claims"
    if validation.get("status") != "passed":
        return "needs_validation"
    if binder.get("status") != "complete":
        return "needs_evidence"
    if signoffs.get("status") != "complete":
        return "needs_signoff"
    return "ready"


def _top_command(binder: dict[str, Any], validation: dict[str, Any], signoffs: dict[str, Any]) -> str | None:
    if validation.get("status") != "passed":
        return validation.get("top_command")
    if binder.get("status") != "complete":
        return binder.get("top_command")
    if signoffs.get("status") != "complete":
        return signoffs.get("top_command")
    return None


def _latest_signoffs(signoffs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("claim_id")): item
        for item in signoffs.get("latest_signoffs", [])
        if isinstance(item, dict) and item.get("claim_id")
    }


def _claim_rows(binder: dict[str, Any], signoffs: dict[str, Any]) -> list[dict[str, Any]]:
    latest = _latest_signoffs(signoffs)
    rows: list[dict[str, Any]] = []
    for claim in binder.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "")
        signoff = latest.get(claim_id, {})
        next_step = None
        if claim.get("status") != "complete":
            next_step = binder.get("top_command")
        elif str(signoff.get("decision") or "") not in {"accepted_workflow_evidence", "rejected"}:
            next_step = signoffs.get("top_command")
        rows.append(
            {
                "claim_id": claim_id,
                "candidate_id": claim.get("candidate_id"),
                "kind": claim.get("kind"),
                "text": claim.get("text"),
                "source_name": claim.get("source_name"),
                "section": claim.get("section"),
                "evidence_status": claim.get("status"),
                "missing_evidence": claim.get("missing_evidence", []),
                "linked_experiment_ids": [item.get("experiment_id") for item in claim.get("linked_experiments", [])],
                "linked_run_ids": [item.get("run_id") for item in claim.get("linked_runs", [])],
                "registered_data_ids": claim.get("registered_data_ids", []),
                "quality_gate_status": claim.get("quality_gate_status"),
                "protocol_covered": (claim.get("protocol_coverage") or {}).get("covered"),
                "review_decision_ids": claim.get("review_decision_ids", []),
                "signoff_decision": signoff.get("decision"),
                "signoff_reviewer": signoff.get("reviewer"),
                "signoff_terminal": signoff.get("terminal"),
                "signoff_note": signoff.get("note"),
                "next_step": next_step,
            }
        )
    return rows


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Claim Evidence Report",
        "",
        f"- schema_version: {report['schema_version']}",
        f"- status: {report['status']}",
        f"- claim_count: {report['claim_count']}",
        f"- binder_status: {report['binder_status']}",
        f"- validation_status: {report['validation_status']}",
        f"- validation_issue_count: {report['validation_issue_count']}",
        f"- signoff_status: {report['signoff_status']}",
        f"- accepted_count: {report['accepted_count']}",
        f"- needs_more_evidence_count: {report['needs_more_evidence_count']}",
        f"- deferred_count: {report['deferred_count']}",
        f"- rejected_count: {report['rejected_count']}",
        f"- unsigned_claim_count: {report['unsigned_claim_count']}",
        f"- open_claim_count: {report['open_claim_count']}",
        f"- open_action_count: {report['open_action_count']}",
        f"- top_command: {report['top_command']}",
        "",
        "## Claim Matrix",
        "",
        "| Claim | Evidence | Signoff | Reviewer | Experiments | Runs | Missing evidence | Next step |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if report["claims"]:
        for claim in report["claims"]:
            lines.append(
                "| {claim_id} | {evidence} | {signoff} | {reviewer} | {experiments} | {runs} | {missing} | {next_step} |".format(
                    claim_id=_cell(claim.get("claim_id")),
                    evidence=_cell(claim.get("evidence_status")),
                    signoff=_cell(claim.get("signoff_decision")),
                    reviewer=_cell(claim.get("signoff_reviewer")),
                    experiments=_cell(claim.get("linked_experiment_ids", [])),
                    runs=_cell(claim.get("linked_run_ids", [])),
                    missing=_cell(claim.get("missing_evidence", [])),
                    next_step=_cell(claim.get("next_step")),
                )
            )
    else:
        lines.append("| none | needs_claims | none | none | [] | [] | [] | openrepro trace-claims <project> |")
    lines.extend(
        [
            "",
            "## Source Artifacts",
            "",
            f"- binder: `{report['source_artifacts']['binder']}`",
            f"- binder_validation: `{report['source_artifacts']['binder_validation']}`",
            f"- claim_signoffs: `{report['source_artifacts']['claim_signoffs']}`",
            "",
            "## Policy",
            "",
            report["policy"],
            "",
        ]
    )
    return "\n".join(lines)
