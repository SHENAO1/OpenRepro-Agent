from pathlib import Path

from typer.testing import CliRunner

from openrepro.agent_board import agent_board_summary, generate_agent_board
from openrepro.cli import app
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_agent_board_complete_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    board = generate_agent_board(project, export_zip=True)
    summary = agent_board_summary(project)
    status = get_status(project)

    assert board["schema_version"] == "1.24.0"
    assert board["status"] == "complete"
    assert board["agent_count"] == 4
    assert board["task_count"] == 0
    assert board["validation_status"] == "passed"
    assert board["top_command"] is None
    assert (project / "reports" / "agent_board" / "index.html").exists()
    assert (project / "reports" / "agent_board_manifest.json").exists()
    assert (project / "reports" / "agent_board.zip").exists()
    assert summary["status"] == "complete"
    assert status.agent_board_exists is True
    assert status.agent_board_status == "complete"


def test_agent_board_groups_current_tasks(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    board = generate_agent_board(project)

    assert board["status"] == "ready"
    assert board["agent_count"] == 4
    assert board["task_count"] > 0
    assert board["open_task_count"] == board["task_count"]
    assert board["validation_status"] == "passed"
    assert any(lane["task_count"] > 0 for lane in board["lanes"])
    assert (project / "workspace" / "multi_agent_plan.json").exists()
    assert (project / "workspace" / "multi_agent_plan_validation.json").exists()


def test_cli_agent_board(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["agent-board", "boc_demo", "--zip"])

    assert result.exit_code == 0, result.output
    assert "Agent board generated" in result.output
    assert (project / "reports" / "agent_board" / "index.html").exists()
    assert (project / "reports" / "agent_board_manifest.json").exists()
    assert (project / "reports" / "agent_board.zip").exists()
