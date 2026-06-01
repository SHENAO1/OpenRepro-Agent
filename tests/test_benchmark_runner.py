from pathlib import Path

import pytest

from openrepro.benchmark_runner import generate_benchmark_index, load_benchmark_task, run_benchmark
from openrepro.utils import read_json


def _write_legacy_task(tmp_path: Path, source: Path) -> Path:
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

    assert task["schema_version"] == "0.3.1"
    assert task["task_id"] == "sample_boc_like_demo"
    assert task["artifacts"]["required"]
    assert task["metrics"]["required"]
    assert task["workflow"] == {"run_demo": True, "run_sweep": False}
    assert task["pass_criteria"] == {"require_manifest_valid": True}


def test_v030_style_benchmark_task_still_loads(tmp_path: Path):
    source = tmp_path / "notes.md"
    source.write_text("# Notes", encoding="utf-8")
    task = load_benchmark_task(_write_legacy_task(tmp_path, source))

    assert task["schema_version"] == "0.3.0"
    assert task["artifacts"]["required"][0] == "workspace/paper_summary.md"
    assert task["artifacts"]["optional"] == []
    assert task["metrics"]["required"] == ["signal_length", "correlation_peak"]
    assert task["metrics"]["optional"] == []


def test_benchmark_task_schema_rejects_missing_fields(tmp_path: Path):
    task = tmp_path / "bad_task.json"
    task.write_text('{"task_id": "bad"}', encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        load_benchmark_task(task)


def test_benchmark_task_schema_rejects_bad_new_fields(tmp_path: Path):
    task = tmp_path / "bad_task.json"
    task.write_text(
        """{
  "task_id": "bad",
  "paper_title": "Bad task",
  "source_files": ["notes.md"],
  "artifacts": {"required": "workspace/paper_summary.md"}
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="artifacts.required must be an array"):
        load_benchmark_task(task)


def test_run_benchmark_creates_evidence_bundle(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC correlation and signal_length = 2048.", encoding="utf-8")
    task_path = _write_legacy_task(tmp_path, source)

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
    assert (tmp_path / "benchmarks" / "runs" / "benchmark_index.json").exists()
    assert (tmp_path / "benchmarks" / "runs" / "benchmark_index.md").exists()


def test_v031_optional_artifacts_and_metrics_do_not_fail(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC correlation and signal_length = 2048.", encoding="utf-8")
    task = tmp_path / "benchmark_task.json"
    task.write_text(
        f"""{{
  "schema_version": "0.3.1",
  "task_id": "optional_task",
  "paper_title": "Optional task",
  "source_files": ["{source.as_posix()}"],
  "artifacts": {{
    "required": [
      "workspace/paper_summary.md",
      "outputs/<timestamp>_<project>/data/demo_metrics.json",
      "outputs/<timestamp>_<project>/manifest.json"
    ],
    "optional": ["workspace/not_created.md"]
  }},
  "metrics": {{
    "required": ["signal_length", "correlation_peak"],
    "optional": ["side_lobe_level"]
  }},
  "workflow": {{"run_demo": true, "run_sweep": false}},
  "pass_criteria": {{"require_manifest_valid": true}}
}}
""",
        encoding="utf-8",
    )

    result = run_benchmark(task, project_name="bench_project")

    assert result["status"] == "passed"
    assert any(not item["required"] and not item["exists"] for item in result["artifact_checks"])
    assert any(not item["required"] and not item["available"] for item in result["metric_checks"])
    assert not any("workspace/not_created.md" in item["message"] for item in result["diagnosis"])


def test_benchmark_index_can_be_rebuilt(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC correlation and signal_length = 2048.", encoding="utf-8")
    task_path = _write_legacy_task(tmp_path, source)
    run_benchmark(task_path, project_name="bench_project")
    runs_dir = tmp_path / "benchmarks" / "runs"
    (runs_dir / "benchmark_index.json").unlink()
    (runs_dir / "benchmark_index.md").unlink()

    index = generate_benchmark_index(runs_dir)

    assert index["run_count"] == 1
    assert index["entries"][0]["task_id"] == "sample_task"
    assert index["entries"][0]["manifest_valid"] is True
    assert read_json(runs_dir / "benchmark_index.json")["run_count"] == 1
    assert (runs_dir / "benchmark_index.md").exists()
