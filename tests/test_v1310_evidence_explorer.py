from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.evidence_explorer import evidence_explorer_summary, generate_evidence_explorer
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_evidence_explorer_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    explorer = generate_evidence_explorer(project, export_zip=True)
    summary = evidence_explorer_summary(project)

    assert explorer["schema_version"] == "1.31.0"
    assert explorer["status"] == "ready"
    assert explorer["claim_count"] > 0
    assert explorer["run_count"] > 0
    assert explorer["nodes"]
    assert explorer["runs"]
    assert (project / "reports" / "evidence_explorer" / "index.html").exists()
    assert (project / "reports" / "evidence_explorer_manifest.json").exists()
    assert (project / "reports" / "evidence_explorer.zip").exists()
    assert summary["present"] is True
    assert summary["status"] == "ready"


def test_refresh_generates_evidence_explorer(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    generate_refresh_run(project, export_zip=True)

    assert (project / "reports" / "evidence_explorer" / "index.html").exists()
    assert (project / "reports" / "evidence_explorer_manifest.json").exists()
    assert (project / "reports" / "evidence_explorer.zip").exists()


def test_cli_evidence_explorer(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_refresh_project(tmp_path)

    result = runner.invoke(app, ["evidence-explorer", "boc_demo", "--zip"])

    assert result.exit_code == 0, result.output
    assert "Evidence explorer generated" in result.output
    assert (tmp_path / "boc_demo" / "reports" / "evidence_explorer" / "index.html").exists()
