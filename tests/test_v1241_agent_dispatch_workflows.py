from pathlib import Path

from typer.testing import CliRunner

from openrepro.agent_dispatch import agent_dispatch_summary, generate_agent_dispatch
from openrepro.cli import app
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_agent_dispatch_complete_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    dispatch = generate_agent_dispatch(project)
    summary = agent_dispatch_summary(project)
    status = get_status(project)

    assert dispatch["schema_version"] == "1.24.1"
    assert dispatch["status"] == "complete"
    assert dispatch["agent_count"] == 4
    assert dispatch["task_count"] == 0
    assert dispatch["validation_status"] == "passed"
    assert dispatch["top_command"] is None
    assert (project / "workspace" / "agent_dispatch.json").exists()
    assert (project / "workspace" / "AGENT_DISPATCH.md").exists()
    assert (project / "workspace" / "agents" / "maintainer" / "TASKS.md").exists()
    assert (project / "workspace" / "agents" / "reviewer" / "TASKS.md").exists()
    assert (project / "workspace" / "agents" / "experimenter" / "TASKS.md").exists()
    assert (project / "workspace" / "agents" / "next_agent" / "TASKS.md").exists()
    assert summary["status"] == "complete"
    assert status.agent_dispatch_exists is True
    assert status.agent_dispatch_status == "complete"


def test_agent_dispatch_groups_current_tasks(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    dispatch = generate_agent_dispatch(project)

    assert dispatch["status"] == "ready"
    assert dispatch["agent_count"] == 4
    assert dispatch["task_count"] > 0
    assert dispatch["open_task_count"] == dispatch["task_count"]
    assert dispatch["validation_status"] == "passed"
    assert any(agent["task_count"] > 0 for agent in dispatch["agents"])
    assert (project / "workspace" / "agent_dispatch.json").exists()
    assert (project / "workspace" / "AGENT_DISPATCH.md").exists()


def test_cli_agent_dispatch(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["agent-dispatch", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Agent dispatch pack generated" in result.output
    assert (project / "workspace" / "agent_dispatch.json").exists()
    assert (project / "workspace" / "AGENT_DISPATCH.md").exists()
    assert (project / "workspace" / "agents" / "maintainer" / "TASKS.md").exists()
