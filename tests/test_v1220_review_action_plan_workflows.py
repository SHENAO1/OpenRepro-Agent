from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.freshness import generate_artifact_freshness
from openrepro.project_manager import get_status
from openrepro.readiness_review import generate_readiness_review
from openrepro.readiness_review_validation import validate_readiness_review
from openrepro.refresh import generate_refresh_run
from openrepro.review_action_plan import generate_review_action_plan, review_action_plan_summary

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_review_action_plan_complete_for_ready_review(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)
    generate_readiness_review(project, export_zip=True)
    validate_readiness_review(project)

    plan = generate_review_action_plan(project)
    summary = review_action_plan_summary(project)
    status = get_status(project)

    assert plan["schema_version"] == "1.22.0"
    assert plan["status"] == "complete"
    assert plan["action_count"] == 0
    assert plan["top_command"] is None
    assert (project / "workspace" / "review_action_plan.json").exists()
    assert (project / "workspace" / "REVIEW_ACTION_PLAN.md").exists()
    assert summary["status"] == "complete"
    assert status.review_action_plan_exists is True
    assert status.review_action_plan_status == "complete"


def test_review_action_plan_surfaces_blocked_review(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_readiness_review(project)

    plan = generate_review_action_plan(project)

    assert plan["status"] == "ready"
    assert plan["action_count"] > 0
    assert plan["top_command"] is not None
    assert all(action["role"] for action in plan["actions"])
    assert all(action["priority"] for action in plan["actions"])


def test_cli_review_action_plan(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    generate_artifact_freshness(project)
    generate_readiness_review(project, export_zip=True)
    validate_readiness_review(project)

    result = runner.invoke(app, ["review-action-plan", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Review action plan generated" in result.output
    assert (project / "workspace" / "review_action_plan.json").exists()
