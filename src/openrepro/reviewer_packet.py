"""Reviewer packet generation for human claim evidence review."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .claim_evidence_report import generate_claim_evidence_report
from .claim_evidence_report_validation import validate_claim_evidence_report
from .claim_signoff_validation import validate_claim_signoffs
from .gaps import generate_reproduction_gaps
from .protocol_preflight import generate_protocol_preflight
from .scorecard import generate_reproduction_scorecard
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

REVIEWER_PACKET_SCHEMA_VERSION = "1.15.0"


def generate_reviewer_packet(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write reports/reviewer_packet.json and Markdown, optionally exporting a zip."""
    project_dir = Path(project_dir)
    claim_report = generate_claim_evidence_report(project_dir)
    signoff_validation = validate_claim_signoffs(project_dir)
    report_validation = validate_claim_evidence_report(project_dir)
    preflight = generate_protocol_preflight(project_dir)
    scorecard = generate_reproduction_scorecard(project_dir)
    gaps = generate_reproduction_gaps(project_dir)
    review_items = _review_items(claim_report)
    open_actions = [item for item in review_items if item.get("next_step")]
    validation_issues = _validation_issues(signoff_validation, report_validation, preflight, gaps)
    status = _packet_status(claim_report, signoff_validation, report_validation, validation_issues, open_actions)
    packet = {
        "schema_version": REVIEWER_PACKET_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": status,
        "claim_count": int(claim_report.get("claim_count", 0) or 0),
        "review_item_count": len(review_items),
        "open_action_count": len(open_actions),
        "validation_issue_count": len(validation_issues),
        "top_command": _top_command(claim_report, signoff_validation, report_validation, validation_issues),
        "validation_status": {
            "claim_evidence_report": claim_report.get("status"),
            "claim_signoff_validation": signoff_validation.get("status"),
            "claim_evidence_report_validation": report_validation.get("status"),
            "protocol_preflight": preflight.get("status"),
            "gaps": gaps.get("status"),
            "scorecard": scorecard.get("overall_status"),
        },
        "review_items": review_items,
        "open_actions": open_actions,
        "validation_issues": validation_issues,
        "review_order": [item["claim_id"] for item in review_items],
        "source_artifacts": _source_artifacts(project_dir),
        "policy": "Reviewer packets organize workflow evidence for human review; they do not prove scientific reproduction.",
    }
    write_json(project_dir / "reports" / "reviewer_packet.json", packet)
    markdown = _render_markdown(packet)
    safe_write_text(project_dir / "reports" / "reviewer_packet.md", markdown)
    if export_zip:
        packet["zip_path"] = str(_export_zip(project_dir, packet))
        write_json(project_dir / "reports" / "reviewer_packet.json", packet)
    return packet


