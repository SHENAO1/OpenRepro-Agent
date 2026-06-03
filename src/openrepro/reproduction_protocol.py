"""Reproduction protocol synthesis from workflow evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_trace import claim_trace_summary
from .data_registry import data_index_summary
from .experiment_spec import inspect_experiment_specs
from .gaps import gaps_summary
from .quality_gate import quality_gate_summaries
from .review_board import review_board_summary
from .review_decisions import review_decision_summary
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, safe_write_text, write_json

REPRODUCTION_PROTOCOL_SCHEMA_VERSION = "1.10.0"


def generate_reproduction_protocol(project_dir: Path) -> dict[str, Any]:
    """Write workspace/reproduction_protocol.json and Markdown."""
    project_dir = Path(project_dir)
    trace = read_json(project_dir / "workspace" / "claim_trace.json", default={}) or {}
    trace = trace if isinstance(trace, dict) else {}
    criteria = _acceptance_criteria(project_dir)
    blocking = [item for item in criteria if item["status"] != "passed"]
    result = {
        "schema_version": REPRODUCTION_PROTOCOL_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "ready" if not blocking else "blocked",
        "criterion_count": len(criteria),
        "blocking_criterion_count": len(blocking),
        "top_command": blocking[0]["suggested_command"] if blocking else None,
        "target_claims": _target_claims(trace),
        "required_data": _required_data(trace),
        "required_experiments": _required_experiments(trace),
        "required_runs": _required_runs(trace),
        "acceptance_criteria": criteria,
        "policy": "Reproduction protocols define workflow acceptance criteria only; they do not claim scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "reproduction_protocol.json", result)
    safe_write_text(project_dir / "workspace" / "REPRODUCTION_PROTOCOL.md", _render_protocol_markdown(result))
    return result


def protocol_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing protocol summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "reproduction_protocol.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "criterion_count": int(data.get("criterion_count", 0) or 0),
        "blocking_criterion_count": int(data.get("blocking_criterion_count", 0) or 0),
        "top_command": data.get("top_command"),
        "target_claim_count": len(data.get("target_claims", [])) if isinstance(data.get("target_claims"), list) else 0,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _acceptance_criteria(project_dir: Path) -> list[dict[str, Any]]:
    trace = claim_trace_summary(project_dir)
    data = data_index_summary(project_dir)
    specs = inspect_experiment_specs(project_dir)
    gates = quality_gate_summaries(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    review_board = review_board_summary(project_dir)
    review_decisions = review_decision_summary(project_dir)
    all_gates_passed = bool(gates) and all(gate.get("status") == "passed" for gate in gates)

    return [
        _criterion(
            "claim_trace_validated",
            "Claim trace is generated and validated.",
            trace["present"] and trace["validation_status"] == "passed",
            f"openrepro trace-claims {project_dir} --validate" if not trace["present"] else f"openrepro validate-claims {project_dir}",
            trace,
        ),
        _criterion(
            "candidate_claims_verified",
            "All traced candidate claims are human-verified.",
            trace["claim_count"] > 0 and trace["verified_claim_count"] == trace["claim_count"],
            f"openrepro approve-candidates {project_dir} --all --reviewer <name>",
            {"claim_count": trace["claim_count"], "verified_claim_count": trace["verified_claim_count"]},
        ),
        _criterion(
            "data_provenance_current",
            "Registered data provenance is current.",
            data["registered_count"] > 0 and data["invalid_count"] == 0,
            f"openrepro register-data {project_dir} --path <path> --role dataset",
            data,
        ),
        _criterion(
            "experiment_specs_current",
            "Experiment specs exist and are current.",
            bool(specs["specs"]) and specs["missing_count"] == 0 and specs["invalid_count"] == 0 and specs["stale_count"] == 0,
            f"openrepro validate-experiment-spec {project_dir} --experiment-id <id>",
            specs,
        ),
        _criterion(
            "run_evidence_present",
            "Claim trace links run evidence.",
            trace["run_trace_count"] > 0,
            f"openrepro run-experiment {project_dir} --experiment-id <id> --confirm",
            {"run_trace_count": trace["run_trace_count"]},
        ),
        _criterion(
            "quality_gates_passed",
            "All available quality gates passed.",
            all_gates_passed,
            f"openrepro quality-gate {project_dir} --all",
            {"quality_gate_count": len(gates), "failed_count": sum(1 for gate in gates if gate.get("status") == "failed")},
        ),
        _criterion(
            "scorecard_ready",
            "Workflow readiness scorecard is ready.",
            scorecard["present"] and scorecard["overall_status"] == "ready",
            f"openrepro scorecard {project_dir}",
            scorecard,
        ),
        _criterion(
            "gaps_clear",
            "Reproduction workflow gaps are clear.",
            gaps["present"] and gaps["status"] == "clear",
            f"openrepro gaps {project_dir}",
            gaps,
        ),
        _criterion(
            "review_queue_handled",
            "Review board items are clear or have recorded human decisions.",
            review_board["status"] == "clear" or review_decisions["unresolved_item_count"] == 0,
            review_decisions["top_command"] or f"openrepro review-board {project_dir}",
            {"review_board": review_board, "review_decisions": review_decisions},
        ),
    ]


def _criterion(
    criterion_id: str,
    label: str,
    passed: bool,
    suggested_command: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "label": label,
        "status": "passed" if passed else "blocked",
        "suggested_command": None if passed else suggested_command,
        "details": details,
    }


def _target_claims(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "claim_id": item.get("claim_id"),
            "candidate_id": item.get("candidate_id"),
            "kind": item.get("kind"),
            "verified_by_human": item.get("verified_by_human"),
            "risk_level": item.get("risk_level"),
            "source_name": item.get("source_name"),
            "section": item.get("section"),
            "text": item.get("text"),
        }
        for item in trace.get("claims", [])
        if isinstance(item, dict)
    ]


def _required_data(trace: dict[str, Any]) -> list[dict[str, Any]]:
    data = trace.get("data_registry", {}) if isinstance(trace.get("data_registry"), dict) else {}
    return [item for item in data.get("sources", []) if isinstance(item, dict)]


def _required_experiments(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "experiment_id": item.get("experiment_id"),
            "template": item.get("template"),
            "status": item.get("status"),
            "claim_ids": item.get("claim_ids", []),
            "verified_claim_ids": item.get("verified_claim_ids", []),
            "registered_data_ids": item.get("registered_data_ids", []),
        }
        for item in trace.get("experiments", [])
        if isinstance(item, dict)
    ]


def _required_runs(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": item.get("run_id"),
            "command": item.get("command"),
            "experiment_id": item.get("experiment_id"),
            "quality_gate_status": item.get("quality_gate_status"),
        }
        for item in trace.get("runs", [])
        if isinstance(item, dict)
    ]


def _render_protocol_markdown(protocol: dict[str, Any]) -> str:
    criteria_lines = [
        "| Criterion | Status | Suggested command |",
        "| --- | --- | --- |",
    ]
    for item in protocol["acceptance_criteria"]:
        criteria_lines.append(
            "| {label} | {status} | `{command}` |".format(
                label=str(item.get("label") or "").replace("|", "/"),
                status=item.get("status"),
                command=item.get("suggested_command") or "",
            )
        )
    claim_lines = ["| Claim | Kind | Verified | Source |", "| --- | --- | --- | --- |"]
    if protocol["target_claims"]:
        for claim in protocol["target_claims"]:
            claim_lines.append(
                "| {claim_id} | {kind} | {verified} | {source} |".format(
                    claim_id=claim.get("claim_id"),
                    kind=claim.get("kind"),
                    verified=claim.get("verified_by_human"),
                    source=claim.get("source_name"),
                )
            )
    else:
        claim_lines.append("| none | none | False | none |")
    return f"""# Reproduction Protocol

- schema_version: {protocol['schema_version']}
- status: {protocol['status']}
- criterion_count: {protocol['criterion_count']}
- blocking_criterion_count: {protocol['blocking_criterion_count']}
- top_command: {protocol['top_command']}

## Target Claims

{chr(10).join(claim_lines)}

## Acceptance Criteria

{chr(10).join(criteria_lines)}

## Required Data

- count: {len(protocol['required_data'])}

## Required Experiments

- count: {len(protocol['required_experiments'])}

## Required Runs

- count: {len(protocol['required_runs'])}

## Policy

{protocol['policy']}
"""
