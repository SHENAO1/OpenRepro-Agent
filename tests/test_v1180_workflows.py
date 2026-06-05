from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.collaboration_pack import generate_collaboration_pack
from openrepro.evidence_fingerprint import evidence_package_status
from openrepro.evidence_package import generate_evidence_package
from openrepro.handoff_generator import generate_handoff
from openrepro.project_manager import get_status
from openrepro.refresh import generate_refresh_run
from openrepro.report_generator import generate_report
from openrepro.review_site import generate_review_site
from openrepro.timeline import generate_project_timeline
from openrepro.utils import read_json

from test_v1160_workflows import _prepare_ready_project

runner = CliRunner()


def _prepare_refresh_project(tmp_path: Path) -> Path:
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)
    generate_report(project)
    generate_handoff(project)
    generate_evidence_package(project, export_zip=True)
    generate_review_site(project, export_zip=True)
    generate_collaboration_pack(project, export_zip=True)
    return project


def test_generate_refresh_run_complete_with_zip(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    run = generate_refresh_run(project, export_zip=True)
    status = get_status(project)
    evidence_status = evidence_package_status(project)

    assert run["schema_version"] == "1.23.0"
    assert run["status"] == "complete"
    assert run["failed_step_count"] == 0
    assert run["top_command"] is None
    assert (project / "workspace" / "refresh_run.json").exists()
    assert (project / "workspace" / "REFRESH_RUN.md").exists()
    assert (project / "workspace" / "refresh_run.zip").exists()
    assert (project / "reports" / "delivery_bundle.json").exists()
    assert (project / "reports" / "DELIVERY_BUNDLE.md").exists()
    assert (project / "reports" / "delivery_bundle.zip").exists()
    assert (project / "workspace" / "multi_agent_plan.json").exists()
    assert (project / "workspace" / "MULTI_AGENT_PLAN.md").exists()
    assert status.refresh_run_exists is True
    assert status.refresh_run_status == "complete"
    assert status.delivery_bundle_exists is True
    assert status.delivery_bundle_status == "ready"
    assert status.multi_agent_plan_exists is True
    assert status.multi_agent_plan_status == "complete"
    assert status.collaboration_pack_next_safe_command_count == 0
    assert evidence_status["status"] == "current"


def test_refresh_does_not_add_human_decisions(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    decisions_before = read_json(project / "workspace" / "review_decisions.json", default={}) or {}
    signoffs_before = read_json(project / "workspace" / "claim_signoffs.json", default={}) or {}

    generate_refresh_run(project)

    decisions_after = read_json(project / "workspace" / "review_decisions.json", default={}) or {}
    signoffs_after = read_json(project / "workspace" / "claim_signoffs.json", default={}) or {}
    assert decisions_after["decision_count"] == decisions_before["decision_count"]
    assert decisions_after["closed_count"] == decisions_before["closed_count"]
    assert signoffs_after["signoff_count"] == signoffs_before["signoff_count"]
    assert signoffs_after["accepted_count"] == signoffs_before["accepted_count"]


def test_cli_refresh(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_refresh_project(tmp_path)

    result = runner.invoke(app, ["refresh", "boc_demo", "--zip"])

    assert result.exit_code == 0, result.output
    assert "Refresh run completed" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "refresh_run.zip").exists()
