"""Built-in lightweight benchmark pack for OpenRepro workflow evidence."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from . import __version__
from .benchmark_runner import BENCHMARK_SCHEMA_VERSION, load_benchmark_task, run_benchmark_suite
from .utils import ensure_dirs, iso_now, safe_write_text, slugify, write_json


OPENREPRO_BENCH_LITE_SCHEMA_VERSION = "1.53.0"
DEFAULT_BENCH_DIR = Path("benchmarks") / "openrepro_bench_lite"

REQUIRED_ARTIFACTS = [
    "workspace/paper_summary.md",
    "workspace/MODEL_LEDGER.md",
    "workspace/EXPERIMENT_PLAN.md",
    "outputs/<timestamp>_<project>/figures/correlation.png",
    "outputs/<timestamp>_<project>/data/demo_metrics.json",
    "outputs/<timestamp>_<project>/manifest.json",
]
OPTIONAL_ARTIFACTS = ["outputs/<timestamp>_<project>/reports/demo_report.md"]
REQUIRED_METRICS = ["signal_length", "correlation_peak", "correlation_peak_index", "run_time_seconds"]
OPTIONAL_METRICS = ["side_lobe_level"]

BENCH_LITE_TASKS = [
    {
        "task_id": "bench_lite_boc_notes",
        "paper_title": "BOC-like workflow notes",
        "example": "boc_notes.md",
        "difficulty": "starter",
        "focus": "source ingestion, rule analysis, plan generation, and demo evidence",
        "expected_runtime_notes": "Runs the built-in lightweight BOC-like demo over toy notes.",
    },
    {
        "task_id": "bench_lite_random_search_notes",
        "paper_title": "Random-search toy workflow notes",
        "example": "random_search_notes.md",
        "difficulty": "starter",
        "focus": "candidate extraction from optimization-style notes plus demo evidence",
        "expected_runtime_notes": "Runs the same workflow-compliance harness on optimization-style toy notes.",
    },
    {
        "task_id": "bench_lite_numeric_table_notes",
        "paper_title": "Numeric table toy workflow notes",
        "example": "numeric_table_notes.md",
        "difficulty": "starter",
        "focus": "parameter/table-like evidence extraction plus demo evidence",
        "expected_runtime_notes": "Runs the same workflow-compliance harness on notes with compact numeric settings.",
    },
]


def list_bench_lite_tasks() -> list[dict[str, Any]]:
    """Return built-in OpenRepro-Bench Lite task metadata."""
    return [
        {
            "task_id": str(task["task_id"]),
            "paper_title": str(task["paper_title"]),
            "example": str(task["example"]),
            "difficulty": str(task["difficulty"]),
            "focus": str(task["focus"]),
        }
        for task in BENCH_LITE_TASKS
    ]


def materialize_bench_lite(
    bench_dir: Path | None = None,
    *,
    task_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Write the built-in benchmark suite, tasks, and source notes to disk."""
    target = DEFAULT_BENCH_DIR if bench_dir is None else Path(bench_dir)
    ensure_dirs([target, target / "sources"])
    selected = _selected_tasks(task_ids)

    source_names = sorted({str(task["example"]) for task in selected})
    for source_name in source_names:
        resource = files("openrepro").joinpath("examples", source_name)
        safe_write_text(target / "sources" / source_name, resource.read_text(encoding="utf-8"))

    task_paths: list[Path] = []
    for task in selected:
        task_doc = _task_document(task)
        task_path = target / f"{task['task_id']}.json"
        write_json(task_path, task_doc)
        task_paths.append(task_path)

    suite = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "suite_id": "openrepro_bench_lite",
        "description": "Built-in lightweight workflow-compliance suite for toy paper-reproduction notes.",
        "tasks": [{"task": path.name, "project": None} for path in task_paths],
        "policy": "Workflow-compliance evidence only; no paper reproduction success or benchmark score is claimed.",
        "openrepro_bench_lite": {
            "schema_version": OPENREPRO_BENCH_LITE_SCHEMA_VERSION,
            "task_count": len(task_paths),
            "source": "package:openrepro.examples",
        },
    }
    suite_path = target / "suite.json"
    write_json(suite_path, suite)
    safe_write_text(target / "OPENREPRO_BENCH_LITE.md", _render_materialized_markdown(target, selected, suite_path))

    return {
        "schema_version": OPENREPRO_BENCH_LITE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "status": "materialized",
        "bench_dir": str(target),
        "suite_path": str(suite_path),
        "task_count": len(task_paths),
        "tasks": [str(path) for path in task_paths],
        "source_count": len(source_names),
        "policy": suite["policy"],
    }


def run_openrepro_bench_lite(
    *,
    project_prefix: str = "openrepro_bench_lite",
    bench_dir: Path | None = None,
    task_ids: list[str] | None = None,
    materialize_only: bool = False,
) -> dict[str, Any]:
    """Materialize and optionally run the built-in benchmark suite."""
    materialized = materialize_bench_lite(bench_dir, task_ids=task_ids)
    target = Path(materialized["bench_dir"])
    summary_path = target / "openrepro_bench_lite_summary.json"
    markdown_path = target / "OPENREPRO_BENCH_LITE_SUMMARY.md"
    if materialize_only:
        summary = {
            **materialized,
            "openrepro_version": __version__,
            "project_prefix": project_prefix,
            "suite_result": None,
            "summary_path": str(summary_path),
            "markdown_path": str(markdown_path),
        }
        write_json(summary_path, summary)
        safe_write_text(markdown_path, _render_summary_markdown(summary))
        return summary

    suite_result = run_benchmark_suite(Path(materialized["suite_path"]), project_prefix=project_prefix)
    task_results = list(suite_result.get("task_results", []))
    tasks_passed = sum(1 for item in task_results if item.get("status") == "passed")
    summary = {
        "schema_version": OPENREPRO_BENCH_LITE_SCHEMA_VERSION,
        "openrepro_version": __version__,
        "created_at": iso_now(),
        "status": suite_result.get("status"),
        "project_prefix": project_prefix,
        "bench_dir": materialized["bench_dir"],
        "suite_path": materialized["suite_path"],
        "suite_dir": suite_result.get("suite_dir"),
        "task_count": len(task_results),
        "tasks_passed": tasks_passed,
        "task_results": task_results,
        "suite_result_schema_version": suite_result.get("schema_version"),
        "summary_path": str(summary_path),
        "markdown_path": str(markdown_path),
        "policy": materialized["policy"],
    }
    write_json(summary_path, summary)
    safe_write_text(markdown_path, _render_summary_markdown(summary))
    return summary


