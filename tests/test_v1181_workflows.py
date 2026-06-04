from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.freshness import generate_artifact_freshness
from openrepro.project_manager import get_status
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_artifact_freshness_current_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    graph = generate_artifact_freshness(project)
    status = get_status(project)

    assert graph["schema_version"] == "1.20.1"
    assert graph["status"] == "current"
    assert graph["stale_node_count"] == 0
    assert graph["top_stale_reason"] is None
    assert (project / "workspace" / "artifact_freshness.json").exists()
    assert (project / "workspace" / "ARTIFACT_FRESHNESS.md").exists()
    assert status.artifact_freshness_exists is True
    assert status.artifact_freshness_status == "current"


def test_artifact_freshness_reports_stale_evidence_package(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    plan_path = project / "workspace" / "EXPERIMENT_PLAN.md"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\n\nManual note for freshness test.\n", encoding="utf-8")

    graph = generate_artifact_freshness(project)

    assert graph["status"] == "needs_refresh"
    assert graph["top_stale_node"] == "evidence_package"
    assert "fingerprint" in graph["top_stale_reason"]
    assert graph["fingerprint_diff"]["changed_count"] >= 1
    assert graph["top_command"].startswith("openrepro evidence-package")


def test_cli_freshness(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_refresh_project(tmp_path)

    result = runner.invoke(app, ["freshness", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Artifact freshness graph generated" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "artifact_freshness.json").exists()
