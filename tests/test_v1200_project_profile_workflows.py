from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.evidence_package import generate_evidence_package
from openrepro.project_manager import get_status
from openrepro.project_profile import generate_project_profile, project_profile_summary
from openrepro.timeline import generate_project_timeline

from test_v1160_workflows import _prepare_ready_project

runner = CliRunner()


def test_generate_project_profile_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)

    profile = generate_project_profile(project)
    summary = project_profile_summary(project)
    status = get_status(project)

    assert profile["schema_version"] == "1.20.0"
    assert profile["status"] == "ready"
    assert profile["top_command"] is None
    assert profile["target_claim_count"] > 0
    assert profile["required_data_count"] > 0
    assert profile["required_experiment_count"] > 0
    assert profile["acceptance_dimension_count"] >= 8
    assert all(item["status"] == "passed" for item in profile["acceptance_dimensions"])
    assert (project / "workspace" / "project_profile.json").exists()
    assert (project / "workspace" / "PROJECT_PROFILE.md").exists()
    assert summary["status"] == "ready"
    assert status.project_profile_exists is True
    assert status.project_profile_status == "ready"


def test_evidence_package_includes_project_profile(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)

    package = generate_evidence_package(project, export_zip=True)
    artifact_names = {item["name"]: item for item in package["workspace_artifacts"]}

    assert package["project_profile"]["schema_version"] == "1.20.0"
    assert package["project_profile"]["status"] == "ready"
    assert artifact_names["project_profile.json"]["present"] is True
    assert package["reports"]["project_profile"]["present"] is True


def test_cli_project_profile(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_ready_project(tmp_path)

    result = runner.invoke(app, ["profile", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Project profile generated" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "project_profile.json").exists()
