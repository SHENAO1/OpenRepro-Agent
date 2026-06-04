from pathlib import Path

from typer.testing import CliRunner

from openrepro.acceptance_criteria import acceptance_criteria_summary, generate_acceptance_criteria
from openrepro.cli import app
from openrepro.evidence_package import generate_evidence_package
from openrepro.project_manager import get_status
from openrepro.project_profile import generate_project_profile
from openrepro.timeline import generate_project_timeline

from test_v1160_workflows import _prepare_ready_project

runner = CliRunner()


def test_generate_acceptance_criteria_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)
    generate_project_profile(project)

    criteria = generate_acceptance_criteria(project)
    summary = acceptance_criteria_summary(project)
    status = get_status(project)

    assert criteria["schema_version"] == "1.20.1"
    assert criteria["status"] == "ready"
    assert criteria["top_command"] is None
    assert criteria["criteria_count"] >= 10
    assert criteria["needs_work_count"] == 0
    assert all(item["status"] == "passed" for item in criteria["criteria"])
    assert (project / "workspace" / "acceptance_criteria.json").exists()
    assert (project / "workspace" / "ACCEPTANCE_CRITERIA.md").exists()
    assert summary["status"] == "ready"
    assert status.acceptance_criteria_exists is True
    assert status.acceptance_criteria_status == "ready"


def test_acceptance_criteria_surfaces_missing_work(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)
    generate_project_profile(project)
    (project / "workspace" / "claim_trace_validation.json").unlink()

    criteria = generate_acceptance_criteria(project)

    assert criteria["status"] == "needs_work"
    assert criteria["needs_work_count"] > 0
    assert criteria["top_command"].startswith("openrepro validate-claims")


def test_evidence_package_includes_acceptance_criteria(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)
    generate_project_profile(project)
    generate_acceptance_criteria(project)

    package = generate_evidence_package(project, export_zip=True)
    artifact_names = {item["name"]: item for item in package["workspace_artifacts"]}

    assert package["acceptance_criteria"]["schema_version"] == "1.20.1"
    assert package["acceptance_criteria"]["status"] == "ready"
    assert artifact_names["acceptance_criteria.json"]["present"] is True
    assert package["reports"]["acceptance_criteria"]["present"] is True


def test_cli_acceptance_criteria(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_ready_project(tmp_path)

    result = runner.invoke(app, ["acceptance", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Acceptance criteria generated" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "acceptance_criteria.json").exists()
