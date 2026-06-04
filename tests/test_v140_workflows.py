from pathlib import Path

from typer.testing import CliRunner

from openrepro.advance import generate_advance_plan
from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.candidate_review import review_candidates
from openrepro.checkpoints import generate_workflow_checkpoints
from openrepro.claim_evidence_binder import generate_claim_evidence_binder, validate_claim_evidence_binder
from openrepro.claim_signoff import record_claim_signoff
from openrepro.claim_signoff_validation import validate_claim_signoffs
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
        "# Claim Signoff Validation Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="signoff-validation")
    approve_candidates(project, approve_all=True, reviewer="signoff-validation")
    data_file = project / "data" / "signoff_validation_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Signoff validation fixture data")
    scaffold_experiment(project, experiment_id="signoff_validation_exp", template="boc-like")
    run_experiment(project, "signoff_validation_exp", confirm=True)
    rerun_experiment(project, "signoff_validation_exp", confirm=True)
    compare_experiments(project, "signoff_validation_exp")
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
    generate_claim_evidence_binder(project)
    validate_claim_evidence_binder(project)
    return project


def _signoff_all_claims(project: Path) -> None:
    binder = generate_claim_evidence_binder(project)
    for claim in binder["claims"]:
        record_claim_signoff(
            project,
            claim_id=claim["claim_id"],
            decision="accepted_workflow_evidence",
            reviewer="signoff-validation",
            note="Workflow evidence reviewed.",
        )


def test_validate_claim_signoffs_passes_for_current_signoffs(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    _signoff_all_claims(project)

    validation = validate_claim_signoffs(project)
    status = get_status(project)

    assert validation["schema_version"] == "1.14.0"
    assert validation["status"] == "passed"
    assert validation["valid"] is True
    assert validation["issue_count"] == 0
    assert validation["top_command"] is None
    assert (project / "workspace" / "claim_signoff_validation.json").exists()
    assert (project / "workspace" / "CLAIM_SIGNOFF_VALIDATION.md").exists()
    assert status.claim_signoff_validation_exists is True
    assert status.claim_signoff_validation_status == "passed"
    assert status.claim_signoff_validation_issue_count == 0


def test_validate_claim_signoffs_detects_stale_snapshot(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)
    _signoff_all_claims(project)
    run_experiment(project, "signoff_validation_exp", confirm=True)

    validation = validate_claim_signoffs(project)

    assert validation["status"] == "failed"
    assert validation["valid"] is False
    assert validation["issue_count"] > 0
    assert validation["top_command"] is not None
    assert any(item["code"] == "signoff_snapshot_stale" for item in validation["issues"])


def test_cli_validate_claim_signoffs_and_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)
    _signoff_all_claims(project)

    result = runner.invoke(app, ["validate-claim-signoffs", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Claim signoff validation passed" in result.output
    assert package["claim_signoff_validation"]["status"] == "passed"
    assert package["claim_signoff_validation"]["issue_count"] == 0
    assert any(item["name"] == "claim_signoff_validation.json" and item["present"] for item in package["workspace_artifacts"])
