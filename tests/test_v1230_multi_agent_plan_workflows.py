from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.multi_agent_plan import generate_multi_agent_plan, multi_agent_plan_summary
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_multi_agent_plan_complete_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    plan = generate_multi_agent_plan(project)
    summary = multi_agent_plan_summary(project)
    status = get_status(project)

    assert plan["schema_version"] == "1.23.0"
    assert plan["status"] == "complete"
    assert plan["agent_count"] == 4
    assert plan["task_count"] == 0
    assert plan["top_command"] is None
    assert (project / "workspace" / "multi_agent_plan.json").exists()
    assert (project / "workspace" / "MULTI_AGENT_PLAN.md").exists()
    assert summary["status"] == "complete"
    assert status.multi_agent_plan_exists is True
    assert status.multi_agent_plan_status == "complete"


def test_multi_agent_plan_assigns_current_next_step(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    plan = generate_multi_agent_plan(project)

    assert plan["status"] == "ready"
    assert plan["task_count"] > 0
    assert plan["top_agent"] is not None
    assert plan["top_command"] is not None
    assert any(task["agent_id"] in {"next_agent", "maintainer", "reviewer", "experimenter"} for task in plan["tasks"])
    assert any(task["source"] == "project_status" for task in plan["tasks"])


def test_cli_multi_agent_plan(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["multi-agent-plan", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Multi-agent plan generated" in result.output
    assert (project / "workspace" / "multi_agent_plan.json").exists()
    assert (project / "workspace" / "MULTI_AGENT_PLAN.md").exists()
