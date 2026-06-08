from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.golden_path import run_golden_path
from openrepro.integrations import export_integrations, integrations_summary
from openrepro.utils import read_json, read_yaml

runner = CliRunner()


def test_export_integrations_writes_adapter_artifacts(tmp_path):
    run_golden_path("random_demo", base_dir=tmp_path)
    project = tmp_path / "random_demo"

    result = export_integrations(project)
    summary = integrations_summary(project)

    assert result["schema_version"] == "1.52.0"
    assert result["target_count"] == 4
    assert set(result["targets"]) == {"mlflow", "aim", "dvc", "hydra"}
    assert summary["status"] == "ready"
    assert summary["target_count"] == 4

    mlflow = read_json(project / "integrations" / "mlflow_run_context.json")
    aim = read_json(project / "integrations" / "aim_run_context.json")
    dvc = read_yaml(project / "integrations" / "dvc_stage.yaml")
    hydra = read_yaml(project / "integrations" / "hydra_config.yaml")

    assert mlflow["integration"] == "mlflow"
    assert mlflow["tags"]["openrepro.template"] == "random-search-toy"
    assert aim["integration"] == "aim"
    assert "openrepro_refresh" in dvc["stages"]
    assert hydra["experiment"]["template"] == "random-search-toy"
    assert (project / "workspace" / "INTEGRATIONS.md").exists()


def test_cli_integrations_export_and_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_golden_path("random_demo", base_dir=tmp_path)

    exported = runner.invoke(app, ["integrations", "export", "random_demo", "--target", "mlflow", "--target", "hydra"])
    summarized = runner.invoke(app, ["integrations", "summary", "random_demo"])

    assert exported.exit_code == 0, exported.output
    assert "Integration adapter artifacts exported" in exported.output
    assert summarized.exit_code == 0, summarized.output
    assert "target_count" in summarized.output
    assert (tmp_path / "random_demo" / "integrations" / "mlflow_run_context.json").exists()
    assert (tmp_path / "random_demo" / "integrations" / "hydra_config.yaml").exists()
