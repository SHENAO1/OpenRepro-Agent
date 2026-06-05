from pathlib import Path

from typer.testing import CliRunner

from openrepro.agent_exec_plan import agent_exec_plan_summary, generate_agent_exec_plan
from openrepro.cli import app
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_agent_exec_plan_complete_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    plan = generate_agent_exec_plan(project, dry_run=True)
    summary = agent_exec_plan_summary(project)
    status = get_status(project)

    assert plan["schema_version"] == "1.25.0"
    assert plan["status"] == "complete"
    assert plan["dry_run"] is True
    assert plan["safe_step_count"] == 0
    assert plan["blocked_task_count"] == 0
    assert plan["top_command"] is None
    assert (project / "workspace" / "agent_exec_plan.json").exists()
    assert (project / "workspace" / "AGENT_EXEC_PLAN.md").exists()
    assert summary["status"] == "complete"
    assert status.agent_exec_plan_exists is True
    assert status.agent_exec_plan_status == "complete"


def test_agent_exec_plan_blocks_placeholder_human_tasks(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    plan = generate_agent_exec_plan(project, dry_run=True)

    assert plan["status"] == "blocked"
    assert plan["safe_step_count"] == 0
    assert plan["blocked_task_count"] > 0
    assert any("placeholder" in item["reason"] for item in plan["blocked_tasks"])


def test_cli_agent_exec_plan(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["agent-exec-plan", "boc_demo", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Agent execution dry-run plan generated" in result.output
    assert (project / "workspace" / "agent_exec_plan.json").exists()
    assert (project / "workspace" / "AGENT_EXEC_PLAN.md").exists()
