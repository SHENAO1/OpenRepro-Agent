from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.collaboration_pack import generate_collaboration_pack
from openrepro.evidence_package import generate_evidence_package
from openrepro.handoff_generator import generate_handoff
from openrepro.project_manager import get_status
from openrepro.report_generator import generate_report
from openrepro.review_site import generate_review_site
from openrepro.timeline import generate_project_timeline

from test_v1160_workflows import _prepare_ready_project

runner = CliRunner()


def _prepare_collaboration_project(tmp_path: Path) -> Path:
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)
    generate_report(project)
    generate_handoff(project)
    generate_evidence_package(project, export_zip=True)
    generate_review_site(project, export_zip=True)
    return project


def test_generate_collaboration_pack_ready_with_zip(tmp_path: Path):
    project = _prepare_collaboration_project(tmp_path)

    pack = generate_collaboration_pack(project, export_zip=True)
    status = get_status(project)

    assert pack["schema_version"] == "1.17.0"
    assert pack["status"] == "ready"
    assert pack["top_command"] is None
    assert pack["role_count"] == 4
    assert pack["role_checklists"]["maintainer"]
    assert pack["role_checklists"]["reviewer"]
    assert pack["role_checklists"]["experimenter"]
    assert pack["role_checklists"]["next_agent"]
    assert (project / "handoff" / "collaboration_pack.json").exists()
    assert (project / "handoff" / "COLLABORATION_PACK.md").exists()
    assert (project / "handoff" / "collaboration_pack.zip").exists()
    assert status.collaboration_pack_exists is True
    assert status.collaboration_pack_status == "ready"
    assert status.evidence_package_status == "current"


def test_generate_collaboration_pack_surfaces_missing_review_site(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    generate_project_timeline(project)
    generate_report(project)
    generate_handoff(project)
    generate_evidence_package(project)

    pack = generate_collaboration_pack(project)

    assert pack["status"] == "needs_review_site"
    assert pack["top_command"].startswith("openrepro review-site")


def test_cli_collaboration_pack(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_collaboration_project(tmp_path)

    result = runner.invoke(app, ["collaboration-pack", "boc_demo", "--zip"])

    assert result.exit_code == 0, result.output
    assert "Collaboration pack generated" in result.output
    assert (tmp_path / "boc_demo" / "handoff" / "collaboration_pack.zip").exists()
