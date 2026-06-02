from pathlib import Path
from zipfile import ZipFile

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.evidence_fingerprint import evidence_package_status
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_compare import compare_experiments, rerun_experiment
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.handoff_generator import generate_handoff
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.report_generator import generate_report
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Evidence Package Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="evidence-test")
    scaffold_experiment(project, experiment_id="evidence_exp", template="boc-like")
    run_experiment(project, "evidence_exp", confirm=True)
    rerun_experiment(project, "evidence_exp", confirm=True)
    compare_experiments(project, "evidence_exp")
    generate_report(project)
    generate_handoff(project)
    return project


def test_evidence_package_zip_and_freshness(tmp_path: Path):
    project = _prepare_project(tmp_path)

    package = generate_evidence_package(project, export_zip=True)
    status = evidence_package_status(project)
    zip_path = project / "reports" / "evidence_package.zip"

    assert package["schema_version"] == "1.0.1"
    assert package["freshness"]["status"] == "current"
    assert status["status"] == "current"
    assert zip_path.exists()
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "reports/evidence_package.json" in names
    assert "reports/evidence_package.md" in names
    assert "workspace/run_lineage.json" in names
    assert (project / "handoff" / "EVIDENCE_PACKAGE.md").exists()


def test_evidence_package_detects_stale_sources(tmp_path: Path):
    project = _prepare_project(tmp_path)
    generate_evidence_package(project)

    source = project / "sources" / "notes.md"
    source.write_text(source.read_text(encoding="utf-8") + "\nextra evidence note\n", encoding="utf-8")
    status = evidence_package_status(project)

    assert status["status"] == "stale"
    assert status["stale"] is True


def test_cli_evidence_package_zip(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    result = runner.invoke(app, ["evidence-package", "boc_demo", "--zip"])
    package = read_json(tmp_path / "boc_demo" / "reports" / "evidence_package.json")

    assert result.exit_code == 0, result.output
    assert "Zip:" in result.output
    assert package["schema_version"] == "1.0.1"
    assert (tmp_path / "boc_demo" / "reports" / "evidence_package.zip").exists()
