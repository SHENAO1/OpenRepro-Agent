from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.pipeline_spec import export_pipeline_spec, pipeline_spec_summary, plan_pipeline, validate_pipeline_spec
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json, read_yaml, write_yaml

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_export_plan_and_validate_pipeline_spec(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)

    spec = export_pipeline_spec(project, preset="delivery", overwrite=True)
    plan = plan_pipeline(project)
    validation = validate_pipeline_spec(project)
    summary = pipeline_spec_summary(project)

    assert spec["schema_version"] == "1.37.0"
    assert spec["preset"] == "delivery"
    assert spec["steps"]
    assert plan["schema_version"] == "1.37.0"
    assert plan["step_count"] == len(spec["steps"])
    assert validation["valid"] is True
    assert (project / "openrepro.pipeline.yaml").exists()
    assert (project / "workspace" / "pipeline_plan.json").exists()
    assert (project / "workspace" / "PIPELINE_PLAN.md").exists()
    assert (project / "workspace" / "pipeline_validation.json").exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.37.0"


def test_pipeline_validation_rejects_unknown_step(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    spec = export_pipeline_spec(project, preset="data", overwrite=True)
    spec["steps"].append({"step_id": "unknown_step", "safe": True, "dependencies": [], "outputs": []})
    write_yaml(project / "openrepro.pipeline.yaml", spec)

    validation = validate_pipeline_spec(project)

    assert validation["valid"] is False
    assert validation["error_count"] == 1
    assert "unknown_step" in validation["errors"][0]


def test_refresh_generates_pipeline_spec(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    plan = read_json(project / "workspace" / "pipeline_plan.json")
    spec = read_yaml(project / "openrepro.pipeline.yaml")

    assert refresh["status"] == "complete"
    assert any(step["name"] == "pipeline_spec" and step["status"] == "passed" for step in refresh["steps"])
    assert spec["schema_version"] == "1.37.0"
    assert plan["schema_version"] == "1.37.0"


def test_cli_pipeline_commands(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_refresh_project(tmp_path)

    export = runner.invoke(app, ["pipeline", "export", "boc_demo", "--preset", "data", "--overwrite"])
    plan = runner.invoke(app, ["pipeline", "plan", "boc_demo"])
    validate = runner.invoke(app, ["pipeline", "validate", "boc_demo"])

    assert export.exit_code == 0, export.output
    assert "Pipeline spec exported" in export.output
    assert plan.exit_code == 0, plan.output
    assert "Pipeline plan generated" in plan.output
    assert validate.exit_code == 0, validate.output
    assert "Pipeline spec is valid" in validate.output
