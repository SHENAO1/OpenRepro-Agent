from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json
from openrepro.workflow_executor import execute_workflow, workflow_execution_summary

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_workflow_executor_dry_run_blocks_unsafe_step(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    result = execute_workflow(project, preset="full", max_steps=2)

    assert result["schema_version"] == "1.40.0"
    assert result["status"] == "blocked"
    assert result["selected_step_count"] == 2
    assert result["steps"][0]["status"] == "skipped"
    assert result["steps"][1]["step_id"] == "ingest"
    assert result["steps"][1]["status"] == "blocked"
    assert (project / "workspace" / "workflow_execution.json").exists()
    assert (project / "workspace" / "WORKFLOW_EXECUTION.md").exists()
    assert (project / "workspace" / "workflow_events.jsonl").exists()


def test_workflow_executor_executes_safe_step_with_logs(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    (project / "workspace" / "evidence_query.json").unlink()
    (project / "workspace" / "EVIDENCE_QUERY.md").unlink()

    result = execute_workflow(project, step_id="evidence_query", confirm=True, retry_count=1)
    summary = workflow_execution_summary(project)
    execution = read_json(project / "workspace" / "workflow_execution.json")

    assert result["status"] == "complete"
    assert result["passed_step_count"] == 1
    assert result["steps"][0]["attempt_count"] == 1
    assert result["steps"][0]["changed_outputs"]
    assert (project / "workspace" / "evidence_query.json").exists()
    assert (project / result["steps"][0]["stdout_path"]).exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.40.0"
    assert execution["execution_id"] == result["execution_id"]


def test_cli_workflow_execute(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    (project / "workspace" / "evidence_query.json").unlink()
    (project / "workspace" / "EVIDENCE_QUERY.md").unlink()

    result = runner.invoke(app, ["workflow", "execute", "boc_demo", "--step", "evidence_query", "--confirm"])

    assert result.exit_code == 0, result.output
    assert "Workflow execution completed" in result.output
    assert (project / "workspace" / "workflow_execution.json").exists()
