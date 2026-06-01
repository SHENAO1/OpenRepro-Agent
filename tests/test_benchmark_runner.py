from pathlib import Path

import pytest

from openrepro.benchmark_runner import load_benchmark_task, run_benchmark


def _write_task(tmp_path: Path, source: Path) -> Path:
    task = tmp_path / "benchmark_task.json"
    task.write_text(
        f"""{{
  "schema_version": "0.3.0",
  "task_id": "sample_task",
  "paper_title": "Sample task",
  "source_files": ["{source.as_posix()}"],
  "expected_artifacts": [
    "workspace/paper_summary.md",
    "workspace/MODEL_LEDGER.md",
    "workspace/EXPERIMENT_PLAN.md",
    "outputs/<timestamp>_<project>/figures/correlation.png",
    "outputs/<timestamp>_<project>/data/demo_metrics.json",
    "outputs/<timestamp>_<project>/manifest.json"
  ],
  "evaluation_metrics": ["signal_length", "correlation_peak"]
}}
""",
        encoding="utf-8",
    )
    return task


def test_benchmark_task_schema_accepts_sample():
    task = load_benchmark_task(Path("benchmarks/sample_task.json"))

    assert task["schema_version"] == "0.3.0"
    assert task["task_id"] == "sample_boc_like_demo"


def test_benchmark_task_schema_rejects_missing_fields(tmp_path: Path):
    task = tmp_path / "bad_task.json"
    task.write_text('{"task_id": "bad"}', encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        load_benchmark_task(task)


def test_run_benchmark_creates_evidence_bundle(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC correlation and signal_length = 2048.", encoding="utf-8")
    task_path = _write_task(tmp_path, source)

    result = run_benchmark(task_path, project_name="bench_project")
    benchmark_dir = Path(result["benchmark_dir"])

    assert result["status"] == "passed"
    assert (benchmark_dir / "benchmark_result.json").exists()
    assert (benchmark_dir / "benchmark_report.md").exists()
    assert (benchmark_dir / "api_usage" / "api_usage.jsonl").exists()
    assert (benchmark_dir / "api_usage" / "api_usage_summary.json").exists()
    assert (benchmark_dir / "manifest.json").exists()
    assert all(item["exists"] for item in result["artifact_checks"])
    assert all(item["available"] for item in result["metric_checks"])
    assert result["policy"].startswith("Workflow-compliance evidence only")
