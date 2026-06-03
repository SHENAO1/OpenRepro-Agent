"""Actionable reproduction workflow gaps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import latest_run_dir, list_run_dirs, sha256_file, validate_run_manifest
from .claim_trace import claim_trace_summary
from .data_registry import data_index_summary
from .diagnostics import diagnose_project
from .document_loader import load_source_index
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .quality_gate import quality_gate_summaries
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, safe_write_text, write_json

GAPS_SCHEMA_VERSION = "1.7.1"


def generate_reproduction_gaps(project_dir: Path) -> dict[str, Any]:
    """Write workspace/reproduction_gaps.json and Markdown."""
    project_dir = Path(project_dir)
    gaps: dict[str, dict[str, Any]] = {}
    _workflow_gaps(project_dir, gaps)
    _scorecard_gaps(project_dir, gaps)
    _diagnosis_gaps(project_dir, gaps)
    ordered = sorted(gaps.values(), key=lambda item: (_severity_rank(item["severity"]), item["gap_id"]))
    result = {
        "schema_version": GAPS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "clear" if not ordered else "open",
        "open_count": len(ordered),
        "critical_count": sum(1 for item in ordered if item["severity"] == "critical"),
        "high_count": sum(1 for item in ordered if item["severity"] == "high"),
        "medium_count": sum(1 for item in ordered if item["severity"] == "medium"),
        "low_count": sum(1 for item in ordered if item["severity"] == "low"),
        "top_suggested_command": ordered[0]["suggested_command"] if ordered else None,
        "gaps": ordered,
        "policy": "Reproduction gaps are actionable workflow to-dos only; closing them does not prove scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "reproduction_gaps.json", result)
    safe_write_text(project_dir / "workspace" / "REPRODUCTION_GAPS.md", _render_gaps_markdown(result))
    return result


def gaps_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing gaps summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "reproduction_gaps.json"
    gaps = read_json(path, default={}) or {}
    gaps = gaps if isinstance(gaps, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": gaps.get("schema_version"),
        "status": gaps.get("status", "missing") if path.exists() else "missing",
        "open_count": int(gaps.get("open_count", 0) or 0),
        "critical_count": int(gaps.get("critical_count", 0) or 0),
        "high_count": int(gaps.get("high_count", 0) or 0),
        "medium_count": int(gaps.get("medium_count", 0) or 0),
        "low_count": int(gaps.get("low_count", 0) or 0),
        "top_suggested_command": gaps.get("top_suggested_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _workflow_gaps(project_dir: Path, gaps: dict[str, dict[str, Any]]) -> None:
    sources = load_source_index(project_dir).get("sources", [])
    analyzed = (project_dir / "workspace" / "paper_summary.md").exists() and (
        project_dir / "workspace" / "MODEL_LEDGER.md"
    ).exists()
    planned = (project_dir / "workspace" / "EXPERIMENT_PLAN.md").exists()
    formula_count = _candidate_count(project_dir, "formula_candidates.json")
    parameter_count = _candidate_count(project_dir, "parameter_candidates.json")
    candidate_count = formula_count + parameter_count
    verified_count = _verified_count(project_dir)
    review_count = _review_count(project_dir)
    scaffolds = inspect_experiment_scaffolds(project_dir)
    specs = inspect_experiment_specs(project_dir)
    data = data_index_summary(project_dir)
    run_dirs = list_run_dirs(project_dir)
    experiment_run_count = _experiment_run_count(project_dir)
    gates = quality_gate_summaries(project_dir)
    trace = claim_trace_summary(project_dir)
    scorecard = scorecard_summary(project_dir)

    if not sources:
        _add_gap(gaps, "source_missing", "critical", "source_index", "No source material ingested.", f"openrepro ingest {project_dir} --source <path>")
    if sources and not analyzed:
        _add_gap(gaps, "analysis_missing", "high", "analysis", "Paper summary and model ledger are missing.", f"openrepro analyze {project_dir}")
    if analyzed and not planned:
        _add_gap(gaps, "plan_missing", "high", "planning", "Experiment plan is missing.", f"openrepro plan {project_dir}")
    if candidate_count > 0 and review_count == 0:
        _add_gap(gaps, "candidate_reviews_missing", "high", "candidate_review", "Candidate review history is missing.", f"openrepro list-candidates {project_dir}")
    if candidate_count > 0 and verified_count == 0:
        _add_gap(
            gaps,
            "verified_candidates_missing",
            "high",
            "candidate_review",
            "No candidates have been promoted to verified inputs.",
            f"openrepro review-candidates {project_dir} --candidate-id <id> --status verified_by_human --reviewer <name>",
        )
    if verified_count > 0 and scaffolds["scaffold_count"] == 0:
        _add_gap(gaps, "experiment_scaffold_missing", "high", "experiment", "No experiment scaffold exists.", f"openrepro scaffold-experiment {project_dir} --experiment-id <id>")
    if scaffolds["missing_required_input_count"] > 0:
        _add_gap(gaps, "experiment_inputs_incomplete", "high", "experiment_inputs", "Experiment inputs are incomplete.", f"openrepro validate-inputs {project_dir} --experiment-id <id>")
    if specs["missing_count"] > 0 or specs["invalid_count"] > 0:
        _add_gap(gaps, "experiment_specs_invalid", "high", "experiment_spec", "Experiment specs are missing or invalid.", f"openrepro validate-experiment-spec {project_dir} --experiment-id <id>")
    elif specs["stale_count"] > 0:
        _add_gap(gaps, "experiment_specs_stale", "medium", "experiment_spec", "Experiment specs are stale.", f"openrepro validate-experiment-spec {project_dir} --experiment-id <id>")
    if data["invalid_count"] > 0:
        _add_gap(gaps, "registered_data_invalid", "high", "data_registry", "Registered data has missing files or hash mismatches.", f"openrepro validate-data {project_dir}")
    if run_dirs and any(not validate_run_manifest(run_dir).get("valid") for run_dir in run_dirs):
        _add_gap(gaps, "run_manifest_invalid", "critical", "run_manifest", "One or more run manifests are invalid.", f"openrepro validate {project_dir} --all")
    if scaffolds["scaffold_count"] > 0 and experiment_run_count == 0:
        _add_gap(gaps, "experiment_runs_missing", "high", "run_evidence", "Experiment scaffolds exist but no experiment run evidence is present.", f"openrepro run-experiment {project_dir} --experiment-id <id> --confirm")
    if run_dirs and any(gate.get("status") == "missing" for gate in gates):
        _add_gap(gaps, "quality_gates_missing", "high", "quality_gate", "One or more runs are missing quality gate reports.", f"openrepro quality-gate {project_dir} --all")
    if any(gate.get("status") == "failed" for gate in gates):
        _add_gap(gaps, "quality_gates_failed", "critical", "quality_gate", "One or more quality gates failed.", f"openrepro quality-gate {project_dir} --all")
    if run_dirs and not (project_dir / "workspace" / "run_lineage.json").exists():
        _add_gap(gaps, "lineage_missing", "medium", "lineage", "Run lineage artifacts are missing.", f"openrepro lineage {project_dir}")
    if candidate_count > 0 and not trace["present"]:
        _add_gap(gaps, "claim_trace_missing", "high", "claim_trace", "Claim trace artifacts are missing.", f"openrepro trace-claims {project_dir} --validate")
    elif trace["present"] and trace["validation_status"] != "passed":
        _add_gap(gaps, "claim_trace_validation_failed", "high", "claim_trace", "Claim trace validation is missing or failed.", f"openrepro validate-claims {project_dir}")
    if not scorecard["present"]:
        _add_gap(gaps, "scorecard_missing", "medium", "scorecard", "Readiness scorecard is missing.", f"openrepro scorecard {project_dir}")


def _scorecard_gaps(project_dir: Path, gaps: dict[str, dict[str, Any]]) -> None:
    scorecard = read_json(project_dir / "workspace" / "reproduction_scorecard.json", default={}) or {}
    if not isinstance(scorecard, dict):
        return
    for dimension in scorecard.get("dimensions", []):
        if not isinstance(dimension, dict) or dimension.get("status") == "ready":
            continue
        actions = dimension.get("recommendations", []) if isinstance(dimension.get("recommendations"), list) else []
        suggested = str(actions[0]) if actions else f"openrepro inspect {project_dir}"
        severity = "high" if dimension.get("status") == "blocked" else "medium"
        _add_gap(
            gaps,
            f"scorecard_{dimension.get('key')}",
            severity,
            "scorecard",
            f"Scorecard dimension needs attention: {dimension.get('label')} ({dimension.get('score')}).",
            suggested,
            details={"dimension": dimension},
        )


def _diagnosis_gaps(project_dir: Path, gaps: dict[str, dict[str, Any]]) -> None:
    diagnosis = diagnose_project(project_dir, latest_run_dir(project_dir))
    for item in diagnosis.get("issues", []):
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "diagnosis_issue")
        _add_gap(
            gaps,
            f"diagnosis_{code}",
            _diagnosis_severity(code),
            "diagnostics",
            str(item.get("message") or code),
            f"openrepro diagnose {project_dir}",
            details=item,
        )


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


def _add_gap(
    gaps: dict[str, dict[str, Any]],
    gap_id: str,
    severity: str,
    source: str,
    title: str,
    suggested_command: str,
    details: dict[str, Any] | None = None,
) -> None:
    if gap_id in gaps:
        return
    gaps[gap_id] = {
        "gap_id": gap_id,
        "severity": severity,
        "source": source,
        "title": title,
        "suggested_command": suggested_command,
        "details": details or {},
        "status": "open",
    }


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity, 4)


def _diagnosis_severity(code: str) -> str:
    if code in {"manifest_mismatch", "missing_manifest", "quality_gate_failed"}:
        return "critical"
    if code.startswith("quality_gate_") or code.startswith("claim_trace_"):
        return "high"
    return "medium"


def _render_gaps_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Reproduction Gaps",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- open_count: {result['open_count']}",
        f"- critical_count: {result['critical_count']}",
        f"- high_count: {result['high_count']}",
        f"- medium_count: {result['medium_count']}",
        f"- top_suggested_command: {result['top_suggested_command']}",
        "",
        "## Gaps",
        "",
        "| Severity | Source | Gap | Suggested command |",
        "| --- | --- | --- | --- |",
    ]
    if result["gaps"]:
        for gap in result["gaps"]:
            lines.append(
                "| {severity} | {source} | {title} | `{command}` |".format(
                    severity=gap["severity"],
                    source=gap["source"],
                    title=gap["title"],
                    command=gap["suggested_command"],
                )
            )
    else:
        lines.append("| none | workflow | No open upstream reproduction workflow gaps found. |  |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
