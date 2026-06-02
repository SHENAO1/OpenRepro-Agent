from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.candidate_review import list_candidates, review_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 128",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    return project


def test_list_candidates_reports_unverified_candidates(tmp_path: Path):
    project = _prepare_project(tmp_path)

    result = list_candidates(project)

    assert result["schema_version"] == "0.7.1"
    assert result["candidate_count"] >= 2
    assert any(item["review_status"] == "candidate_unverified" for item in result["candidates"])


def test_review_candidates_records_rejected_status(tmp_path: Path):
    project = _prepare_project(tmp_path)

    result = review_candidates(
        project,
        candidate_ids=["F001"],
        status="rejected_by_human",
        reviewer="reviewer",
        note="formula context was insufficient",
    )
    listed = list_candidates(project, status="rejected_by_human")

    assert result["latest_review_count"] == 1
    assert listed["candidate_count"] == 1
    assert listed["candidates"][0]["candidate_id"] == "F001"
    assert (project / "workspace" / "candidate_reviews.json").exists()
    assert (project / "workspace" / "CANDIDATE_REVIEWS.md").exists()


def test_review_verified_updates_verified_candidates(tmp_path: Path):
    project = _prepare_project(tmp_path)

    review_candidates(project, candidate_ids=["F001"], status="verified_by_human", reviewer="reviewer", note="checked")
    verified = read_json(project / "workspace" / "verified_candidates.json")

    assert verified["formula_candidate_ids"] == ["F001"]
    assert verified["formula_candidates"][0]["status"] == "verified_by_human"


def test_candidate_review_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    listed = runner.invoke(app, ["list-candidates", "boc_demo"])
    reviewed = runner.invoke(
        app,
        [
            "review-candidates",
            "boc_demo",
            "--candidate-id",
            "F001",
            "--status",
            "needs_more_evidence",
            "--reviewer",
            "cli-reviewer",
        ],
    )

    assert listed.exit_code == 0, listed.output
    assert "Listed" in listed.output
    assert reviewed.exit_code == 0, reviewed.output
    assert "Recorded 1 candidate reviews" in reviewed.output
