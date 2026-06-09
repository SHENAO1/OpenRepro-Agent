from pathlib import Path

from typer.testing import CliRunner

from openrepro.agent_task_spec import agent_task_spec_summary, generate_agent_task_spec
from openrepro.cli import app
from openrepro.evidence_package import generate_evidence_package
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json
from openrepro.workflow_registry import build_workflow_state

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_agent_task_spec_blocks_initial_placeholder_tasks(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    spec = generate_agent_task_spec(project, max_tasks=5)
    summary = agent_task_spec_summary(project)
    result_schema = read_json(project / "workspace" / "agent_result_schema.json")

    assert spec["schema_version"] == "1.58.0"
    assert spec["status"] == "blocked"
    assert spec["task_contract_count"] > 0
    assert spec["blocked_task_count"] > 0
    assert all(task["execution_mode"] == "external_supervised" for task in spec["tasks"])
    assert any(task["blocked_reason"] for task in spec["tasks"])
    assert result_schema["required"] == spec["result_contract"]["required_fields"]
    assert (project / "workspace" / "agent_task_spec.json").exists()
    assert (project / "workspace" / "AGENT_TASK_SPEC.md").exists()
    assert summary["status"] == "blocked"


def test_agent_task_spec_complete_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    spec = generate_agent_task_spec(project)
    status = get_status(project)
    state = build_workflow_state(project)
    step = next(item for item in state["steps"] if item["step_id"] == "agent_task_spec")

    assert spec["status"] == "complete"
    assert spec["task_contract_count"] == 0
    assert status.agent_task_spec_exists is True
    assert status.agent_task_spec_status == "complete"
    assert step["status"] == "complete"


def test_cli_agent_task_spec_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["agent-task-spec", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Agent task spec generated" in result.output
    assert package["agent_task_spec"]["schema_version"] == "1.58.0"
    assert any(item["name"] == "agent_task_spec.json" and item["present"] for item in package["workspace_artifacts"])
    assert any(item["name"] == "agent_result_schema.json" and item["present"] for item in package["workspace_artifacts"])
