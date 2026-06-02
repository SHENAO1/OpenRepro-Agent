"""Benchmark runner for workflow-compliance evidence."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import __version__
from .analyzer import analyze_project
from .api_usage import write_mock_usage_files
from .artifact_manager import latest_run_dir, validate_run_manifest, write_run_manifest
from .diagnostics import diagnose_error, diagnose_validation_result
from .demo_runner import run_demo, run_sweep
from .document_loader import ingest_source
from .planner import generate_experiment_plan
from .project_manager import init_project, require_project
from .provider import ProviderRequest, complete_with_cache, get_provider
from .utils import iso_now, local_timestamp_for_path, read_json, safe_write_text, slugify, write_json


BENCHMARK_SCHEMA_VERSION = "0.6.0"
REQUIRED_TASK_FIELDS = ["task_id", "paper_title", "source_files"]
PROVENANCE_FIELDS = ["dataset", "environment", "dependencies", "paper_source", "expected_runtime_notes"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_benchmark_task(task_path: Path) -> dict[str, Any]:
    """Load and validate a benchmark task."""
    task_path = Path(task_path)
    task = read_json(task_path, default=None)
    if not isinstance(task, dict):
        raise ValueError(f"Invalid task schema: task file is not JSON object: {task_path}")
    missing = [field for field in REQUIRED_TASK_FIELDS if field not in task]
    if missing:
        raise ValueError(f"Invalid task schema: missing required fields: {', '.join(missing)}")
    if not isinstance(task.get("source_files"), list) or not task["source_files"]:
        raise ValueError("Invalid task schema: source_files must be a non-empty array")
    artifacts = task.get("artifacts") or {}
    metrics = task.get("metrics") or {}
    workflow_raw = task.get("workflow") or {}
    pass_criteria_raw = task.get("pass_criteria") or {}
    if "expected_artifacts" in task and not isinstance(task.get("expected_artifacts"), list):
        raise ValueError("Invalid task schema: expected_artifacts must be an array")
    if "evaluation_metrics" in task and not isinstance(task.get("evaluation_metrics"), list):
        raise ValueError("Invalid task schema: evaluation_metrics must be an array")
    if not isinstance(artifacts, dict):
        raise ValueError("Invalid task schema: artifacts must be an object")
    if not isinstance(metrics, dict):
        raise ValueError("Invalid task schema: metrics must be an object")
    if not isinstance(workflow_raw, dict):
        raise ValueError("Invalid task schema: workflow must be an object")
    if not isinstance(pass_criteria_raw, dict):
        raise ValueError("Invalid task schema: pass_criteria must be an object")
    for section_name, section in [("artifacts", artifacts), ("metrics", metrics)]:
        for field_name in ["required", "optional"]:
            if field_name in section and not isinstance(section.get(field_name), list):
                raise ValueError(f"Invalid task schema: {section_name}.{field_name} must be an array")
    workflow = {"run_demo": True, "run_sweep": False}
    workflow.update(workflow_raw)
    pass_criteria = {"require_manifest_valid": True}
    pass_criteria.update(pass_criteria_raw)

    task["artifacts"] = {
        "required": list(artifacts.get("required", task.get("expected_artifacts", []))),
        "optional": list(artifacts.get("optional", [])),
    }
    task["metrics"] = {
        "required": list(metrics.get("required", task.get("evaluation_metrics", []))),
        "optional": list(metrics.get("optional", [])),
    }
    task["workflow"] = {
        "run_demo": bool(workflow.get("run_demo", True)),
        "run_sweep": bool(workflow.get("run_sweep", False)),
    }
    task["pass_criteria"] = {
        "require_manifest_valid": bool(pass_criteria.get("require_manifest_valid", True)),
    }
    task["provenance"] = {
        "dataset": task.get("dataset"),
        "environment": task.get("environment"),
        "dependencies": task.get("dependencies"),
        "paper_source": task.get("paper_source"),
        "expected_runtime_notes": task.get("expected_runtime_notes"),
    }
    task["provenance_complete"] = all(bool(task["provenance"].get(field)) for field in PROVENANCE_FIELDS)
    task.setdefault("schema_version", BENCHMARK_SCHEMA_VERSION)
    return task


def _resolve_source(task_path: Path, source: str) -> Path:
    raw = Path(source)
    candidates = [raw] if raw.is_absolute() else [task_path.parent / raw, Path.cwd() / raw, _repo_root() / raw]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Source file not found for benchmark task: {source}")


def _benchmark_root(task_path: Path) -> Path:
    if task_path.parent.name == "benchmarks":
        return task_path.parent / "runs"
    return Path.cwd() / "benchmarks" / "runs"


def _benchmark_run_dir(task_path: Path, task_id: str) -> Path:
    root = _benchmark_root(task_path)
    root.mkdir(parents=True, exist_ok=True)
    base = root / f"{local_timestamp_for_path()}_{slugify(task_id)}"
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = root / f"{base.name}_{counter}"
        counter += 1
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _benchmark_suite_dir(suite_path: Path, suite_id: str) -> Path:
    root = _benchmark_root(suite_path)
    root.mkdir(parents=True, exist_ok=True)
    base = root / f"{local_timestamp_for_path()}_{slugify(suite_id)}_suite"
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = root / f"{base.name}_{counter}"
        counter += 1
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _resolve_expected_artifact(project_dir: Path, latest: Path | None, pattern: str) -> Path:
    normalized = pattern.replace("\\", "/")
    marker = "outputs/<timestamp>_<project>/"
    if normalized.startswith(marker) and latest is not None:
        return latest / normalized[len(marker) :]
    return project_dir / normalized


def _artifact_checks(project_dir: Path, latest: Path | None, expected: list[str], required: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for pattern in expected:
        path = _resolve_expected_artifact(project_dir, latest, str(pattern))
        checks.append(
            {
                "pattern": pattern,
                "resolved_path": str(path),
                "exists": path.exists(),
                "required": required,
            }
        )
    return checks


def _metric_checks(latest: Path | None, expected_metrics: list[str], required: bool) -> list[dict[str, Any]]:
    metrics: dict[str, Any] = {}
    if latest is not None:
        metrics = read_json(latest / "data" / "demo_metrics.json", default={}) or {}
    return [
        {
            "metric": str(metric),
            "available": str(metric) in metrics,
            "value": metrics.get(str(metric)),
            "required": required,
        }
        for metric in expected_metrics
    ]


def _write_benchmark_report(run_dir: Path, result: dict[str, Any]) -> Path:
    artifact_passed = sum(1 for item in result["artifact_checks"] if item["exists"])
    metric_passed = sum(1 for item in result["metric_checks"] if item["available"])
    issues = result.get("diagnosis", [])
    issue_lines = "\n".join(
        f"- {item['code']}: {item['message']} | repair: {item['repair_suggestion']}" for item in issues
    ) or "- No diagnosis issues."
    report = f"""# Benchmark Report

