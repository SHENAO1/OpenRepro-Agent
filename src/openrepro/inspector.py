"""Project inspection summary for humans and agents."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .artifact_manager import latest_run_dir, list_run_dirs, validate_run_manifest
from .benchmark_runner import collect_benchmark_results
from .diagnostics import diagnose_project
from .document_loader import load_source_index
from .experiment_templates import inspect_experiment_scaffolds
from .project_manager import get_status
from .utils import iso_now, read_json, write_json


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _candidate_count(project_dir: Path, filename: str) -> int:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    return len(data.get("candidates", [])) if isinstance(data, dict) else 0


def _verified_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(data, dict):
        data = {}
    return {
        "status": data.get("status", "missing"),
        "formula_candidate_count": int(data.get("formula_candidate_count", 0) or 0),
        "parameter_candidate_count": int(data.get("parameter_candidate_count", 0) or 0),
        "path": str(project_dir / "workspace" / "verified_candidates.json") if data else None,
    }


def _candidate_review_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews = data.get("reviews", []) if isinstance(data, dict) else []
    counts = Counter(str(item.get("status")) for item in reviews if isinstance(item, dict))
    return {
        "status": "present" if reviews else "missing",
        "review_count": len(reviews),
        "status_counts": dict(counts),
    }


def _repair_dry_run_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "repair_dry_run.json", default={}) or {}
    if not isinstance(data, dict):
        data = {}
    return {
        "status": "present" if data else "missing",
        "created_at": data.get("created_at"),
        "healthy": data.get("healthy"),
        "action_count": int(data.get("action_count", 0) or 0),
        "path": str(project_dir / "workspace" / "repair_dry_run.json") if data else None,
    }


def _lineage_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "run_lineage.json", default={}) or {}
    if not isinstance(data, dict):
        data = {}
    complete_runs = 0
    for item in data.get("runs", []) if isinstance(data.get("runs", []), list) else []:
        if isinstance(item, dict) and item.get("provenance_complete"):
            complete_runs += 1
    return {
        "status": "present" if data else "missing",
        "created_at": data.get("created_at"),
        "run_count": int(data.get("run_count", 0) or 0),
        "complete_run_count": complete_runs,
        "path": str(project_dir / "workspace" / "run_lineage.json") if data else None,
    }


def _run_command_counts(run_dirs: list[Path]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for run_dir in run_dirs:
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        if isinstance(manifest, dict):
            counts[str(manifest.get("command") or "unknown")] += 1
        else:
            counts["unknown"] += 1
    return dict(counts)


def _benchmark_runs_for_project(project_dir: Path) -> list[dict[str, Any]]:
    runs_dirs = [Path.cwd() / "benchmarks" / "runs", _repo_root() / "benchmarks" / "runs"]
    seen: set[str] = set()
    matches: list[dict[str, Any]] = []
    project_name = project_dir.name
    project_strings = {str(project_dir), str(project_dir.resolve())}
    for runs_dir in runs_dirs:
        for result in collect_benchmark_results(runs_dir):
            result_path = str(result.get("_result_path", ""))
            if result_path in seen:
                continue
            seen.add(result_path)
            result_project = str(result.get("project_dir", ""))
            if result_project in project_strings or Path(result_project).name == project_name:
                matches.append(result)
    return matches


def inspect_project(project_dir: Path) -> dict[str, Any]:
    """Inspect a project and write workspace/inspect_summary.json."""
    project_dir = Path(project_dir)
    status = get_status(project_dir)
    source_index = load_source_index(project_dir)
    sources = source_index.get("sources", [])
    pdf_sources = [source for source in sources if source.get("suffix") == ".pdf"]
    pdf_status_counts = Counter(str(source.get("extraction_status") or "not_pdf") for source in pdf_sources)

    run_dirs = list_run_dirs(project_dir)
    latest = latest_run_dir(project_dir)
    latest_validation = validate_run_manifest(latest) if latest is not None else None
    latest_manifest_status = "missing"
    if latest_validation is not None:
        latest_manifest_status = "valid" if latest_validation.get("valid") else "invalid"
    diagnosis = diagnose_project(project_dir, latest)
    benchmark_runs = _benchmark_runs_for_project(project_dir)
    verified = _verified_summary(project_dir)
    reviews = _candidate_review_summary(project_dir)
    repair_dry_run = _repair_dry_run_summary(project_dir)
    lineage = _lineage_summary(project_dir)
    scaffolds = inspect_experiment_scaffolds(project_dir)
    run_command_counts = _run_command_counts(run_dirs)

    summary = {
        "schema_version": "0.9.0",
        "created_at": iso_now(),
        "project_name": status.project_name,
        "project_dir": str(project_dir),
        "source_count": len(sources),
        "pdf_source_count": len(pdf_sources),
        "pdf_extraction_statuses": dict(pdf_status_counts),
        "formula_candidate_count": _candidate_count(project_dir, "formula_candidates.json"),
        "parameter_candidate_count": _candidate_count(project_dir, "parameter_candidates.json"),
        "verified_formula_candidate_count": verified["formula_candidate_count"],
        "verified_parameter_candidate_count": verified["parameter_candidate_count"],
        "verified_candidates_status": verified["status"],
        "candidate_review_status": reviews["status"],
        "candidate_review_count": reviews["review_count"],
        "candidate_review_status_counts": reviews["status_counts"],
        "experiment_scaffold_count": scaffolds["scaffold_count"],
        "experiment_template_counts": scaffolds["template_counts"],
        "experiment_input_completeness_counts": scaffolds["input_completeness_counts"],
        "experiment_expected_artifacts_valid_count": scaffolds["expected_artifacts_valid_count"],
        "experiment_expected_artifacts_attention_count": scaffolds["expected_artifacts_attention_count"],
        "experiment_scaffold_issue_counts": scaffolds["issue_counts"],
        "experiment_scaffolds": scaffolds["scaffolds"],
        "run_count": len(run_dirs),
        "run_command_counts": run_command_counts,
        "experiment_run_count": run_command_counts.get("run-experiment", 0),
        "latest_run_dir": str(latest) if latest else None,
        "latest_manifest_status": latest_manifest_status,
        "latest_manifest_valid": latest_validation.get("valid") if latest_validation else None,
        "benchmark_run_count": len(benchmark_runs),
        "diagnosis_healthy": diagnosis.get("healthy"),
        "diagnosis_issue_count": len(diagnosis.get("issues", [])),
        "latest_repair_dry_run_status": repair_dry_run["status"],
        "latest_repair_dry_run_action_count": repair_dry_run["action_count"],
        "latest_repair_dry_run_healthy": repair_dry_run["healthy"],
        "lineage_status": lineage["status"],
        "lineage_run_count": lineage["run_count"],
        "lineage_complete_run_count": lineage["complete_run_count"],
        "next_step": status.next_step,
    }
    write_json(project_dir / "workspace" / "inspect_summary.json", summary)
    return summary
