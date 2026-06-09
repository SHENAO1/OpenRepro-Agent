from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.golden_path import run_golden_path
from openrepro.integrations import integrations_summary, run_integration_execution
from openrepro.utils import read_json

runner = CliRunner()


def test_run_integration_execution_writes_dry_run_plan(tmp_path: Path):
    run_golden_path("random_demo", base_dir=tmp_path, report=False, handoff=False)
    project = tmp_path / "random_demo"

    result = run_integration_execution(project, targets=["mlflow", "hydra"])
    summary = integrations_summary(project)

    assert result["schema_version"] == "1.54.0"
    assert result["status"] == "planned"
    assert result["confirm"] is False
    assert result["target_count"] == 2
    assert {item["target"] for item in result["executions"]} == {"mlflow", "hydra"}
    assert all(item["status"] == "planned" for item in result["executions"])
    assert (project / "integrations" / "run_mlflow_adapter.py").exists()
    assert (project / "integrations" / "run_hydra_adapter.py").exists()
    assert (project / "workspace" / "integration_execution.json").exists()
    assert (project / "workspace" / "INTEGRATION_EXECUTION.md").exists()
    assert summary["execution_present"] is True
    assert summary["execution_status"] == "planned"
    export = read_json(project / "workspace" / "integrations.json")
    assert export["schema_version"] == "1.52.0"


def test_cli_integrations_run_writes_plan_and_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_golden_path("random_demo", base_dir=tmp_path, report=False, handoff=False)

    planned = runner.invoke(app, ["integrations", "run", "random_demo", "--target", "mlflow"])
    summarized = runner.invoke(app, ["integrations", "summary", "random_demo"])

    assert planned.exit_code == 0, planned.output
    assert "Integration execution plan written" in planned.output
    assert summarized.exit_code == 0, summarized.output
    assert "execution_status" in summarized.output
    assert (tmp_path / "random_demo" / "workspace" / "integration_execution.json").exists()
