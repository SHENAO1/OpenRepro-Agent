from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json
from openrepro.workflow_preset import generate_workflow_preset, workflow_preset_summary

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_workflow_preset_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)

    preset = generate_workflow_preset(project, preset="delivery")
    summary = workflow_preset_summary(project)

    assert preset["schema_version"] == "1.34.0"
    assert preset["preset"] == "delivery"
    assert preset["status"] == "complete"
    assert preset["selected_step_count"] > 0
    assert preset["top_command"] is None
    assert (project / "workspace" / "workflow_preset.json").exists()
    assert (project / "workspace" / "WORKFLOW_PRESET.md").exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.34.0"


def test_workflow_preset_reports_next_safe_command(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    (project / "workspace" / "evidence_query.json").unlink()
    (project / "workspace" / "EVIDENCE_QUERY.md").unlink()

    preset = generate_workflow_preset(project, preset="delivery")

    assert preset["status"] == "needs_work"
    assert preset["next_step"]["step_id"] == "evidence_query"
    assert "--step evidence_query --confirm" in preset["top_command"]


def test_refresh_generates_workflow_preset(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    preset = read_json(project / "workspace" / "workflow_preset.json")

    assert refresh["status"] == "complete"
    assert any(step["name"] == "workflow_preset" and step["status"] == "passed" for step in refresh["steps"])
    assert preset["schema_version"] == "1.34.0"
    assert preset["preset"] == "delivery"
    assert (project / "workspace" / "WORKFLOW_PRESET.md").exists()


def test_cli_workflow_preset(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)

    result = runner.invoke(app, ["workflow", "preset", "boc_demo", "--preset", "agent"])

    assert result.exit_code == 0, result.output
    assert "Workflow preset generated" in result.output
    assert (project / "workspace" / "workflow_preset.json").exists()
    assert (project / "workspace" / "WORKFLOW_PRESET.md").exists()
