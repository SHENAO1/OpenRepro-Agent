from pathlib import Path

from typer.testing import CliRunner

from openrepro.agent_sandbox import agent_sandbox_summary, run_agent_sandbox
from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.utils import write_json

runner = CliRunner()


def _sandbox_project(tmp_path: Path) -> Path:
    init_project("agent_demo", base_dir=tmp_path)
    project = tmp_path / "agent_demo"
    write_json(
        project / "workspace" / "agent_exec_plan.json",
        {
            "schema_version": "1.25.0",
            "status": "ready",
            "safe_step_count": 1,
            "blocked_task_count": 0,
            "steps": [
                {
                    "step_id": "E001",
                    "task_id": "T001",
                    "agent_id": "maintainer",
                    "command_name": "report",
                    "command": "openrepro report agent_demo",
                    "reason": "safe derived-artifact command",
                }
            ],
            "blocked_tasks": [],
        },
    )
    return project


def test_agent_sandbox_dry_run_and_approval_gate(tmp_path: Path):
    project = _sandbox_project(tmp_path)

    dry_run = run_agent_sandbox(project, role="maintainer")
    blocked = run_agent_sandbox(project, role="maintainer", confirm=True)

    assert dry_run["schema_version"] == "1.43.0"
    assert dry_run["status"] == "dry_run"
    assert dry_run["steps"][0]["status"] == "dry_run"
    assert blocked["status"] == "blocked"
    assert blocked["steps"][0]["message"] == "Sandbox execution requires --approve."
    assert (project / "workspace" / "agent_sandbox_run.json").exists()
    assert (project / "workspace" / "AGENT_SANDBOX_RUN.md").exists()
    assert (project / "workspace" / "agent_sandbox_trajectory.jsonl").exists()


def test_agent_sandbox_executes_approved_safe_step(tmp_path: Path):
    project = _sandbox_project(tmp_path)

    result = run_agent_sandbox(project, role="maintainer", confirm=True, approved=True)
    summary = agent_sandbox_summary(project)

    assert result["status"] == "complete"
    assert result["passed_step_count"] == 1
    assert (project / "reports" / "report.md").exists()
    assert (project / result["steps"][0]["stdout_path"]).exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.43.0"


def test_cli_agent_sandbox(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _sandbox_project(tmp_path)

    result = runner.invoke(app, ["agent", "run", "agent_demo", "--role", "maintainer", "--confirm", "--approve"])

    assert result.exit_code == 0, result.output
    assert "Agent sandbox completed" in result.output
    assert (project / "workspace" / "agent_sandbox_run.json").exists()
