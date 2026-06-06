from pathlib import Path

from typer.testing import CliRunner

from openrepro.agent_adapter import agent_adapter_summary, generate_agent_adapter, validate_agent_adapter
from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_agent_adapter_blocks_initial_placeholder_tasks(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    adapter = generate_agent_adapter(project, runner="external-test", max_steps=3)
    validation = validate_agent_adapter(project)
    summary = agent_adapter_summary(project)

    assert adapter["schema_version"] == "1.30.0"
    assert adapter["status"] == "blocked"
    assert adapter["runner"] == "external-test"
    assert adapter["adapter_step_count"] == 0
    assert adapter["blocked_task_count"] > 0
    assert validation["valid"] is True
    assert validation["warning_count"] == 1
    assert (project / "workspace" / "agent_adapter.json").exists()
    assert (project / "workspace" / "AGENT_ADAPTER.md").exists()
    assert (project / "workspace" / "agent_trajectory.jsonl").exists()
    assert summary["present"] is True
    assert summary["validation_valid"] is True


def test_agent_adapter_complete_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    adapter = generate_agent_adapter(project)
    validation = validate_agent_adapter(project)

    assert adapter["status"] == "complete"
    assert adapter["adapter_step_count"] == 0
    assert adapter["blocked_task_count"] == 0
    assert validation["valid"] is True
    assert validation["warning_count"] == 0


def test_cli_agent_adapter_and_validation(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("boc_demo", base_dir=tmp_path)

    adapter_result = runner.invoke(app, ["agent-adapter", "boc_demo", "--runner", "external-test"])
    validation_result = runner.invoke(app, ["validate-agent-adapter", "boc_demo"])

    assert adapter_result.exit_code == 0, adapter_result.output
    assert "Agent adapter generated" in adapter_result.output
    assert validation_result.exit_code == 0, validation_result.output
    assert "Agent adapter is valid" in validation_result.output
