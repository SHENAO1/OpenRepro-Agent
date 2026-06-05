from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.paper_lineage import generate_paper_lineage, paper_lineage_summary
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_paper_lineage_ready_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    lineage = generate_paper_lineage(project)
    summary = paper_lineage_summary(project)
    status = get_status(project)

    assert lineage["schema_version"] == "1.26.0"
    assert lineage["status"] == "ready"
    assert lineage["claim_count"] > 0
    assert lineage["method_count"] > 0
    assert lineage["experiment_count"] > 0
    assert lineage["metric_count"] > 0
    assert lineage["node_count"] >= lineage["claim_count"]
    assert lineage["edge_count"] > 0
    assert (project / "workspace" / "paper_lineage.json").exists()
    assert (project / "workspace" / "PAPER_LINEAGE.md").exists()
    assert summary["status"] == "ready"
    assert status.paper_lineage_exists is True
    assert status.paper_lineage_status == "ready"


def test_paper_lineage_needs_claim_trace_for_initialized_project(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    lineage = generate_paper_lineage(project)

    assert lineage["status"] == "needs_claim_trace"
    assert lineage["claim_count"] == 0
    assert lineage["top_command"] == f"openrepro trace-claims {project} --validate"


def test_cli_paper_lineage(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["paper-lineage", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Paper lineage generated" in result.output
    assert (project / "workspace" / "paper_lineage.json").exists()
    assert (project / "workspace" / "PAPER_LINEAGE.md").exists()
