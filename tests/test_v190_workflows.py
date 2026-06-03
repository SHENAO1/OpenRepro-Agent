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
from openrepro.review_board import generate_review_board
from openrepro.scorecard import generate_reproduction_scorecard

runner = CliRunner()


def _prepare_ready_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Review Board Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="review-board-test")
    approve_candidates(project, approve_all=True, reviewer="review-board-test")
    data_file = project / "data" / "review_board_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Review board fixture data")
    scaffold_experiment(project, experiment_id="review_board_exp", template="boc-like")
    run_experiment(project, "review_board_exp", confirm=True)
    rerun_experiment(project, "review_board_exp", confirm=True)
    compare_experiments(project, "review_board_exp")
    generate_run_lineage(project)
    generate_claim_trace(project)
    validate_claim_trace(project)
    generate_reproduction_scorecard(project)
    generate_reproduction_gaps(project)
    generate_workflow_checkpoints(project)
    generate_advance_plan(project, dry_run=True)
    return project


def test_generate_review_board_clear_for_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)

    board = generate_review_board(project)
    status = get_status(project)

    assert board["schema_version"] == "1.9.0"
    assert board["status"] == "clear"
    assert board["item_count"] == 0
    assert board["top_command"] is None
    assert (project / "workspace" / "review_board.json").exists()
    assert (project / "workspace" / "REVIEW_BOARD.md").exists()
    assert status.review_board_exists is True
    assert status.review_board_status == "clear"
    assert status.review_board_item_count == 0


def test_generate_review_board_surfaces_unverified_candidate(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text("# Candidate Notes\n\nFormula: x[n] = c[n] + noise.\n\nnoise_std = 0.05", encoding="utf-8")
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)

    board = generate_review_board(project)

    assert board["status"] == "needs_review"
    assert board["item_count"] > 0
    assert board["top_command"] is not None
    assert any(item["source"] == "candidate_review" for item in board["items"])
    assert any(item["item_id"] == "candidate_verification_missing" for item in board["items"])


def test_cli_review_board_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)

    result = runner.invoke(app, ["review-board", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Review board generated" in result.output
    assert package["review_board"]["status"] == "clear"
    assert package["review_board"]["item_count"] == 0
    assert any(item["name"] == "review_board.json" and item["present"] for item in package["workspace_artifacts"])
