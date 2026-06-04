from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.dashboard import generate_dashboard
from openrepro.freshness import generate_artifact_freshness
from openrepro.project_manager import get_status
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_dashboard_ready_with_zip(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)

    dashboard = generate_dashboard(project, export_zip=True)
    status = get_status(project)

    assert dashboard["schema_version"] == "1.20.0"
    assert dashboard["status"] == "ready"
    assert dashboard["top_command"] is None
    assert dashboard["readiness"]["score"] == 100.0
    assert dashboard["freshness"]["status"] == "current"
    assert (project / "reports" / "dashboard" / "index.html").exists()
    assert (project / "reports" / "dashboard_manifest.json").exists()
    assert (project / "reports" / "dashboard.zip").exists()
    assert "OpenRepro Dashboard" in (project / "reports" / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert status.dashboard_exists is True
    assert status.dashboard_status == "ready"


def test_generate_dashboard_surfaces_missing_freshness(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    dashboard = generate_dashboard(project)

    assert dashboard["status"] == "needs_refresh"
    assert dashboard["top_command"].startswith("openrepro refresh")


def test_cli_dashboard(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["dashboard", "boc_demo", "--zip"])

    assert result.exit_code == 0, result.output
    assert "Dashboard generated" in result.output
    assert (project / "reports" / "dashboard.zip").exists()
