from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.openrepro_bench_lite import materialize_bench_lite, run_openrepro_bench_lite, validate_materialized_bench_lite
from openrepro.utils import read_json

runner = CliRunner()


def test_materialize_bench_lite_writes_curated_tasks(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = materialize_bench_lite()
    validation = validate_materialized_bench_lite()

    assert result["schema_version"] == "1.53.0"
    assert result["task_count"] == 3
    assert validation["valid"] is True
    assert validation["task_count"] == 3
    assert all(task["provenance_complete"] for task in validation["tasks"])
    assert (tmp_path / "benchmarks" / "openrepro_bench_lite" / "suite.json").exists()
    assert (tmp_path / "benchmarks" / "openrepro_bench_lite" / "sources" / "numeric_table_notes.md").exists()


def test_run_bench_lite_subset_creates_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = run_openrepro_bench_lite(project_prefix="lite_test", task_ids=["bench_lite_boc_notes"])

    assert result["schema_version"] == "1.53.0"
    assert result["status"] == "passed"
    assert result["task_count"] == 1
    assert result["tasks_passed"] == 1
    assert result["suite_result_schema_version"] == "0.6.0"
    assert "workflow-compliance evidence only" in result["policy"].lower()
    assert Path(result["summary_path"]).exists()
    assert Path(result["markdown_path"]).exists()
    assert Path(result["suite_dir"]).exists()
    saved = read_json(Path(result["summary_path"]))
    assert saved["task_results"][0]["task_id"] == "bench_lite_boc_notes"


def test_cli_bench_lite_lists_and_runs_subset(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    listed = runner.invoke(app, ["bench-lite", "--list-tasks"])
    ran = runner.invoke(
        app,
        ["bench-lite", "--task-id", "bench_lite_boc_notes", "--project-prefix", "lite_cli"],
    )

    assert listed.exit_code == 0, listed.output
    assert "bench_lite_boc_notes" in listed.output
    assert ran.exit_code == 0, ran.output
    assert "OpenRepro-Bench Lite completed" in ran.output
    assert (tmp_path / "benchmarks" / "openrepro_bench_lite" / "openrepro_bench_lite_summary.json").exists()
