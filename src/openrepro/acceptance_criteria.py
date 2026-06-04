"""Acceptance criteria generation for reproduction workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_trace import claim_trace_summary
from .data_registry import data_index_summary
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .gaps import gaps_summary
from .project_profile import generate_project_profile
from .protocol_coverage import protocol_coverage_summary
from .protocol_preflight import protocol_preflight_summary
from .quality_gate import quality_gate_summaries
from .reproduction_protocol import protocol_summary
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, safe_write_text, write_json

ACCEPTANCE_CRITERIA_SCHEMA_VERSION = "1.20.1"


def generate_acceptance_criteria(project_dir: Path) -> dict[str, Any]:
    """Write workspace/acceptance_criteria.json and workspace/ACCEPTANCE_CRITERIA.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    criteria = build_acceptance_criteria(project_dir)
    write_json(project_dir / "workspace" / "acceptance_criteria.json", criteria)
    safe_write_text(project_dir / "workspace" / "ACCEPTANCE_CRITERIA.md", _render_markdown(criteria))
    return criteria


def build_acceptance_criteria(project_dir: Path) -> dict[str, Any]:
    """Build acceptance criteria payload without writing files."""
    project_dir = Path(project_dir)
    profile = _load_or_generate_profile(project_dir)
    trace = claim_trace_summary(project_dir)
    data = data_index_summary(project_dir)
    scaffolds = inspect_experiment_scaffolds(project_dir)
    specs = inspect_experiment_specs(project_dir)
    gates = quality_gate_summaries(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    protocol = protocol_summary(project_dir)
    coverage = protocol_coverage_summary(project_dir)
    preflight = protocol_preflight_summary(project_dir)
    target_claims = [item for item in profile.get("target_claims", []) if isinstance(item, dict)]
    required_data = [item for item in profile.get("required_data", []) if isinstance(item, dict)]
    required_experiments = [item for item in profile.get("required_experiments", []) if isinstance(item, dict)]
    criteria = [
        _criterion(
            "profile_defined",
            "Profile defines reproduction scope.",
            "scope",
            profile.get("status") in {"ready", "ready_with_open_work"} and bool(target_claims),
            f"{len(target_claims)} target claim(s) in profile.",
            {"profile_status": profile.get("status"), "target_claim_count": len(target_claims)},
            f"openrepro profile {project_dir}",
        ),
        _criterion(
            "target_claims_reviewed",
            "All target claims have human-reviewed candidate status.",
            "claims",
            bool(target_claims) and all(item.get("verified_by_human") for item in target_claims),
            f"{sum(1 for item in target_claims if item.get('verified_by_human'))}/{len(target_claims)} target claims verified.",
            {"target_claim_count": len(target_claims)},
            f"openrepro approve-candidates {project_dir} --all --reviewer <name>",
        ),
        _criterion(
            "data_requirements_current",
            "Required data is registered and current.",
            "data",
            bool(required_data) and all(item.get("status") == "current" for item in required_data) and data["invalid_count"] == 0,
            f"{data['valid_count']}/{data['registered_count']} registered data file(s) are current.",
            {"registered_count": data["registered_count"], "status_counts": data["status_counts"]},
            f"openrepro validate-data {project_dir}",
        ),
        _criterion(
            "experiment_scaffolds_ready",
            "Required experiment scaffolds are present and runnable.",
            "experiments",
            bool(required_experiments) and all(item.get("runnable") for item in required_experiments),
            f"{scaffolds['scaffold_count']} experiment scaffold(s) inspected.",
            {"scaffold_count": scaffolds["scaffold_count"], "template_counts": scaffolds["template_counts"]},
            f"openrepro scaffold-experiment {project_dir} --experiment-id <id>",
        ),
        _criterion(
            "experiment_inputs_complete",
            "Experiment input contracts have no missing required inputs.",
            "experiments",
            bool(required_experiments)
            and all(item.get("input_completeness_status") in {"complete", "no_required_inputs"} for item in required_experiments),
            f"{scaffolds['missing_required_input_count']} required input(s) missing.",
            {"input_completeness_counts": scaffolds["input_completeness_counts"]},
            f"openrepro validate-inputs {project_dir} --experiment-id <id>",
        ),
        _criterion(
            "experiment_specs_current",
            "Experiment specs are present, valid, and current.",
            "experiments",
            bool(specs["specs"]) and specs["missing_count"] == 0 and specs["invalid_count"] == 0 and specs["stale_count"] == 0,
            f"Spec status counts: {specs['status_counts']}.",
            {"status_counts": specs["status_counts"]},
            f"openrepro validate-experiment-spec {project_dir} --experiment-id <id>",
        ),
        _criterion(
            "run_evidence_present",
            "Run evidence is linked through the claim trace.",
            "runs",
            trace["run_trace_count"] > 0,
            f"{trace['run_trace_count']} run trace(s) linked.",
            {"experiment_trace_count": trace["experiment_trace_count"], "run_trace_count": trace["run_trace_count"]},
            f"openrepro run-experiment {project_dir} --experiment-id <id> --confirm",
        ),
        _criterion(
            "quality_gates_passed",
            "All available quality gates passed.",
            "quality",
            bool(gates) and all(item.get("status") == "passed" for item in gates),
            f"{sum(1 for item in gates if item.get('status') == 'passed')}/{len(gates)} quality gate(s) passed.",
            {"quality_gate_count": len(gates), "failed": [item for item in gates if item.get("status") == "failed"]},
            f"openrepro quality-gate {project_dir} --all",
        ),
        _criterion(
            "claim_trace_validated",
            "Claim trace is present and validated.",
            "claims",
            trace["present"] and trace["validation_status"] == "passed",
            f"Claim trace validation status is {trace['validation_status']}.",
            {"claim_count": trace["claim_count"], "validation_issue_count": trace["validation_issue_count"]},
            f"openrepro validate-claims {project_dir}",
        ),
        _criterion(
            "readiness_gaps_clear",
            "Readiness scorecard is ready and reproduction gaps are clear.",
            "readiness",
            scorecard["overall_status"] == "ready" and gaps["status"] == "clear",
            f"Scorecard is {scorecard['overall_status']}; gaps are {gaps['status']}.",
            {"readiness_score": scorecard["overall_score"], "open_gap_count": gaps["open_count"]},
            f"openrepro gaps {project_dir}",
        ),
        _criterion(
            "protocol_ready",
            "Protocol, coverage, and preflight checks are ready.",
            "protocol",
            protocol["status"] == "ready" and coverage["status"] == "complete" and preflight["status"] == "ready",
            f"Protocol={protocol['status']}; coverage={coverage['status']}; preflight={preflight['status']}.",
            {"protocol_status": protocol["status"], "coverage_status": coverage["status"], "preflight_status": preflight["status"]},
            f"openrepro protocol-preflight {project_dir}",
        ),
    ]
    failed = [item for item in criteria if item["status"] != "passed"]
    status = "ready" if not failed else "needs_work"
    return {
        "schema_version": ACCEPTANCE_CRITERIA_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": profile.get("project_name") or project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": failed[0]["suggested_command"] if failed else None,
        "criteria_count": len(criteria),
        "passed_count": len(criteria) - len(failed),
        "needs_work_count": len(failed),
        "required_failed_count": len(failed),
        "criteria": criteria,
        "profile": {
            "schema_version": profile.get("schema_version"),
            "status": profile.get("status"),
            "target_claim_count": profile.get("target_claim_count"),
            "required_data_count": profile.get("required_data_count"),
            "required_experiment_count": profile.get("required_experiment_count"),
            "path": str(project_dir / "workspace" / "project_profile.json"),
        },
        "policy": "Acceptance criteria evaluate workflow readiness only; they do not claim scientific reproduction success.",
    }


def acceptance_criteria_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing acceptance criteria summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "acceptance_criteria.json"
    markdown_path = project_dir / "workspace" / "ACCEPTANCE_CRITERIA.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "top_command": data.get("top_command"),
        "criteria_count": int(data.get("criteria_count", 0) or 0),
        "passed_count": int(data.get("passed_count", 0) or 0),
        "needs_work_count": int(data.get("needs_work_count", 0) or 0),
        "required_failed_count": int(data.get("required_failed_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _load_or_generate_profile(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "workspace" / "project_profile.json"
    profile = read_json(path, default=None)
    if isinstance(profile, dict):
        return profile
    return generate_project_profile(project_dir)


def _criterion(
    criterion_id: str,
    label: str,
    dimension: str,
    passed: bool,
    summary: str,
    observed: dict[str, Any],
    suggested_command: str,
) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "label": label,
        "dimension": dimension,
        "severity": "required",
        "status": "passed" if passed else "needs_work",
        "summary": summary,
        "observed": observed,
        "suggested_command": None if passed else suggested_command,
    }


def _render_markdown(criteria: dict[str, Any]) -> str:
    rows = [
        "| Criterion | Dimension | Status | Summary | Suggested command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in criteria["criteria"]:
        rows.append(
            "| {criterion} | {dimension} | {status} | {summary} | `{command}` |".format(
                criterion=_cell(item["criterion_id"]),
                dimension=_cell(item["dimension"]),
                status=_cell(item["status"]),
                summary=_cell(item["summary"]),
                command=_cell(item.get("suggested_command") or ""),
            )
        )
    return f"""# Acceptance Criteria

- schema_version: {criteria['schema_version']}
- created_at: {criteria['created_at']}
- project_name: {criteria['project_name']}
- status: {criteria['status']}
- top_command: {criteria['top_command']}
- criteria_count: {criteria['criteria_count']}
- passed_count: {criteria['passed_count']}
- needs_work_count: {criteria['needs_work_count']}

## Criteria

{chr(10).join(rows)}

## Profile

- profile_status: {criteria['profile']['status']}
- target_claim_count: {criteria['profile']['target_claim_count']}
- required_data_count: {criteria['profile']['required_data_count']}
- required_experiment_count: {criteria['profile']['required_experiment_count']}

## Policy

{criteria['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
