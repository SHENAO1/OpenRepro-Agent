"""Project inspection summary for humans and agents."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .artifact_manager import latest_run_dir, list_run_dirs, validate_run_manifest
from .benchmark_runner import collect_benchmark_results
from .diagnostics import diagnose_project
from .document_loader import load_source_index
from .project_manager import get_status
from .utils import iso_now, read_json, write_json


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _candidate_count(project_dir: Path, filename: str) -> int:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    return len(data.get("candidates", [])) if isinstance(data, dict) else 0


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

    summary = {
        "schema_version": "0.3.1",
        "created_at": iso_now(),
        "project_name": status.project_name,
        "project_dir": str(project_dir),
        "source_count": len(sources),
        "pdf_source_count": len(pdf_sources),
        "pdf_extraction_statuses": dict(pdf_status_counts),
        "formula_candidate_count": _candidate_count(project_dir, "formula_candidates.json"),
        "parameter_candidate_count": _candidate_count(project_dir, "parameter_candidates.json"),
        "run_count": len(run_dirs),
        "latest_run_dir": str(latest) if latest else None,
        "latest_manifest_status": latest_manifest_status,
        "latest_manifest_valid": latest_validation.get("valid") if latest_validation else None,
        "benchmark_run_count": len(benchmark_runs),
        "diagnosis_healthy": diagnosis.get("healthy"),
        "diagnosis_issue_count": len(diagnosis.get("issues", [])),
        "next_step": status.next_step,
    }
    write_json(project_dir / "workspace" / "inspect_summary.json", summary)
    return summary
