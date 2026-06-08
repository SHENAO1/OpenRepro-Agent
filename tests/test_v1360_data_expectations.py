from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.data_expectations import data_expectations_summary, init_data_expectations, run_data_expectations
from openrepro.data_registry import register_data
from openrepro.project_manager import init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json, write_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def _project_with_jsonl(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    data_file = project / "data" / "records.jsonl"
    data_file.write_text('{"trial": 1, "score": 0.1}\n{"trial": 2, "score": 0.2}\n', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Expectation fixture data")
    return project


def test_init_and_run_data_expectations(tmp_path: Path):
    project = _project_with_jsonl(tmp_path)

    suite = init_data_expectations(project)
    result = run_data_expectations(project)
    summary = data_expectations_summary(project)

    assert suite["schema_version"] == "1.36.0"
    assert suite["expectation_count"] > 0
    assert result["status"] == "passed"
    assert result["failed_count"] == 0
    assert (project / "workspace" / "data_expectations.json").exists()
    assert (project / "workspace" / "DATA_EXPECTATIONS.md").exists()
    assert (project / "workspace" / "data_expectation_results.json").exists()
    assert (project / "workspace" / "DATA_EXPECTATION_RESULTS.md").exists()
    assert summary["schema_version"] == "1.36.0"


def test_data_expectations_report_failures(tmp_path: Path):
    project = _project_with_jsonl(tmp_path)
    suite = init_data_expectations(project)
    suite["expectations"].append(
        {
            "expectation_id": "dataset_row_count_too_high",
            "data_id": suite["expectations"][0]["data_id"],
            "type": "row_count_min",
            "column": None,
            "params": {"min": 99},
            "enabled": True,
        }
    )
    suite["expectation_count"] = len(suite["expectations"])
    write_json(project / "workspace" / "data_expectations.json", suite)

    result = run_data_expectations(project)

    assert result["status"] == "failed"
    assert result["failed_count"] == 1
    assert result["top_failed_expectation"] == "dataset_row_count_too_high"


def test_refresh_generates_data_expectations(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    results = read_json(project / "workspace" / "data_expectation_results.json")

    assert refresh["status"] == "complete"
    assert any(step["name"] == "data_expectations" and step["status"] == "passed" for step in refresh["steps"])
    assert results["schema_version"] == "1.36.0"
    assert results["status"] == "passed"


def test_cli_data_expectations(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _project_with_jsonl(tmp_path)

    init_result = runner.invoke(app, ["data-expectations", "init", "boc_demo"])
    run_result = runner.invoke(app, ["data-expectations", "run", "boc_demo"])

    assert init_result.exit_code == 0, init_result.output
    assert "Data expectations initialized" in init_result.output
    assert run_result.exit_code == 0, run_result.output
    assert "Data expectations passed" in run_result.output
