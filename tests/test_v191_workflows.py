from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.review_board import generate_review_board
from openrepro.review_decisions import record_review_decision

runner = CliRunner()


def _prepare_project_with_review_item(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text("# Decision Notes\n\nFormula: x[n] = c[n] + noise.\n\nnoise_std = 0.05", encoding="utf-8")
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    generate_review_board(project)
    return project


def test_record_review_decision_closes_one_board_item(tmp_path: Path):
    project = _prepare_project_with_review_item(tmp_path)
    board = generate_review_board(project)

    decisions = record_review_decision(
        project,
        item_id="candidate_verification_missing",
        decision="resolved",
        reviewer="decision-test",
        note="Handled by human review.",
    )
    status = get_status(project)

    assert decisions["schema_version"] == "1.9.1"
    assert decisions["decision_count"] == 1
    assert decisions["closed_count"] == 1
    assert decisions["unresolved_item_count"] == board["item_count"] - 1
    assert decisions["latest_decisions"][0]["decision"] == "resolved"
    assert (project / "workspace" / "review_decisions.json").exists()
    assert (project / "workspace" / "REVIEW_DECISIONS.md").exists()
    assert status.review_decisions_exists is True
    assert status.review_decision_count == 1
    assert status.review_decision_closed_count == 1


def test_cli_review_decision_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project_with_review_item(tmp_path)

    result = runner.invoke(
        app,
        [
            "review-decision",
            "boc_demo",
            "--item-id",
            "candidate_verification_missing",
            "--decision",
            "needs_followup",
            "--reviewer",
            "cli-reviewer",
            "--note",
            "Need paper-side verification.",
        ],
    )
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Review decision recorded" in result.output
    assert package["review_decisions"]["status"] == "needs_decision"
    assert package["review_decisions"]["decision_count"] == 1
    assert package["review_decisions"]["unresolved_item_count"] > 0
    assert any(item["name"] == "review_decisions.json" and item["present"] for item in package["workspace_artifacts"])
