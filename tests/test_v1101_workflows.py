from pathlib import Path

from typer.testing import CliRunner

from openrepro.advance import generate_advance_plan
from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.candidate_review import review_candidates
from openrepro.checkpoints import generate_workflow_checkpoints
from openrepro.claim_trace import generate_claim_trace, validate_claim_trace
from openrepro.cli import app
from openrepro.data_registry import register_data
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_compare import compare_experiments, rerun_experiment
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.gaps import generate_reproduction_gaps
from openrepro.lineage import generate_run_lineage
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.protocol_coverage import generate_protocol_coverage
from openrepro.reproduction_protocol import generate_reproduction_protocol
from openrepro.review_board import generate_review_board
from openrepro.review_decisions import generate_review_decisions
from openrepro.scorecard import generate_reproduction_scorecard

runner = CliRunner()


def _prepare_ready_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Coverage Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="coverage-test")
    approve_candidates(project, approve_all=True, reviewer="coverage-test")
    data_file = project / "data" / "coverage_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Coverage fixture data")
    scaffold_experiment(project, experiment_id="coverage_exp", template="boc-like")
    run_experiment(project, "coverage_exp", confirm=True)
    rerun_experiment(project, "coverage_exp", confirm=True)
    compare_experiments(project, "coverage_exp")
    generate_run_lineage(project)
    generate_claim_trace(project)
    validate_claim_trace(project)
    generate_reproduction_scorecard(project)
    generate_reproduction_gaps(project)
    generate_workflow_checkpoints(project)
    generate_advance_plan(project, dry_run=True)
    generate_review_board(project)
    generate_review_decisions(project)
    generate_reproduction_protocol(project)
    return project


def test_generate_protocol_coverage_complete_for_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)

    coverage = generate_protocol_coverage(project)
    status = get_status(project)

    assert coverage["schema_version"] == "1.10.1"
    assert coverage["status"] == "complete"
    assert coverage["coverage_score"] == 100.0
    assert coverage["uncovered_count"] == 0
    assert all(item["status"] == "complete" for item in coverage["dimensions"])
    assert (project / "workspace" / "protocol_coverage.json").exists()
    assert (project / "workspace" / "PROTOCOL_COVERAGE.md").exists()
    assert status.protocol_coverage_exists is True
    assert status.protocol_coverage_status == "complete"
    assert status.protocol_coverage_uncovered_count == 0


def test_generate_protocol_coverage_surfaces_missing_evidence(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text("# Blocked Coverage\n\nFormula: x[n] = c[n] + noise.\n\nnoise_std = 0.05", encoding="utf-8")
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    generate_reproduction_protocol(project)

    coverage = generate_protocol_coverage(project)

    assert coverage["status"] in {"blocked", "partial"}
    assert coverage["uncovered_count"] > 0
    assert coverage["coverage_score"] < 100.0
    assert coverage["top_command"] is not None
    assert any(item["key"] == "target_claims" and item["status"] == "missing" for item in coverage["dimensions"])


def test_cli_protocol_coverage_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)

    result = runner.invoke(app, ["protocol-coverage", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Protocol coverage generated" in result.output
    assert package["protocol_coverage"]["status"] == "complete"
    assert package["protocol_coverage"]["uncovered_count"] == 0
    assert any(item["name"] == "protocol_coverage.json" and item["present"] for item in package["workspace_artifacts"])
