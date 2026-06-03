"""Reproduction readiness scorecards for workflow evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file, validate_run_manifest
from .claim_trace import claim_trace_summary
from .data_registry import data_index_summary
from .document_loader import load_source_index
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .quality_gate import quality_gate_summaries
from .utils import iso_now, read_json, safe_write_text, write_json

SCORECARD_SCHEMA_VERSION = "1.7.0"


def generate_reproduction_scorecard(project_dir: Path) -> dict[str, Any]:
    """Write workspace/reproduction_scorecard.json and Markdown."""
    project_dir = Path(project_dir)
    dimensions = _dimensions(project_dir)
    total_weight = sum(item["weight"] for item in dimensions)
    weighted_score = round(sum(item["score"] * item["weight"] for item in dimensions) / total_weight, 2) if total_weight else 0.0
    blocking = [item for item in dimensions if item["status"] in {"missing", "blocked"}]
    partial = [item for item in dimensions if item["status"] == "partial"]
    result = {
        "schema_version": SCORECARD_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "overall_score": weighted_score,
        "overall_status": _overall_status(weighted_score, len(blocking)),
        "dimension_count": len(dimensions),
        "blocking_dimension_count": len(blocking),
        "partial_dimension_count": len(partial),
        "dimensions": dimensions,
        "recommended_actions": _recommended_actions(dimensions),
        "policy": "Readiness scorecards summarize workflow evidence completeness only; they are not scientific reproduction scores.",
    }
    write_json(project_dir / "workspace" / "reproduction_scorecard.json", result)
    safe_write_text(project_dir / "workspace" / "REPRODUCTION_SCORECARD.md", _render_scorecard_markdown(result))
    return result


def scorecard_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing scorecard summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "reproduction_scorecard.json"
    scorecard = read_json(path, default={}) or {}
    scorecard = scorecard if isinstance(scorecard, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": scorecard.get("schema_version"),
        "overall_score": float(scorecard.get("overall_score", 0) or 0),
        "overall_status": scorecard.get("overall_status", "missing") if path.exists() else "missing",
        "blocking_dimension_count": int(scorecard.get("blocking_dimension_count", 0) or 0),
        "partial_dimension_count": int(scorecard.get("partial_dimension_count", 0) or 0),
        "dimension_count": int(scorecard.get("dimension_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _dimensions(project_dir: Path) -> list[dict[str, Any]]:
    source_index = load_source_index(project_dir)
    sources = source_index.get("sources", []) if isinstance(source_index, dict) else []
    formula_candidates = _candidate_count(project_dir, "formula_candidates.json")
    parameter_candidates = _candidate_count(project_dir, "parameter_candidates.json")
    candidate_count = formula_candidates + parameter_candidates
    reviews = _candidate_review_summary(project_dir)
    verified = _verified_summary(project_dir)
    scaffolds = inspect_experiment_scaffolds(project_dir)
    specs = inspect_experiment_specs(project_dir)
    data = data_index_summary(project_dir)
    runs = _run_summary(project_dir)
    gates = quality_gate_summaries(project_dir)
    trace = claim_trace_summary(project_dir)
    comparison = read_json(project_dir / "workspace" / "experiment_comparison.json", default={}) or {}
    comparison = comparison if isinstance(comparison, dict) else {}

    return [
        _dimension(
            "paper_evidence",
            "Paper Evidence",
            _score_bool(bool(sources), 40)
            + _score_bool(candidate_count > 0, 30)
            + _score_bool((project_dir / "workspace" / "paper_metadata.json").exists(), 15)
            + _score_bool((project_dir / "workspace" / "caption_index.json").exists(), 15),
            1.1,
            {
                "source_count": len(sources),
                "formula_candidate_count": formula_candidates,
                "parameter_candidate_count": parameter_candidates,
                "paper_metadata_present": (project_dir / "workspace" / "paper_metadata.json").exists(),
                "caption_index_present": (project_dir / "workspace" / "caption_index.json").exists(),
            },
            ["Run `openrepro ingest`, `openrepro analyze`, and inspect candidate provenance."],
        ),
        _dimension(
            "candidate_review",
            "Candidate Review",
            _candidate_review_score(candidate_count, verified["total_count"], reviews["review_count"]),
            1.0,
            {
                "candidate_count": candidate_count,
                "verified_candidate_count": verified["total_count"],
                "candidate_review_count": reviews["review_count"],
                "review_status_counts": reviews["status_counts"],
            },
            ["Run `openrepro list-candidates`, `openrepro review-candidates`, and `openrepro approve-candidates`."],
        ),
        _dimension(
            "data_provenance",
            "Data Provenance",
            _ratio_score(data["valid_count"], data["registered_count"]),
            1.0,
            {
                "registered_count": data["registered_count"],
                "valid_count": data["valid_count"],
                "invalid_count": data["invalid_count"],
                "status_counts": data["status_counts"],
            },
            ["Run `openrepro register-data` and `openrepro validate-data`."],
        ),
        _dimension(
            "experiment_specs",
            "Experiment Specs",
            _experiment_spec_score(scaffolds["scaffold_count"], specs),
            1.1,
            {
                "experiment_scaffold_count": scaffolds["scaffold_count"],
                "spec_status_counts": specs["status_counts"],
                "missing_count": specs["missing_count"],
                "invalid_count": specs["invalid_count"],
                "stale_count": specs["stale_count"],
            },
            ["Run `openrepro scaffold-experiment` and `openrepro validate-experiment-spec`."],
        ),
        _dimension(
            "run_evidence",
            "Run Evidence",
            _run_evidence_score(runs),
            1.1,
            runs,
            ["Run `openrepro run-experiment`, `openrepro run-demo`, and `openrepro validate --all`."],
        ),
        _dimension(
            "quality_gates",
            "Quality Gates",
            _ratio_score(sum(1 for gate in gates if gate.get("status") == "passed"), len(gates)),
            1.0,
            {
                "quality_gate_count": len(gates),
                "passed_count": sum(1 for gate in gates if gate.get("status") == "passed"),
                "failed_count": sum(1 for gate in gates if gate.get("status") == "failed"),
                "missing_count": sum(1 for gate in gates if gate.get("status") == "missing"),
                "failed_check_names": sorted({name for gate in gates for name in gate.get("failed_check_names", [])}),
            },
            ["Run `openrepro quality-gate --all` and address failed checks."],
        ),
        _dimension(
            "repeatability_evidence",
            "Repeatability Evidence",
            _repeatability_score(runs["experiment_run_count"], comparison),
            0.8,
            {
                "experiment_run_count": runs["experiment_run_count"],
                "comparison_present": bool(comparison),
                "all_metrics_equal": comparison.get("all_metrics_equal"),
                "warning_count": len(comparison.get("warnings", [])) if isinstance(comparison.get("warnings"), list) else 0,
            },
            ["Run `openrepro rerun-experiment` and `openrepro compare-experiments`."],
        ),
        _dimension(
            "claim_trace_health",
            "Claim Trace Health",
            _claim_trace_score(trace),
            1.2,
            {
                "claim_trace_present": trace["present"],
                "claim_count": trace["claim_count"],
                "verified_claim_count": trace["verified_claim_count"],
                "experiment_trace_count": trace["experiment_trace_count"],
                "run_trace_count": trace["run_trace_count"],
                "validation_status": trace["validation_status"],
                "validation_issue_count": trace["validation_issue_count"],
            },
            ["Run `openrepro trace-claims --validate` and inspect `CLAIM_TRACE_VALIDATION.md`."],
        ),
    ]


def _candidate_count(project_dir: Path, filename: str) -> int:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    return len(data.get("candidates", [])) if isinstance(data, dict) else 0


def _candidate_review_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews = data.get("reviews", []) if isinstance(data, dict) else []
    counts: dict[str, int] = {}
    for review in reviews:
        if isinstance(review, dict):
            status = str(review.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
    return {"review_count": len(reviews), "status_counts": counts}


def _verified_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(data, dict):
        data = {}
    formula_count = int(data.get("formula_candidate_count", 0) or 0)
    parameter_count = int(data.get("parameter_candidate_count", 0) or 0)
    return {
        "formula_count": formula_count,
        "parameter_count": parameter_count,
        "total_count": formula_count + parameter_count,
    }


def _run_summary(project_dir: Path) -> dict[str, Any]:
    run_dirs = list_run_dirs(project_dir)
    valid_manifests = 0
    experiment_run_count = 0
    command_counts: dict[str, int] = {}
    for run_dir in run_dirs:
        validation = validate_run_manifest(run_dir)
        if validation.get("valid"):
            valid_manifests += 1
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        command = str(manifest.get("command") or "unknown") if isinstance(manifest, dict) else "unknown"
        command_counts[command] = command_counts.get(command, 0) + 1
        if command == "run-experiment":
            experiment_run_count += 1
    return {
        "run_count": len(run_dirs),
        "valid_manifest_count": valid_manifests,
        "invalid_manifest_count": len(run_dirs) - valid_manifests,
        "experiment_run_count": experiment_run_count,
        "command_counts": command_counts,
    }


def _score_bool(value: bool, points: int) -> int:
    return points if value else 0


def _ratio_score(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (numerator / denominator) * 100)), 2)


def _candidate_review_score(candidate_count: int, verified_count: int, review_count: int) -> float:
    if candidate_count <= 0:
        return 0.0
    verified_score = min(70.0, (verified_count / candidate_count) * 70)
    review_score = 30.0 if review_count > 0 else 0.0
    return round(verified_score + review_score, 2)


def _experiment_spec_score(scaffold_count: int, specs: dict[str, Any]) -> float:
    if scaffold_count <= 0:
        return 0.0
    penalty = specs["missing_count"] * 35 + specs["invalid_count"] * 45 + specs["stale_count"] * 20
    return float(max(0, min(100, 100 - penalty)))


def _run_evidence_score(runs: dict[str, Any]) -> float:
    if runs["run_count"] <= 0:
        return 0.0
    score = 20.0
    if runs["experiment_run_count"] > 0:
        score += 40.0
    score += min(40.0, _ratio_score(runs["valid_manifest_count"], runs["run_count"]) * 0.4)
    return round(score, 2)


def _repeatability_score(experiment_run_count: int, comparison: dict[str, Any]) -> float:
    if experiment_run_count <= 0:
        return 0.0
    if experiment_run_count == 1:
        return 40.0
    if comparison and comparison.get("all_metrics_equal") is True:
        return 100.0
    if comparison:
        return 80.0
    return 70.0


def _claim_trace_score(trace: dict[str, Any]) -> float:
    if not trace["present"]:
        return 0.0
    if trace["validation_status"] == "passed":
        return 100.0
    if trace["validation_status"] == "missing":
        return 60.0
    return 40.0


def _dimension(
    key: str,
    label: str,
    score: float,
    weight: float,
    details: dict[str, Any],
    recommendations: list[str],
) -> dict[str, Any]:
    score = round(max(0.0, min(100.0, score)), 2)
    return {
        "key": key,
        "label": label,
        "score": score,
        "weight": weight,
        "status": _dimension_status(score),
        "details": details,
        "recommendations": [] if score >= 90 else recommendations,
    }


def _dimension_status(score: float) -> str:
    if score >= 90:
        return "ready"
    if score >= 60:
        return "partial"
    if score > 0:
        return "blocked"
    return "missing"


def _overall_status(score: float, blocking_count: int) -> str:
    if score >= 90 and blocking_count == 0:
        return "ready"
    if score >= 60:
        return "partial"
    return "blocked"


def _recommended_actions(dimensions: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for item in sorted(dimensions, key=lambda dimension: (dimension["score"], -dimension["weight"])):
        for action in item["recommendations"]:
            if action not in actions:
                actions.append(action)
    return actions[:8]


def _render_scorecard_markdown(scorecard: dict[str, Any]) -> str:
    lines = [
        "# Reproduction Readiness Scorecard",
        "",
        f"- schema_version: {scorecard['schema_version']}",
        f"- overall_score: {scorecard['overall_score']}",
        f"- overall_status: {scorecard['overall_status']}",
        f"- blocking_dimension_count: {scorecard['blocking_dimension_count']}",
        f"- partial_dimension_count: {scorecard['partial_dimension_count']}",
        "",
        "## Dimensions",
        "",
        "| Dimension | Score | Status | Weight |",
        "| --- | --- | --- | --- |",
    ]
    for item in scorecard["dimensions"]:
        lines.append(f"| {item['label']} | {item['score']} | {item['status']} | {item['weight']} |")
    lines.extend(["", "## Recommended Actions", ""])
    if scorecard["recommended_actions"]:
        lines.extend(f"- {action}" for action in scorecard["recommended_actions"])
    else:
        lines.append("- No scorecard actions are currently recommended.")
    lines.extend(["", "## Policy", "", scorecard["policy"], ""])
    return "\n".join(lines)