def _selected_tasks(task_ids: list[str] | None) -> list[dict[str, Any]]:
    if not task_ids:
        return list(BENCH_LITE_TASKS)
    available = {str(task["task_id"]): task for task in BENCH_LITE_TASKS}
    unknown = [task_id for task_id in task_ids if task_id not in available]
    if unknown:
        known = ", ".join(sorted(available))
        raise ValueError(f"Unknown OpenRepro-Bench Lite task id: {', '.join(unknown)}. Known tasks: {known}")
    return [available[task_id] for task_id in task_ids]


def _task_document(task: dict[str, Any]) -> dict[str, Any]:
    example = str(task["example"])
    task_id = str(task["task_id"])
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "task_id": task_id,
        "paper_title": task["paper_title"],
        "source_files": [f"sources/{example}"],
        "artifacts": {
            "required": REQUIRED_ARTIFACTS,
            "optional": OPTIONAL_ARTIFACTS,
        },
        "metrics": {
            "required": REQUIRED_METRICS,
            "optional": OPTIONAL_METRICS,
        },
        "workflow": {"run_demo": True, "run_sweep": False},
        "pass_criteria": {"require_manifest_valid": True},
        "dataset": {
            "name": example,
            "type": "markdown_notes",
            "path": f"sources/{example}",
        },
        "environment": {
            "python": ">=3.10",
            "runner": "OpenRepro-Agent CLI",
        },
        "dependencies": ["numpy", "matplotlib", "pdfplumber", "pyyaml", "typer"],
        "paper_source": {
            "title": task["paper_title"],
            "source_type": "toy_example_notes",
            "claim_policy": "workflow evidence only",
        },
        "expected_runtime_notes": task["expected_runtime_notes"],
        "openrepro_bench_lite": {
            "schema_version": OPENREPRO_BENCH_LITE_SCHEMA_VERSION,
            "difficulty": task["difficulty"],
            "focus": task["focus"],
            "source_example": example,
        },
        "notes": "This task checks workflow evidence only. It is not a benchmark score or a paper reproduction claim.",
    }


def _render_materialized_markdown(target: Path, tasks: list[dict[str, Any]], suite_path: Path) -> str:
    rows = "\n".join(
        f"| {task['task_id']} | {task['paper_title']} | {task['difficulty']} | {task['focus']} |"
        for task in tasks
    )
    return f"""# OpenRepro-Bench Lite

- schema_version: {OPENREPRO_BENCH_LITE_SCHEMA_VERSION}
- suite_path: `{suite_path}`
- bench_dir: `{target}`

| Task | Title | Difficulty | Focus |
| --- | --- | --- | --- |
{rows}

## Run

```bash
openrepro bench-lite
```

## Policy

OpenRepro-Bench Lite reports workflow-compliance evidence only. It does not claim paper reproduction success or scientific benchmark scores.
"""


def _render_summary_markdown(summary: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {task_id} | {status} | {provenance_complete} | `{benchmark_dir}` |".format(
            task_id=item.get("task_id"),
            status=item.get("status"),
            provenance_complete=item.get("provenance_complete"),
            benchmark_dir=item.get("benchmark_dir"),
        )
        for item in summary.get("task_results", [])
    )
    if not rows:
        rows = "| none | materialized_only | n/a | n/a |"
    return f"""# OpenRepro-Bench Lite Summary

- schema_version: {summary['schema_version']}
- openrepro_version: {summary.get('openrepro_version')}
- status: {summary['status']}
- task_count: {summary.get('task_count')}
- tasks_passed: {summary.get('tasks_passed', 0)}
- project_prefix: {summary.get('project_prefix')}
- suite_dir: `{summary.get('suite_dir')}`

| Task | Status | Provenance | Benchmark Dir |
| --- | --- | --- | --- |
{rows}

## Policy

{summary['policy']}
"""


def validate_materialized_bench_lite(bench_dir: Path | None = None) -> dict[str, Any]:
    """Load materialized task files and report basic task validity."""
    target = DEFAULT_BENCH_DIR if bench_dir is None else Path(bench_dir)
    suite_path = target / "suite.json"
    task_files = sorted(path for path in target.glob("bench_lite_*.json") if path.is_file())
    loaded = []
    issues = []
    for task_path in task_files:
        try:
            task = load_benchmark_task(task_path)
            loaded.append({"task_id": task["task_id"], "provenance_complete": task["provenance_complete"]})
        except Exception as exc:
            issues.append({"path": str(task_path), "message": str(exc)})
    return {
        "schema_version": OPENREPRO_BENCH_LITE_SCHEMA_VERSION,
        "bench_dir": str(target),
        "suite_path": str(suite_path),
        "valid": suite_path.exists() and not issues and bool(loaded),
        "task_count": len(loaded),
        "tasks": loaded,
        "issues": issues,
        "slug": slugify("OpenRepro-Bench Lite"),
    }
