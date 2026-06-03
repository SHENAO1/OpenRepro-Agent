from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.claim_trace import generate_claim_trace, validate_claim_trace
from openrepro.cli import app
from openrepro.data_registry import register_data
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_compare import compare_experiments, rerun_experiment
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.inspector import inspect_project
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.scorecard import generate_reproduction_scorecard

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Scorecard Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="scorecard-test")
    data_file = project / "data" / "scorecard_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Scorecard fixture data")
    scaffold_experiment(project, experiment_id="scorecard_exp", template="boc-like")
    run_experiment(project, "scorecard_exp", confirm=True)
    rerun_experiment(project, "scorecard_exp", confirm=True)
    compare_experiments(project, "scorecard_exp")
    generate_claim_trace(project)
    validate_claim_trace(project)
    return project


def test_generate_reproduction_scorecard_summarizes_readiness(tmp_path: Path):
    project = _prepare_project(tmp_path)

    scorecard = generate_reproduction_scorecard(project)
    status = get_status(project)
    summary = inspect_project(project)
    dimension_keys = {item["key"] for item in scorecard["dimensions"]}

    assert scorecard["schema_version"] == "1.7.0"
    assert scorecard["overall_score"] >= 80
    assert "claim_trace_health" in dimension_keys
    assert "quality_gates" in dimension_keys
    assert scorecard["policy"].startswith("Readiness scorecards summarize workflow evidence")
    assert (project / "workspace" / "REPRODUCTION_SCORECARD.md").exists()
    assert status.scorecard_exists is True
    assert status.scorecard_overall_score == scorecard["overall_score"]
    assert summary["scorecard_status"] == scorecard["overall_status"]


def test_cli_scorecard_and_evidence_package_include_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)

    result = runner.invoke(app, ["scorecard", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Reproduction readiness scorecard generated" in result.output
    assert package["scorecard"]["overall_score"] >= 80
    assert package["scorecard"]["overall_status"] in {"ready", "partial"}
    assert any(item["name"] == "reproduction_scorecard.json" and item["present"] for item in package["workspace_artifacts"])
