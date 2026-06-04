"""Human signoff records for claim evidence binders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_evidence_binder import (
    claim_evidence_binder_summary,
    claim_evidence_binder_validation_summary,
    generate_claim_evidence_binder,
    validate_claim_evidence_binder,
)
from .utils import iso_now, read_json, safe_write_text, write_json

CLAIM_SIGNOFF_SCHEMA_VERSION = "1.13.0"
ALLOWED_CLAIM_SIGNOFF_DECISIONS = {
    "accepted_workflow_evidence",
    "needs_more_evidence",
    "rejected",
    "deferred",
}
TERMINAL_CLAIM_SIGNOFF_DECISIONS = {"accepted_workflow_evidence", "rejected"}


def record_claim_signoff(
    project_dir: Path,
    claim_id: str,
    decision: str,
    reviewer: str,
    note: str = "",
    followup_command: str | None = None,
) -> dict[str, Any]:
    """Append a human signoff decision for a current claim evidence binder claim."""
    project_dir = Path(project_dir)
    claim_id = claim_id.strip()
    decision = decision.strip().lower()
    if decision not in ALLOWED_CLAIM_SIGNOFF_DECISIONS:
        allowed = ", ".join(sorted(ALLOWED_CLAIM_SIGNOFF_DECISIONS))
        raise ValueError(f"Unsupported decision {decision!r}; expected one of: {allowed}")
    if not claim_id:
        raise ValueError("Claim id is required.")
    if not reviewer.strip():
        raise ValueError("Reviewer is required.")

    binder = _current_or_generated_binder(project_dir)
    validation = validate_claim_evidence_binder(project_dir)
    if validation.get("status") != "passed":
        raise ValueError("Claim evidence binder validation must pass before claim signoff.")

    claim_map = {str(item.get("claim_id")): item for item in binder.get("claims", []) if isinstance(item, dict)}
    if claim_id not in claim_map:
        raise ValueError(f"Claim not found in claim evidence binder: {claim_id}")
    claim = claim_map[claim_id]
    if decision == "accepted_workflow_evidence" and claim.get("status") != "complete":
        raise ValueError("accepted_workflow_evidence requires a complete claim evidence binder record.")

    existing = _load_claim_signoffs(project_dir)
    signoffs = existing.get("signoffs", [])
    signoffs = signoffs if isinstance(signoffs, list) else []
    record = {
        "signoff_id": f"S{len(signoffs) + 1:03d}",
        "created_at": iso_now(),
        "claim_id": claim_id,
        "decision": decision,
        "reviewer": reviewer.strip(),
        "note": note,
        "followup_command": followup_command,
        "terminal": decision in TERMINAL_CLAIM_SIGNOFF_DECISIONS,
        "claim_snapshot": {
            "candidate_id": claim.get("candidate_id"),
            "kind": claim.get("kind"),
            "text": claim.get("text"),
            "source_name": claim.get("source_name"),
            "section": claim.get("section"),
            "status": claim.get("status"),
            "missing_evidence": claim.get("missing_evidence", []),
            "linked_experiment_count": len(claim.get("linked_experiments", [])),
            "linked_run_count": len(claim.get("linked_runs", [])),
            "quality_gate_status": claim.get("quality_gate_status"),
        },
        "policy": "Claim signoffs record human workflow acceptance only; they do not prove scientific reproduction.",
    }
    signoffs.append(record)
    return _write_claim_signoffs(project_dir, signoffs, binder, validation)


def generate_claim_signoffs(project_dir: Path) -> dict[str, Any]:
    """Write current claim signoff summary artifacts without adding decisions."""
    project_dir = Path(project_dir)
    binder = _current_or_generated_binder(project_dir)
    validation = claim_evidence_binder_validation_summary(project_dir)
    existing = _load_claim_signoffs(project_dir)
    signoffs = existing.get("signoffs", [])
    signoffs = signoffs if isinstance(signoffs, list) else []
    return _write_claim_signoffs(project_dir, signoffs, binder, validation)


def claim_signoff_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim signoff status without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_signoffs.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    binder = claim_evidence_binder_summary(project_dir)
    fallback_claim_count = binder["claim_count"]
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "claim_count": int(data.get("claim_count", fallback_claim_count) or 0),
        "signoff_count": int(data.get("signoff_count", 0) or 0),
        "signed_claim_count": int(data.get("signed_claim_count", 0) or 0),
        "terminal_signoff_count": int(data.get("terminal_signoff_count", 0) or 0),
        "accepted_count": int(data.get("accepted_count", 0) or 0),
        "needs_more_evidence_count": int(data.get("needs_more_evidence_count", 0) or 0),
        "deferred_count": int(data.get("deferred_count", 0) or 0),
        "rejected_count": int(data.get("rejected_count", 0) or 0),
        "unsigned_claim_count": int(data.get("unsigned_claim_count", fallback_claim_count) or 0),
        "open_claim_count": int(data.get("open_claim_count", fallback_claim_count) or 0),
        "top_claim": data.get("top_claim"),
        "top_command": data.get("top_command") or _top_command_from_binder(project_dir),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _current_or_generated_binder(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "workspace" / "claim_evidence_binder.json"
    binder = read_json(path, default={}) or {}
    if not isinstance(binder, dict) or not path.exists():
        binder = generate_claim_evidence_binder(project_dir)
    return binder if isinstance(binder, dict) else {}


def _load_claim_signoffs(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "claim_signoffs.json", default={}) or {}
    return data if isinstance(data, dict) else {}


def _write_claim_signoffs(
    project_dir: Path,
    signoffs: list[dict[str, Any]],
    binder: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    latest_by_claim: dict[str, dict[str, Any]] = {}
    for signoff in signoffs:
        if isinstance(signoff, dict) and signoff.get("claim_id"):
            latest_by_claim[str(signoff["claim_id"])] = signoff

    claims = [item for item in binder.get("claims", []) if isinstance(item, dict)]
    claim_ids = {str(item.get("claim_id")) for item in claims if item.get("claim_id")}
    latest_for_current = [latest_by_claim[claim_id] for claim_id in sorted(claim_ids) if claim_id in latest_by_claim]
    terminal_claim_ids = {
        str(item.get("claim_id"))
        for item in latest_for_current
        if str(item.get("decision")) in TERMINAL_CLAIM_SIGNOFF_DECISIONS
    }
    signed_claim_ids = {str(item.get("claim_id")) for item in latest_for_current}
    open_claims = [item for item in claims if str(item.get("claim_id")) not in terminal_claim_ids]
    top_claim = str(open_claims[0].get("claim_id")) if open_claims else None
    result = {
        "schema_version": CLAIM_SIGNOFF_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "binder_schema_version": binder.get("schema_version"),
        "binder_status": binder.get("status"),
        "binder_validation_status": validation.get("status"),
        "status": _status_from_counts(len(claims), len(open_claims)),
        "claim_count": len(claims),
        "signoff_count": len(signoffs),
        "signed_claim_count": len(signed_claim_ids),
        "terminal_signoff_count": len(terminal_claim_ids),
        "accepted_count": sum(1 for item in latest_for_current if item.get("decision") == "accepted_workflow_evidence"),
        "needs_more_evidence_count": sum(1 for item in latest_for_current if item.get("decision") == "needs_more_evidence"),
        "deferred_count": sum(1 for item in latest_for_current if item.get("decision") == "deferred"),
        "rejected_count": sum(1 for item in latest_for_current if item.get("decision") == "rejected"),
        "unsigned_claim_count": len(claim_ids - signed_claim_ids),
        "open_claim_count": len(open_claims),
        "orphan_signoff_count": sum(1 for claim_id in latest_by_claim if claim_id not in claim_ids),
        "top_claim": top_claim,
        "top_command": _decision_command(project_dir, open_claims[0]) if open_claims else None,
        "latest_signoffs": latest_for_current,
        "open_claims": [_open_claim_ref(item) for item in open_claims],
        "signoffs": signoffs,
        "policy": "Claim signoffs are human workflow decisions about evidence records; they do not prove scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "claim_signoffs.json", result)
    safe_write_text(project_dir / "workspace" / "CLAIM_SIGNOFFS.md", _render_claim_signoffs_markdown(result))
    return result


def _status_from_counts(claim_count: int, open_claim_count: int) -> str:
    if claim_count <= 0:
        return "needs_claims"
    if open_claim_count <= 0:
        return "complete"
    return "needs_signoff"


def _decision_command(project_dir: Path, claim: dict[str, Any] | None) -> str | None:
    if not claim or not claim.get("claim_id"):
        return None
    decision = "accepted_workflow_evidence" if claim.get("status") == "complete" else "needs_more_evidence"
    return f"openrepro claim-signoff {project_dir} --claim-id {claim.get('claim_id')} --decision {decision} --reviewer <name>"


def _top_command_from_binder(project_dir: Path) -> str | None:
    binder = read_json(project_dir / "workspace" / "claim_evidence_binder.json", default={}) or {}
    if not isinstance(binder, dict):
        return None
    claims = [item for item in binder.get("claims", []) if isinstance(item, dict)]
    return _decision_command(project_dir, claims[0] if claims else None)


def _open_claim_ref(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": claim.get("claim_id"),
        "status": claim.get("status"),
        "missing_evidence": claim.get("missing_evidence", []),
        "suggested_decision": "accepted_workflow_evidence" if claim.get("status") == "complete" else "needs_more_evidence",
    }


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_claim_signoffs_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Claim Signoffs",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- binder_status: {result['binder_status']}",
        f"- binder_validation_status: {result['binder_validation_status']}",
        f"- claim_count: {result['claim_count']}",
        f"- signoff_count: {result['signoff_count']}",
        f"- signed_claim_count: {result['signed_claim_count']}",
        f"- terminal_signoff_count: {result['terminal_signoff_count']}",
        f"- accepted_count: {result['accepted_count']}",
        f"- needs_more_evidence_count: {result['needs_more_evidence_count']}",
        f"- deferred_count: {result['deferred_count']}",
        f"- rejected_count: {result['rejected_count']}",
        f"- unsigned_claim_count: {result['unsigned_claim_count']}",
        f"- open_claim_count: {result['open_claim_count']}",
        f"- top_claim: {result['top_claim']}",
        f"- top_command: {result['top_command']}",
        "",
        "## Latest Signoffs",
        "",
        "| Claim | Decision | Reviewer | Terminal | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    if result["latest_signoffs"]:
        for item in result["latest_signoffs"]:
            lines.append(
                "| {claim_id} | {decision} | {reviewer} | {terminal} | {note} |".format(
                    claim_id=_cell(item.get("claim_id")),
                    decision=_cell(item.get("decision")),
                    reviewer=_cell(item.get("reviewer")),
                    terminal=_cell(item.get("terminal")),
                    note=_cell(item.get("note") or ""),
                )
            )
    else:
        lines.append("| none | none | none | False | No claim signoffs recorded. |")
    lines.extend(["", "## Open Claims", "", "| Claim | Status | Missing evidence | Suggested command |", "| --- | --- | --- | --- |"])
    if result["open_claims"]:
        for item in result["open_claims"]:
            command = _decision_command(Path(result["project_dir"]), item) or ""
            lines.append(
                "| {claim_id} | {status} | {missing} | `{command}` |".format(
                    claim_id=_cell(item.get("claim_id")),
                    status=_cell(item.get("status")),
                    missing=_cell(item.get("missing_evidence", [])),
                    command=_cell(command),
                )
            )
    else:
        lines.append("| none | complete | [] |  |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
