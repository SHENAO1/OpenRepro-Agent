from pathlib import Path

from typer.testing import CliRunner

from openrepro.advance import generate_advance_plan
from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.candidate_review import review_candidates
from openrepro.checkpoints import generate_workflow_checkpoints
from openrepro.claim_evidence_binder import generate_claim_evidence_binder
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
from openrepro.protocol_plan import generate_protocol_plan
from openrepro.protocol_preflight import generate_protocol_preflight
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
        "# Binder Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="binder-test")
    approve_candidates(project, approve_all=True, reviewer="binder-test")
    data_file = project / "data" / "binder_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Binder fixture data")
    scaffold_experiment(project, experiment_id="binder_exp", template="boc-like")
    run_experiment(project, "binder_exp", confirm=True)
    rerun_experiment(project, "binder_exp", confirm=True)
    compare_experiments(project, "binder_exp")
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
    generate_protocol_coverage(project)
    generate_protocol_plan(project)
    generate_protocol_preflight(project)
    return project


def test_generate_claim_evidence_binder_complete_for_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)

    binder = generate_claim_evidence_binder(project)
    status = get_status(project)

    assert binder["schema_version"] == "1.12.0"
    assert binder["status"] == "complete"
    assert binder["claim_count"] > 0
    assert binder["incomplete_claim_count"] == 0
    assert binder["top_command"] is None
    assert all(item["status"] == "complete" for item in binder["claims"])
    assert (project / "workspace" / "claim_evidence_binder.json").exists()
    assert (project / "workspace" / "CLAIM_EVIDENCE_BINDER.md").exists()
    assert status.claim_evidence_binder_exists is True
    assert status.claim_evidence_binder_status == "complete"
    assert status.claim_evidence_binder_incomplete_claim_count == 0


def test_generate_claim_evidence_binder_surfaces_missing_evidence(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text("# Blocked Binder\n\nFormula: x[n] = c[n] + noise.\n\nnoise_std = 0.05", encoding="utf-8")
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)

    binder = generate_claim_evidence_binder(project)

    assert binder["status"] == "needs_evidence"
    assert binder["claim_count"] > 0
    assert binder["incomplete_claim_count"] > 0
    assert binder["top_command"] is not None
    assert any("experiment_link" in item["missing_evidence"] for item in binder["claims"])
    assert any("run_evidence" in item["missing_evidence"] for item in binder["claims"])


def test_cli_evidence_binder_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)

    result = runner.invoke(app, ["evidence-binder", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Claim evidence binder generated" in result.output
    assert package["claim_evidence_binder"]["status"] == "complete"
    assert package["claim_evidence_binder"]["incomplete_claim_count"] == 0
    assert any(item["name"] == "claim_evidence_binder.json" and item["present"] for item in package["workspace_artifacts"])
