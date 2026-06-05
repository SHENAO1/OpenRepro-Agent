from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.freshness import generate_artifact_freshness
from openrepro.project_manager import get_status
from openrepro.readiness_review import generate_readiness_review
from openrepro.readiness_review_validation import readiness_review_validation_summary, validate_readiness_review
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json, write_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_validate_readiness_review_passes_for_current_review(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)
    generate_readiness_review(project, export_zip=True)

    validation = validate_readiness_review(project)
    summary = readiness_review_validation_summary(project)
    status = get_status(project)

    assert validation["schema_version"] == "1.21.1"
    assert validation["status"] == "passed"
    assert validation["valid"] is True
    assert validation["issue_count"] == 0
    assert (project / "reports" / "readiness_review_validation.json").exists()
    assert (project / "reports" / "READINESS_REVIEW_VALIDATION.md").exists()
    assert summary["status"] == "passed"
    assert status.readiness_review_validation_exists is True
    assert status.readiness_review_validation_status == "passed"


def test_validate_readiness_review_fails_for_tampered_review(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)
    generate_readiness_review(project, export_zip=True)
    review_path = project / "reports" / "readiness_review.json"
    review = read_json(review_path, default={}) or {}
    review["status"] = "needs_work"
    write_json(review_path, review)

    validation = validate_readiness_review(project)

    assert validation["status"] == "failed"
    assert validation["issue_count"] > 0
    assert validation["top_command"].startswith("openrepro readiness-review")


def test_cli_validate_readiness_review(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)
    generate_readiness_review(project, export_zip=True)

    result = runner.invoke(app, ["validate-readiness-review", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Readiness review validation passed" in result.output
    assert (project / "reports" / "readiness_review_validation.json").exists()
