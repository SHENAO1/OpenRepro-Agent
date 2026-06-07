from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.data_profile import data_profile_summary, generate_data_profile
from openrepro.data_registry import register_data
from openrepro.project_manager import init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_data_profile_for_registered_csv(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    data_file = project / "data" / "measurements.csv"
    data_file.write_text("trial,score,label\n1,0.1,hit\n2,bad,miss\n3,,hit\n", encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Profile fixture data")

    profile = generate_data_profile(project, max_rows=10)
    summary = data_profile_summary(project)
    source = profile["sources"][0]
    columns = {column["name"]: column for column in source["columns"]}

    assert profile["schema_version"] == "1.33.0"
    assert profile["status"] == "warning"
    assert profile["source_count"] == 1
    assert source["format"] == "csv"
    assert source["row_count"] == 3
    assert columns["trial"]["dominant_type"] == "int"
    assert columns["score"]["types"]["float"] == 1
    assert columns["score"]["types"]["string"] == 1
    assert columns["score"]["null_count"] == 1
    assert any("score has mixed" in warning for warning in source["warnings"])
    assert (project / "workspace" / "data_profile.json").exists()
    assert (project / "workspace" / "DATA_PROFILE.md").exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.33.0"


def test_refresh_generates_data_profile(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    profile = read_json(project / "workspace" / "data_profile.json")

    assert refresh["status"] == "complete"
    assert any(step["name"] == "data_profile" and step["status"] == "passed" for step in refresh["steps"])
    assert profile["schema_version"] == "1.33.0"
    assert profile["source_count"] >= 1
    assert (project / "workspace" / "DATA_PROFILE.md").exists()


def test_cli_data_profile(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    data_file = project / "data" / "records.jsonl"
    data_file.write_text('{"trial": 1, "score": 0.1}\n{"trial": 2, "score": 0.2}\n', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="CLI profile data")

    result = runner.invoke(app, ["data-profile", "boc_demo", "--max-rows", "5"])

    assert result.exit_code == 0, result.output
    assert "Data profile generated" in result.output
    assert (project / "workspace" / "data_profile.json").exists()
    assert (project / "workspace" / "DATA_PROFILE.md").exists()
