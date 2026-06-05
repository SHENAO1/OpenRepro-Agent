from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.multi_agent_plan import generate_multi_agent_plan
from openrepro.multi_agent_plan_validation import (
    multi_agent_plan_validation_summary,
    validate_multi_agent_plan,
)
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json, write_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_validate_multi_agent_plan_complete_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    validation = validate_multi_agent_plan(project)
    summary = multi_agent_plan_validation_summary(project)
    status = get_status(project)

    assert validation["schema_version"] == "1.23.1"
    assert validation["status"] == "passed"
    assert validation["valid"] is True
    assert validation["issue_count"] == 0
    assert validation["top_command"] is None
    assert (project / "workspace" / "multi_agent_plan_validation.json").exists()
    assert (project / "workspace" / "MULTI_AGENT_PLAN_VALIDATION.md").exists()
    assert summary["status"] == "passed"
    assert status.multi_agent_plan_validation_exists is True
    assert status.multi_agent_plan_validation_status == "passed"


def test_validate_multi_agent_plan_detects_stale_counts(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    generate_multi_agent_plan(project)
    plan_path = project / "workspace" / "multi_agent_plan.json"
    plan = read_json(plan_path, default={}) or {}
    plan["task_count"] = 999
    write_json(plan_path, plan)

    validation = validate_multi_agent_plan(project)

    assert validation["status"] == "failed"
    assert validation["valid"] is False
    assert validation["issue_count"] >= 1
    assert validation["top_command"] == f"openrepro multi-agent-plan {project}"
    assert any(item["code"] == "task_count_mismatch" for item in validation["issues"])


def test_validate_multi_agent_plan_flags_forbidden_commands(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    generate_multi_agent_plan(project)
    plan_path = project / "workspace" / "multi_agent_plan.json"
    plan = read_json(plan_path, default={}) or {}
    plan["tasks"] = [
        {
            "task_id": "M001",
            "source": "test",
            "title": "Unsafe execution",
            "agent_id": "experimenter",
            "priority": "P0",
            "status": "open",
            "command": f"openrepro run-experiment {project} --experiment-id exp --confirm",
            "requires_human_input": False,
            "details": {},
        }
    ]
    plan["task_count"] = 1
    plan["open_task_count"] = 1
    plan["top_agent"] = "experimenter"
    plan["top_command"] = plan["tasks"][0]["command"]
    write_json(plan_path, plan)

    validation = validate_multi_agent_plan(project)

    assert validation["status"] == "failed"
    assert any(item["code"] == "forbidden_command" for item in validation["issues"])


def test_cli_validate_multi_agent_plan(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["validate-multi-agent-plan", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Multi-agent plan validation passed" in result.output
    assert (project / "workspace" / "multi_agent_plan_validation.json").exists()
    assert (project / "workspace" / "MULTI_AGENT_PLAN_VALIDATION.md").exists()
