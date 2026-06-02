from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_compare import compare_experiments, rerun_experiment
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.handoff_generator import generate_handoff
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.report_generator import generate_report

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


def test_generate_evidence_package(tmp_path: Path):
    project = _prepare_project(tmp_path)

    package = generate_evidence_package(project)
    artifact_names = {item["name"]: item for item in package["workspace_artifacts"]}

    assert package["schema_version"] == "1.0.0"
    assert package["openrepro_version"] == "1.0.0"
    assert package["status"]["lineage_exists"] is True
    assert package["handoff"]["complete"] is True
    assert len(package["runs"]) == 2
    assert len(package["experiments"]) == 1
    assert artifact_names["experiment_comparison.json"]["present"] is True
    assert "does not claim paper reproduction success" in package["policy"]
    assert (project / "reports" / "evidence_package.json").exists()
    assert (project / "reports" / "evidence_package.md").exists()


def test_cli_evidence_package(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    result = runner.invoke(app, ["evidence-package", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Evidence package generated" in result.output
    assert "Schema: 1.0.0" in result.output
    assert (tmp_path / "boc_demo" / "reports" / "evidence_package.json").exists()
