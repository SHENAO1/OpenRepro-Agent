from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.freshness import generate_artifact_freshness
from openrepro.project_manager import get_status
from openrepro.readiness_review import generate_readiness_review, readiness_review_summary
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_readiness_review_ready_with_zip(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)

    review = generate_readiness_review(project, export_zip=True)
    summary = readiness_review_summary(project)
    status = get_status(project)

    assert review["schema_version"] == "1.21.0"
    assert review["status"] == "ready_for_human_review"
    assert review["top_command"] is None
    assert review["blocker_count"] == 0
    assert review["open_action_count"] == 0
    assert (project / "reports" / "readiness_review.json").exists()
    assert (project / "reports" / "READINESS_REVIEW.md").exists()
    assert (project / "reports" / "readiness_review.zip").exists()
    assert summary["status"] == "ready_for_human_review"
    assert status.readiness_review_exists is True
    assert status.readiness_review_status == "ready_for_human_review"


def test_readiness_review_surfaces_missing_dashboard(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    review = generate_readiness_review(project)

    assert review["status"] == "needs_work"
    assert review["blocker_count"] > 0
    assert review["top_command"] is not None
    assert any(item["check_id"] == "dashboard_ready" and item["status"] == "blocked" for item in review["checks"])


def test_cli_readiness_review(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)

    result = runner.invoke(app, ["readiness-review", "boc_demo", "--zip"])

    assert result.exit_code == 0, result.output
    assert "Readiness review generated" in result.output
    assert (project / "reports" / "readiness_review.zip").exists()