def reviewer_packet_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing reviewer packet summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "reports" / "reviewer_packet.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "claim_count": int(data.get("claim_count", 0) or 0),
        "open_action_count": int(data.get("open_action_count", 0) or 0),
        "validation_issue_count": int(data.get("validation_issue_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _review_items(claim_report: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for claim in claim_report.get("claims", []):
        if not isinstance(claim, dict):
            continue
        risk_flags = []
        if claim.get("evidence_status") != "complete":
            risk_flags.append("evidence_incomplete")
        if claim.get("signoff_decision") != "accepted_workflow_evidence":
            risk_flags.append("signoff_not_accepted")
        if claim.get("next_step"):
            risk_flags.append("open_action")
        items.append(
            {
                "claim_id": claim.get("claim_id"),
                "kind": claim.get("kind"),
                "text": claim.get("text"),
                "source_name": claim.get("source_name"),
                "section": claim.get("section"),
                "evidence_status": claim.get("evidence_status"),
                "signoff_decision": claim.get("signoff_decision"),
                "signoff_reviewer": claim.get("signoff_reviewer"),
                "quality_gate_status": claim.get("quality_gate_status"),
                "protocol_covered": claim.get("protocol_covered"),
                "linked_experiment_ids": claim.get("linked_experiment_ids", []),
                "linked_run_ids": claim.get("linked_run_ids", []),
                "registered_data_ids": claim.get("registered_data_ids", []),
                "next_step": claim.get("next_step"),
                "risk_flags": risk_flags,
            }
        )
    return items


def _validation_issues(
    signoff_validation: dict[str, Any],
    report_validation: dict[str, Any],
    preflight: dict[str, Any],
    gaps: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if signoff_validation.get("status") != "passed":
        issues.append({"source": "claim_signoff_validation", "status": signoff_validation.get("status"), "top_command": signoff_validation.get("top_command")})
    if report_validation.get("status") != "passed":
        issues.append({"source": "claim_evidence_report_validation", "status": report_validation.get("status"), "top_command": report_validation.get("top_command")})
    if preflight.get("blocking_count", 0):
        issues.append({"source": "protocol_preflight", "status": preflight.get("status"), "top_command": preflight.get("top_command")})
    if gaps.get("open_count", 0):
        issues.append({"source": "reproduction_gaps", "status": gaps.get("status"), "top_command": gaps.get("top_suggested_command")})
    return issues


def _packet_status(
    claim_report: dict[str, Any],
    signoff_validation: dict[str, Any],
    report_validation: dict[str, Any],
    validation_issues: list[dict[str, Any]],
    open_actions: list[dict[str, Any]],
) -> str:
    if int(claim_report.get("claim_count", 0) or 0) <= 0:
        return "needs_claims"
    if signoff_validation.get("status") != "passed" or report_validation.get("status") != "passed":
        return "needs_validation"
    if validation_issues or open_actions:
        return "needs_review"
    return "ready"


def _top_command(
    claim_report: dict[str, Any],
    signoff_validation: dict[str, Any],
    report_validation: dict[str, Any],
    validation_issues: list[dict[str, Any]],
) -> str | None:
    if signoff_validation.get("status") != "passed":
        return signoff_validation.get("top_command")
    if report_validation.get("status") != "passed":
        return report_validation.get("top_command")
    if validation_issues:
        return validation_issues[0].get("top_command")
    return claim_report.get("top_command")


def _source_artifacts(project_dir: Path) -> list[dict[str, Any]]:
    names = [
        project_dir / "reports" / "claim_evidence_report.md",
        project_dir / "reports" / "claim_evidence_report_validation.md",
        project_dir / "workspace" / "CLAIM_SIGNOFFS.md",
        project_dir / "workspace" / "CLAIM_SIGNOFF_VALIDATION.md",
        project_dir / "workspace" / "CLAIM_EVIDENCE_BINDER.md",
        project_dir / "workspace" / "CLAIM_EVIDENCE_BINDER_VALIDATION.md",
        project_dir / "workspace" / "PROTOCOL_PREFLIGHT.md",
        project_dir / "workspace" / "REPRODUCTION_SCORECARD.md",
        project_dir / "workspace" / "REPRODUCTION_GAPS.md",
    ]
    artifacts = []
    for path in names:
        artifacts.append(
            {
                "name": path.name,
                "path": str(path),
                "present": path.exists(),
                "sha256": sha256_file(path) if path.exists() else None,
            }
        )
    return artifacts


def _export_zip(project_dir: Path, packet: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "reviewer_packet.zip"
    files = [
        project_dir / "reports" / "reviewer_packet.json",
        project_dir / "reports" / "reviewer_packet.md",
    ]
    files.extend(Path(item["path"]) for item in packet.get("source_artifacts", []) if item.get("present") and item.get("path"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(packet: dict[str, Any]) -> str:
    item_lines = [
        "| Claim | Evidence | Signoff | Reviewer | Risk flags | Next step |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if packet["review_items"]:
        for item in packet["review_items"]:
            item_lines.append(
                "| {claim_id} | {evidence} | {signoff} | {reviewer} | {risk} | {next_step} |".format(
                    claim_id=_cell(item.get("claim_id")),
                    evidence=_cell(item.get("evidence_status")),
                    signoff=_cell(item.get("signoff_decision")),
                    reviewer=_cell(item.get("signoff_reviewer")),
                    risk=_cell(item.get("risk_flags", [])),
                    next_step=_cell(item.get("next_step")),
                )
            )
    else:
        item_lines.append("| none | needs_claims | none | none | [] | openrepro trace-claims <project> |")
    artifact_lines = [
        "| Artifact | Present | SHA-256 |",
        "| --- | --- | --- |",
    ]
    for item in packet["source_artifacts"]:
        artifact_lines.append(f"| {_cell(item['name'])} | {item['present']} | {_cell(item.get('sha256'))} |")
    return f"""# Reviewer Packet

- schema_version: {packet['schema_version']}
- status: {packet['status']}
- claim_count: {packet['claim_count']}
- review_item_count: {packet['review_item_count']}
- open_action_count: {packet['open_action_count']}
- validation_issue_count: {packet['validation_issue_count']}
- top_command: {packet['top_command']}

## Validation Status

```json
{packet['validation_status']}
```

## Review Items

{chr(10).join(item_lines)}

## Open Actions

```json
{packet['open_actions']}
```

## Source Artifacts

{chr(10).join(artifact_lines)}

## Policy

{packet['policy']}
"""
