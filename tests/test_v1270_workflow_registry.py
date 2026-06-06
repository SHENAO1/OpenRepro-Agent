from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json
from openrepro.workflow_registry import (
    build_workflow_state,
    explain_workflow_step,
    generate_workflow_state,
    run_workflow,
    workflow_state_summary,
)

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_workflow_state_for_initialized_project(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    state = generate_workflow_state(project)
    summary = workflow_state_summary(project)

    assert state["schema_version"] == "1.28.0"
    assert state["status"] == "needs_work"
    assert state["step_count"] > 40
    assert state["complete_step_count"] == 1
    assert state["next_step"]["step_id"] == "ingest"
    assert state["top_command"] == f"openrepro ingest {project} --source <source>"
    assert (project / "workspace" / "workflow_state.json").exists()
    assert (project / "workspace" / "WORKFLOW_STATE.md").exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.28.0"


def test_workflow_state_complete_after_refresh_project(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)

    state = generate_workflow_state(project)

    assert state["status"] == "complete"
    assert state["complete_step_count"] == state["step_count"]
    assert state["blocked_step_count"] == 0
    assert state["top_command"] is None


def test_explain_workflow_step_reports_dependencies(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)

    explanation = explain_workflow_step(project, "paper_lineage")
    step = explanation["step"]

    assert step["step_id"] == "paper_lineage"
    assert step["status"] == "complete"
    assert step["dependencies"] == ["agent_exec_plan"]
    assert step["missing_dependencies"] == []


def test_workflow_run_dry_run_writes_plan(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    result = run_workflow(project, step_id="ingest")

    assert result["schema_version"] == "1.28.0"
    assert result["status"] == "dry_run"
    assert result["selected_step_count"] == 1
    assert result["steps"][0]["step_id"] == "ingest"
    assert result["steps"][0]["status"] == "blocked"
    assert "not safe" in result["steps"][0]["message"]
    assert (project / "workspace" / "workflow_run.json").exists()
    assert (project / "workspace" / "WORKFLOW_RUN.md").exists()


def test_workflow_run_executes_safe_step_with_confirm(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    (project / "workspace" / "paper_lineage.json").unlink()
    (project / "workspace" / "PAPER_LINEAGE.md").unlink()
    before = build_workflow_state(project)
    assert before["next_step"]["step_id"] == "paper_lineage"

    result = run_workflow(project, step_id="paper_lineage", confirm=True)

    assert result["status"] == "complete"
    assert result["passed_step_count"] == 1
    assert (project / "workspace" / "paper_lineage.json").exists()
    refreshed_state = read_json(project / "workspace" / "workflow_state.json")
    assert refreshed_state["status"] == "complete"


def test_cli_workflow_status_explain_and_run(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_refresh_project(tmp_path)

    status = runner.invoke(app, ["workflow", "status", "boc_demo"])
    explain = runner.invoke(app, ["workflow", "explain", "boc_demo", "paper_lineage"])
    run = runner.invoke(app, ["workflow", "run", "boc_demo", "--step", "paper_lineage"])

    assert status.exit_code == 0, status.output
    assert "Workflow state generated" in status.output
    assert explain.exit_code == 0, explain.output
    assert "paper_lineage" in explain.output
    assert run.exit_code == 0, run.output
    assert "Workflow run" in run.output