## Task

- task_id: {result['task_id']}
- paper_title: {result['paper_title']}
- status: {result['status']}

## Workflow Evidence

- project_dir: `{result['project_dir']}`
- latest_run_dir: `{result.get('latest_run_dir')}`
- manifest_valid: {result['manifest_validation'].get('valid')}
- expected_artifacts_passed: {artifact_passed}/{len(result['artifact_checks'])}
- expected_metrics_available: {metric_passed}/{len(result['metric_checks'])}
- provenance_complete: {result.get('provenance_complete')}

## Provenance

```json
{result.get('provenance')}
```

## Diagnosis

{issue_lines}

## Policy

This benchmark report describes workflow-compliance evidence only. It does not claim paper reproduction success or benchmark scores.
"""
    path = run_dir / "benchmark_report.md"
    safe_write_text(path, report)
    return path


def run_benchmark(task_path: Path, project_name: str | None = None) -> dict[str, Any]:
    """Run a benchmark task and write workflow-compliance evidence."""
    task_path = Path(task_path)
    task = load_benchmark_task(task_path)
    task_id = str(task["task_id"])
    project = project_name or task_id
    project_dir = Path(project)
    if not project_dir.exists():
        init_project(project)
    project_dir = require_project(project)

    benchmark_dir = _benchmark_run_dir(task_path, task_id)
    api_usage_dir = benchmark_dir / "api_usage"
    provider = get_provider("mock")

    diagnosis: list[dict[str, str]] = []
    try:
        for source in task["source_files"]:
            ingest_source(project_dir, _resolve_source(task_path, str(source)))
        analyze_project(project_dir)
        generate_experiment_plan(project_dir)
        if task["workflow"]["run_demo"]:
            run_demo(project_dir)
        if task["workflow"]["run_sweep"]:
            run_sweep(project_dir)
    except Exception as exc:
        diagnosis.append(diagnose_error(str(exc), source="benchmark_flow"))

    latest = latest_run_dir(project_dir)
    validation = validate_run_manifest(latest) if latest is not None else {
        "valid": False,
        "errors": ["No run directory found after benchmark flow."],
        "warnings": [],
        "checked_artifacts": 0,
    }
    if task["pass_criteria"]["require_manifest_valid"] and not validation.get("valid"):
        diagnosis.extend(diagnose_validation_result(validation))

    artifact_checks = _artifact_checks(project_dir, latest, [str(item) for item in task["artifacts"]["required"]], True)
    artifact_checks.extend(
        _artifact_checks(project_dir, latest, [str(item) for item in task["artifacts"]["optional"]], False)
    )
    metric_checks = _metric_checks(latest, [str(item) for item in task["metrics"]["required"]], True)
    metric_checks.extend(_metric_checks(latest, [str(item) for item in task["metrics"]["optional"]], False))
    for item in artifact_checks:
        if item["required"] and not item["exists"]:
            diagnosis.append(diagnose_error(f"Missing required artifact: {item['pattern']}", source="benchmark"))
    for item in metric_checks:
        if item["required"] and not item["available"]:
            diagnosis.append(diagnose_error(f"Missing evaluation metric: {item['metric']}", source="benchmark"))

    summary_request = ProviderRequest(
        task="benchmark-summary",
        prompt=f"Summarize benchmark task {task_id} for project {project_dir}.",
        metadata={"task_id": task_id, "project": str(project_dir)},
    )
    provider_response = complete_with_cache(
        provider,
        summary_request,
        cache_dir=project_dir / "workspace" / "provider_cache",
        api_usage_dir=api_usage_dir,
    )
    write_mock_usage_files(api_usage_dir, task="benchmark")

    manifest_passed = validation.get("valid") or not task["pass_criteria"]["require_manifest_valid"]
    status = "passed" if manifest_passed and all(
        item["exists"] for item in artifact_checks if item["required"]
    ) and all(
        item["available"] for item in metric_checks if item["required"]
    ) else "needs_review"
    result = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "openrepro_version": __version__,
        "task_id": task_id,
        "paper_title": task["paper_title"],
        "project_dir": str(project_dir),
        "benchmark_dir": str(benchmark_dir),
        "created_at": iso_now(),
        "status": status,
        "latest_run_dir": str(latest) if latest else None,
        "manifest_validation": validation,
        "artifact_checks": artifact_checks,
        "metric_checks": metric_checks,
        "workflow": task["workflow"],
        "pass_criteria": task["pass_criteria"],
        "provenance": task["provenance"],
        "provenance_complete": task["provenance_complete"],
        "provider_response": provider_response.to_dict(),
        "diagnosis": diagnosis,
        "policy": "Workflow-compliance evidence only; no paper reproduction success or benchmark score is claimed.",
    }
    write_json(benchmark_dir / "benchmark_result.json", result)
    _write_benchmark_report(benchmark_dir, result)
    if latest is not None and (latest / "manifest.json").exists():
        shutil.copy2(latest / "manifest.json", benchmark_dir / "source_run_manifest.json")
    write_run_manifest(
        benchmark_dir,
        "benchmark",
        required_artifacts=[
            "benchmark_result.json",
            "benchmark_report.md",
            "api_usage/api_usage.jsonl",
            "api_usage/api_usage_summary.json",
        ],
    )
    generate_benchmark_index(_benchmark_root(task_path))
    return result


def _artifact_pass_count(result: dict[str, Any]) -> str:
    checks = result.get("artifact_checks", [])
    return f"{sum(1 for item in checks if item.get('exists'))}/{len(checks)}"


def _metric_pass_count(result: dict[str, Any]) -> str:
    checks = result.get("metric_checks", [])
    return f"{sum(1 for item in checks if item.get('available'))}/{len(checks)}"


def collect_benchmark_results(runs_dir: Path) -> list[dict[str, Any]]:
    """Collect benchmark result files from a runs directory."""
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return []
    results: list[dict[str, Any]] = []
    for result_path in sorted(runs_dir.glob("*/benchmark_result.json"), reverse=True):
        result = read_json(result_path, default=None)
        if isinstance(result, dict):
            result["_result_path"] = str(result_path)
            results.append(result)
    return results


def generate_benchmark_index(runs_dir: Path | None = None) -> dict[str, Any]:
    """Generate benchmark_index.json and benchmark_index.md for benchmark runs."""
    target = Path.cwd() / "benchmarks" / "runs" if runs_dir is None else Path(runs_dir)
    target.mkdir(parents=True, exist_ok=True)
    results = collect_benchmark_results(target)
    entries = []
    for result in results:
        entries.append(
            {
                "task_id": result.get("task_id"),
                "status": result.get("status"),
                "created_at": result.get("created_at"),
                "benchmark_dir": result.get("benchmark_dir"),
                "project_dir": result.get("project_dir"),
                "latest_run_dir": result.get("latest_run_dir"),
                "artifact_pass_count": _artifact_pass_count(result),
                "metric_pass_count": _metric_pass_count(result),
                "manifest_valid": (result.get("manifest_validation") or {}).get("valid"),
                "provenance_complete": bool(result.get("provenance_complete")),
                "diagnosis_count": len(result.get("diagnosis", [])),
            }
        )
    index = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "created_at": iso_now(),
        "runs_dir": str(target),
        "run_count": len(entries),
        "entries": entries,
    }
    write_json(target / "benchmark_index.json", index)
    lines = [
        "# Benchmark Index",
        "",
        "| Task | Status | Created | Artifacts | Metrics | Manifest | Provenance | Diagnosis | Directory |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        lines.append(
            "| {task_id} | {status} | {created_at} | {artifact_pass_count} | {metric_pass_count} | {manifest_valid} | {provenance_complete} | {diagnosis_count} | `{benchmark_dir}` |".format(
                **entry
            )
        )
    safe_write_text(target / "benchmark_index.md", "\n".join(lines) + "\n")
    return index


def _resolve_task_path(suite_path: Path, task: str) -> Path:
    raw = Path(task)
    candidates = [raw] if raw.is_absolute() else [suite_path.parent / raw, Path.cwd() / raw, _repo_root() / raw]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Benchmark task file not found for suite: {task}")


def load_benchmark_suite(suite_path: Path) -> dict[str, Any]:
    """Load and validate a benchmark suite file."""
    suite_path = Path(suite_path)
    suite = read_json(suite_path, default=None)
    if not isinstance(suite, dict):
        raise ValueError(f"Invalid benchmark suite: suite file is not a JSON object: {suite_path}")
    missing = [field for field in ["suite_id", "tasks"] if field not in suite]
    if missing:
        raise ValueError(f"Invalid benchmark suite: missing required fields: {', '.join(missing)}")
    if not isinstance(suite.get("tasks"), list) or not suite["tasks"]:
        raise ValueError("Invalid benchmark suite: tasks must be a non-empty array")
    normalized_tasks = []
    for item in suite["tasks"]:
        if isinstance(item, str):
            normalized_tasks.append({"task": item, "project": None})
        elif isinstance(item, dict) and isinstance(item.get("task"), str):
            normalized_tasks.append({"task": item["task"], "project": item.get("project")})
        else:
            raise ValueError("Invalid benchmark suite: each task must be a path string or object with task")
    suite["tasks"] = normalized_tasks
    suite.setdefault("schema_version", BENCHMARK_SCHEMA_VERSION)
    suite.setdefault("policy", "Workflow-compliance evidence only; no paper reproduction score is claimed.")
    return suite


def _write_suite_report(suite_dir: Path, result: dict[str, Any]) -> Path:
    passed = sum(1 for item in result["task_results"] if item.get("status") == "passed")
    lines = [
        "# Benchmark Suite Report",
        "",
        f"- suite_id: {result['suite_id']}",
        f"- status: {result['status']}",
        f"- tasks_passed: {passed}/{len(result['task_results'])}",
        "",
        "## Tasks",
        "",
        "| Task | Status | Provenance | Benchmark Dir | Project Dir |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in result["task_results"]:
        lines.append(
            f"| {item.get('task_id')} | {item.get('status')} | {item.get('provenance_complete')} | `{item.get('benchmark_dir')}` | `{item.get('project_dir')}` |"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "This suite reports workflow-compliance evidence only. It does not claim paper reproduction success or benchmark scores.",
        ]
    )
    path = suite_dir / "benchmark_suite_report.md"
    safe_write_text(path, "\n".join(lines) + "\n")
    return path


def run_benchmark_suite(suite_path: Path, project_prefix: str | None = None) -> dict[str, Any]:
    """Run a collection of benchmark tasks and write suite-level evidence."""
    suite_path = Path(suite_path)
    suite = load_benchmark_suite(suite_path)
    suite_id = str(suite["suite_id"])
    suite_dir = _benchmark_suite_dir(suite_path, suite_id)
    task_results = []
    diagnosis: list[dict[str, str]] = []

    for index, task_entry in enumerate(suite["tasks"], start=1):
        task_path = _resolve_task_path(suite_path, str(task_entry["task"]))
        project = task_entry.get("project")
        if project_prefix:
            task_id = load_benchmark_task(task_path)["task_id"]
            project = f"{project_prefix}_{slugify(str(task_id))}_{index}"
        try:
            result = run_benchmark(task_path, project_name=project)
            task_results.append(
                {
                    "task_id": result.get("task_id"),
                    "status": result.get("status"),
                    "benchmark_dir": result.get("benchmark_dir"),
                    "project_dir": result.get("project_dir"),
                    "provenance_complete": bool(result.get("provenance_complete")),
                    "diagnosis_count": len(result.get("diagnosis", [])),
                }
            )
        except Exception as exc:
            diagnosis.append(diagnose_error(str(exc), source="benchmark_suite"))
            task_results.append(
                {
                    "task_id": str(task_entry.get("task")),
                    "status": "failed_to_run",
                    "benchmark_dir": None,
                    "project_dir": project,
                    "diagnosis_count": 1,
                }
            )

    status = "passed" if task_results and all(item.get("status") == "passed" for item in task_results) else "needs_review"
    result = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "openrepro_version": __version__,
        "suite_id": suite_id,
        "created_at": iso_now(),
        "suite_dir": str(suite_dir),
        "status": status,
        "task_results": task_results,
        "diagnosis": diagnosis,
        "policy": suite["policy"],
    }
    write_json(suite_dir / "benchmark_suite_result.json", result)
    _write_suite_report(suite_dir, result)
    write_run_manifest(suite_dir, "benchmark-suite")
    generate_benchmark_index(_benchmark_root(suite_path))
    return result
