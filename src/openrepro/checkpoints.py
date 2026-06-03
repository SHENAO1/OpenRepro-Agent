"""Workflow checkpoints for reproducibility projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file, validate_run_manifest
from .claim_trace import claim_trace_summary
from .data_registry import data_index_summary
from .document_loader import load_source_index
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .gaps import gaps_summary
from .quality_gate import quality_gate_summaries
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, safe_write_text, write_json

CHECKPOINT_SCHEMA_VERSION = "1.8.0"


def generate_workflow_checkpoints(project_dir: Path) -> dict[str, Any]:
    """Write workflow checkpoint artifacts under workspace/."""
    project_dir = Path(project_dir)
    checkpoints = _build_checkpoints(project_dir)
    actionable = [item for item in checkpoints if item["status"] != "complete"]
    result = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "complete" if not actionable else "needs_attention",
        "checkpoint_count": len(checkpoints),
        "complete_count": sum(1 for item in checkpoints if item["status"] == "complete"),
        "partial_count": sum(1 for item in checkpoints if item["status"] == "partial"),
        "blocked_count": sum(1 for item in checkpoints if item["status"] == "blocked"),
        "missing_count": sum(1 for item in checkpoints if item["status"] == "missing"),
        "next_checkpoint": actionable[0]["checkpoint_id"] if actionable else None,
        "next_command": actionable[0]["next_command"] if actionable else None,
        "checkpoints": checkpoints,
        "policy": "Workflow checkpoints summarize engineering progress only; they do not claim scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "workflow_checkpoints.json", result)
    safe_write_text(project_dir / "workspace" / "WORKFLOW_CHECKPOINTS.md", _render_checkpoints_markdown(result))
    return result


def checkpoint_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing checkpoint summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "workflow_checkpoints.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "checkpoint_count": int(data.get("checkpoint_count", 0) or 0),
        "complete_count": int(data.get("complete_count", 0) or 0),
        "partial_count": int(data.get("partial_count", 0) or 0),
        "blocked_count": int(data.get("blocked_count", 0) or 0),
        "missing_count": int(data.get("missing_count", 0) or 0),
        "next_checkpoint": data.get("next_checkpoint"),
        "next_command": data.get("next_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _build_checkpoints(project_dir: Path) -> list[dict[str, Any]]:
    source_index = load_source_index(project_dir)
    sources = source_index.get("sources", []) if isinstance(source_index, dict) else []
    analyzed = (project_dir / "workspace" / "paper_summary.md").exists() and (
        project_dir / "workspace" / "MODEL_LEDGER.md"
    ).exists()
    planned = (project_dir / "workspace" / "EXPERIMENT_PLAN.md").exists()
    candidate_count = _candidate_count(project_dir, "formula_candidates.json") + _candidate_count(
        project_dir, "parameter_candidates.json"
    )
    verified_count = _verified_count(project_dir)
    review_count = _review_count(project_dir)
    scaffolds = inspect_experiment_scaffolds(project_dir)
    specs = inspect_experiment_specs(project_dir)
    data = data_index_summary(project_dir)
    runs = list_run_dirs(project_dir)
    experiment_run_count = _experiment_run_count(project_dir)
    valid_run_count = sum(1 for run_dir in runs if validate_run_manifest(run_dir).get("valid"))
    gates = quality_gate_summaries(project_dir)
    trace = claim_trace_summary(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    lineage_exists = (project_dir / "workspace" / "run_lineage.json").exists()

    return [
        _checkpoint(
            "source_ingested",
            "Source Ingested",
            "complete" if sources else "missing",
            f"openrepro ingest {project_dir} --source <path>",
            {"source_count": len(sources)},
        ),
        _checkpoint(
            "analysis_ready",
            "Analysis Ready",
            "complete" if analyzed else "missing" if not sources else "partial",
            f"openrepro analyze {project_dir}",
            {"analyzed": analyzed, "candidate_count": candidate_count},
        ),
        _checkpoint(
            "plan_ready",
            "Plan Ready",
            "complete" if planned else "missing" if not analyzed else "partial",
            f"openrepro plan {project_dir}",
            {"planned": planned},
        ),
        _checkpoint(
            "candidates_reviewed",
            "Candidates Reviewed",
            _review_status(candidate_count, review_count, verified_count),
            f"openrepro review-candidates {project_dir} --candidate-id <id> --status verified_by_human --reviewer <name>",
            {"candidate_count": candidate_count, "review_count": review_count, "verified_count": verified_count},
        ),
        _checkpoint(
            "data_provenance",
            "Data Provenance",
            _data_status(data),
            f"openrepro validate-data {project_dir}",
            {
                "registered_count": data["registered_count"],
                "valid_count": data["valid_count"],
                "invalid_count": data["invalid_count"],
            },
        ),
        _checkpoint(
            "experiment_scaffold",
            "Experiment Scaffold",
            "complete" if scaffolds["scaffold_count"] else "missing" if verified_count == 0 else "partial",
            f"openrepro scaffold-experiment {project_dir} --experiment-id <id>",
            {"scaffold_count": scaffolds["scaffold_count"], "template_counts": scaffolds["template_counts"]},
        ),
        _checkpoint(
            "experiment_inputs",
            "Experiment Inputs",
            _input_status(scaffolds),
            f"openrepro validate-inputs {project_dir} --experiment-id <id>",
            {
                "missing_required_input_count": scaffolds["missing_required_input_count"],
                "input_completeness_counts": scaffolds["input_completeness_counts"],
            },
        ),
        _checkpoint(
            "experiment_specs",
            "Experiment Specs",
            _spec_status(specs),
            f"openrepro validate-experiment-spec {project_dir} --experiment-id <id>",
            {
                "status_counts": specs["status_counts"],
                "missing_count": specs["missing_count"],
                "invalid_count": specs["invalid_count"],
                "stale_count": specs["stale_count"],
            },
        ),
        _checkpoint(
            "run_evidence",
            "Run Evidence",
            _run_status(runs, valid_run_count, experiment_run_count, scaffolds["scaffold_count"]),
            f"openrepro run-experiment {project_dir} --experiment-id <id> --confirm",
            {
                "run_count": len(runs),
                "valid_run_count": valid_run_count,
                "experiment_run_count": experiment_run_count,
            },
        ),
        _checkpoint(
            "quality_gates",
            "Quality Gates",
            _gate_status(gates, runs),
            f"openrepro quality-gate {project_dir} --all",
            {
                "quality_gate_count": len(gates),
                "passed_count": sum(1 for gate in gates if gate.get("status") == "passed"),
                "failed_count": sum(1 for gate in gates if gate.get("status") == "failed"),
                "missing_count": sum(1 for gate in gates if gate.get("status") == "missing"),
            },
        ),
        _checkpoint(
            "lineage",
            "Run Lineage",
            "complete" if lineage_exists else "missing" if not runs else "partial",
            f"openrepro lineage {project_dir}",
            {"lineage_exists": lineage_exists, "run_count": len(runs)},
        ),
        _checkpoint(
            "claim_trace",
            "Claim Trace",
            _claim_trace_status(trace, candidate_count),
            f"openrepro trace-claims {project_dir} --validate",
            {
                "present": trace["present"],
                "claim_count": trace["claim_count"],
                "validation_status": trace["validation_status"],
                "validation_issue_count": trace["validation_issue_count"],
            },
        ),
        _checkpoint(
            "scorecard",
            "Readiness Scorecard",
            "complete" if scorecard["present"] else "missing",
            f"openrepro scorecard {project_dir}",
            {
                "present": scorecard["present"],
                "overall_score": scorecard["overall_score"],
                "overall_status": scorecard["overall_status"],
            },
        ),
        _checkpoint(
            "gaps",
            "Reproduction Gaps",
            _gaps_status(gaps),
            f"openrepro gaps {project_dir}",
            {
                "present": gaps["present"],
                "status": gaps["status"],
                "open_count": gaps["open_count"],
                "top_suggested_command": gaps["top_suggested_command"],
            },
        ),
    ]


def _candidate_count(project_dir: Path, filename: str) -> int:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    return len(data.get("candidates", [])) if isinstance(data, dict) else 0


def _verified_count(project_dir: Path) -> int:
    data = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(data, dict):
        return 0
    return int(data.get("formula_candidate_count", 0) or 0) + int(data.get("parameter_candidate_count", 0) or 0)


def _review_count(project_dir: Path) -> int:
    data = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews = data.get("reviews", []) if isinstance(data, dict) else []
    return len(reviews)


def _experiment_run_count(project_dir: Path) -> int:
    count = 0
    for run_dir in list_run_dirs(project_dir):
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        if isinstance(manifest, dict) and manifest.get("command") == "run-experiment":
            count += 1
    return count


def _review_status(candidate_count: int, review_count: int, verified_count: int) -> str:
    if candidate_count <= 0:
        return "missing"
    if verified_count > 0 and review_count > 0:
        return "complete"
    if verified_count > 0 or review_count > 0:
        return "partial"
    return "missing"


def _data_status(data: dict[str, Any]) -> str:
    if data["registered_count"] <= 0:
        return "missing"
    if data["invalid_count"] > 0:
        return "blocked"
    return "complete"


def _input_status(scaffolds: dict[str, Any]) -> str:
    if scaffolds["scaffold_count"] <= 0:
        return "missing"
    if scaffolds["missing_required_input_count"] > 0:
        return "blocked"
    if scaffolds["input_completeness_counts"].get("complete", 0) < scaffolds["scaffold_count"]:
        return "partial"
    return "complete"


def _spec_status(specs: dict[str, Any]) -> str:
    if specs["missing_count"] > 0 or specs["invalid_count"] > 0:
        return "blocked"
    if specs["stale_count"] > 0:
        return "partial"
    if specs["status_counts"]:
        return "complete"
    return "missing"


def _run_status(runs: list[Path], valid_run_count: int, experiment_run_count: int, scaffold_count: int) -> str:
    if not runs:
        return "missing" if scaffold_count <= 0 else "partial"
    if valid_run_count < len(runs):
        return "blocked"
    if experiment_run_count <= 0:
        return "partial"
    return "complete"


def _gate_status(gates: list[dict[str, Any]], runs: list[Path]) -> str:
    if not runs:
        return "missing"
    if not gates or any(gate.get("status") == "missing" for gate in gates):
        return "partial"
    if any(gate.get("status") == "failed" for gate in gates):
        return "blocked"
    return "complete"


def _claim_trace_status(trace: dict[str, Any], candidate_count: int) -> str:
    if candidate_count <= 0 and not trace["present"]:
        return "missing"
    if not trace["present"]:
        return "missing"
    if trace["validation_status"] == "passed":
        return "complete"
    if trace["validation_status"] == "missing":
        return "partial"
    return "blocked"


def _gaps_status(gaps: dict[str, Any]) -> str:
    if not gaps["present"]:
        return "missing"
    if gaps["open_count"] == 0:
        return "complete"
    if gaps["critical_count"] or gaps["high_count"]:
        return "blocked"
    return "partial"


def _checkpoint(
    checkpoint_id: str,
    label: str,
    status: str,
    next_command: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint_id,
        "label": label,
        "status": status,
        "next_command": None if status == "complete" else next_command,
        "details": details,
    }


def _render_checkpoints_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Workflow Checkpoints",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- complete_count: {result['complete_count']}",
        f"- partial_count: {result['partial_count']}",
        f"- blocked_count: {result['blocked_count']}",
        f"- missing_count: {result['missing_count']}",
        f"- next_checkpoint: {result['next_checkpoint']}",
        f"- next_command: {result['next_command']}",
        "",
        "## Checkpoints",
        "",
        "| Checkpoint | Status | Next command |",
        "| --- | --- | --- |",
    ]
    for item in result["checkpoints"]:
        lines.append(f"| {item['label']} | {item['status']} | {item.get('next_command') or ''} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
