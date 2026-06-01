from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.benchmark_runner import load_benchmark_suite, run_benchmark_suite
from openrepro.demo_runner import run_demo, run_sweep
from openrepro.document_loader import ingest_source
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.repair import create_repair_plan
from openrepro.run_compare import compare_runs
from openrepro.utils import read_json


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 128",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    return project


def test_scaffold_experiment_creates_guarded_files(tmp_path: Path):
    project = _prepare_project(tmp_path)

    summary = scaffold_experiment(project, experiment_id="paper_exp")
    exp_dir = Path(summary["experiment_dir"])

    assert summary["status"] == "approval_required"
    assert (exp_dir / "README.md").exists()
    assert (exp_dir / "APPROVAL_REQUIRED.md").exists()
    assert (exp_dir / "runner_stub.py").exists()
    assert read_json(exp_dir / "experiment_config.json")["runnable"] is False
    assert (project / "workspace" / "experiment_scaffold_summary.json").exists()


def test_repair_plan_records_manifest_issue(tmp_path: Path):
    project = _prepare_project(tmp_path)
    metadata = run_demo(project)
    run_dir = Path(metadata["run_dir"])
    (run_dir / "data" / "demo_metrics.json").write_text("{}", encoding="utf-8")

    plan = create_repair_plan(project, run_dir)

    assert plan["issue_count"] >= 1
    assert any(action["code"] == "manifest_mismatch" for action in plan["actions"])
    assert (project / "workspace" / "repair_plan.json").exists()
    assert (project / "workspace" / "REPAIR_PLAN.md").exists()


def test_compare_runs_writes_metric_deltas(tmp_path: Path):
    project = _prepare_project(tmp_path)
    first = Path(run_demo(project)["run_dir"])
    second = Path(run_sweep(project, noise_std_values=[0.0], seeds=[1])["run_dir"])

    comparison = compare_runs(project, left_run=first, right_run=second)

    assert comparison["left"]["run_dir"] == str(first)
    assert comparison["right"]["run_dir"] == str(second)
    assert comparison["metric_deltas"]
    assert (project / "workspace" / "run_comparison.json").exists()
    assert (project / "workspace" / "RUN_COMPARISON.md").exists()


def test_benchmark_suite_creates_suite_evidence(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC correlation and signal_length = 2048.", encoding="utf-8")
    task = tmp_path / "task.json"
    task.write_text(
        f"""{{
  "schema_version": "0.4.0",
  "task_id": "suite_task",
  "paper_title": "Suite task",
  "source_files": ["{source.as_posix()}"],
  "artifacts": {{
    "required": [
      "workspace/paper_summary.md",
      "outputs/<timestamp>_<project>/data/demo_metrics.json",
      "outputs/<timestamp>_<project>/manifest.json"
    ]
  }},
  "metrics": {{"required": ["signal_length", "correlation_peak"]}}
}}
""",
        encoding="utf-8",
    )
    suite = tmp_path / "suite.json"
    suite.write_text(
        f"""{{
  "schema_version": "0.4.0",
  "suite_id": "suite_demo",
  "tasks": [{{"task": "{task.as_posix()}", "project": "suite_project"}}]
}}
""",
        encoding="utf-8",
    )

    loaded = load_benchmark_suite(suite)
    result = run_benchmark_suite(suite)
    suite_dir = Path(result["suite_dir"])

    assert loaded["suite_id"] == "suite_demo"
    assert result["status"] == "passed"
    assert (suite_dir / "benchmark_suite_result.json").exists()
    assert (suite_dir / "benchmark_suite_report.md").exists()
    assert (suite_dir / "manifest.json").exists()
    assert (tmp_path / "benchmarks" / "runs" / "benchmark_index.json").exists()
