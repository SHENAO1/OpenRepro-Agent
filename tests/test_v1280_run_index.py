from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.demo_runner import run_demo
from openrepro.project_manager import init_project
from openrepro.run_index import compare_indexed_runs, generate_run_index, indexed_run, run_index_summary
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_runs_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    run_demo(project)
    run_demo(project)
    return project


def test_generate_run_index_and_explorer(tmp_path: Path):
    project = _prepare_runs_project(tmp_path)

    index = generate_run_index(project, export_zip=True)
    summary = run_index_summary(project)

    assert index["schema_version"] == "1.28.0"
    assert index["status"] == "ready"
    assert index["run_count"] == 2
    assert index["valid_manifest_count"] == 2
    assert index["commands"]["run-demo"] == 2
    assert all(run["metric_count"] > 0 for run in index["runs"])
    assert (project / "workspace" / "run_index.json").exists()
    assert (project / "workspace" / "RUN_INDEX.md").exists()
    assert (project / "reports" / "run_explorer" / "index.html").exists()
    assert (project / "reports" / "run_explorer_manifest.json").exists()
    assert (project / "reports" / "run_explorer.zip").exists()
    assert summary["schema_version"] == "1.28.0"
    assert summary["run_count"] == 2


def test_indexed_run_lookup_and_compare(tmp_path: Path):
    project = _prepare_runs_project(tmp_path)
    index = generate_run_index(project)
    left = index["runs"][1]["run_id"]
    right = index["runs"][0]["run_id"]

    run = indexed_run(project, left)
    comparison = compare_indexed_runs(project, left_run_id=left, right_run_id=right)

    assert run["run_id"] == left
    assert comparison["schema_version"] == "1.28.0"
    assert comparison["left"]["run_id"] == left
    assert comparison["right"]["run_id"] == right
    assert comparison["metric_deltas"]
    assert (project / "workspace" / "run_index_comparison.json").exists()
    assert (project / "workspace" / "RUN_INDEX_COMPARISON.md").exists()


def test_cli_runs_index_list_show_and_compare(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_runs_project(tmp_path)
    index = generate_run_index(project)
    left = index["runs"][1]["run_id"]
    right = index["runs"][0]["run_id"]

    index_result = runner.invoke(app, ["runs", "index", "boc_demo", "--zip"])
    list_result = runner.invoke(app, ["runs", "list", "boc_demo"])
    show_result = runner.invoke(app, ["runs", "show", "boc_demo", left])
    compare_result = runner.invoke(app, ["runs", "compare", "boc_demo", "--left", left, "--right", right])

    assert index_result.exit_code == 0, index_result.output
    assert "Run index generated" in index_result.output
    assert list_result.exit_code == 0, list_result.output
    listed = read_json(project / "workspace" / "run_index.json")
    assert any(run["run_id"] == left for run in listed["runs"])
    assert show_result.exit_code == 0, show_result.output
    assert "correlation_peak" in show_result.output
    assert compare_result.exit_code == 0, compare_result.output
    assert "Indexed run comparison written" in compare_result.output
    payload = read_json(project / "workspace" / "run_index_comparison.json")
    assert payload["left"]["run_id"] == left
