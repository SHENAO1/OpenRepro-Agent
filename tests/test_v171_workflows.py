from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.claim_trace import generate_claim_trace, validate_claim_trace
from openrepro.cli import app
from openrepro.candidate_review import review_candidates
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
from openrepro.scorecard import generate_reproduction_scorecard

runner = CliRunner()


def _prepare_ready_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Gaps Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="gaps-test")
    approve_candidates(project, approve_all=True, reviewer="gaps-test")
    data_file = project / "data" / "gaps_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Gaps fixture data")
    scaffold_experiment(project, experiment_id="gaps_exp", template="boc-like")
    run_experiment(project, "gaps_exp", confirm=True)
    rerun_experiment(project, "gaps_exp", confirm=True)
    compare_experiments(project, "gaps_exp")
    generate_run_lineage(project)
    generate_claim_trace(project)
    validate_claim_trace(project)
    generate_reproduction_scorecard(project)
    return project


def test_generate_reproduction_gaps_clear_for_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)

    gaps = generate_reproduction_gaps(project)
    status = get_status(project)

    assert gaps["schema_version"] == "1.7.1"
    assert gaps["status"] == "clear"
    assert gaps["open_count"] == 0
    assert gaps["top_suggested_command"] is None
    assert (project / "workspace" / "REPRODUCTION_GAPS.md").exists()
    assert status.gaps_exists is True
    assert status.gaps_open_count == 0


def test_generate_reproduction_gaps_surfaces_missing_source(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    gaps = generate_reproduction_gaps(project)
    gap_ids = {item["gap_id"] for item in gaps["gaps"]}

    assert gaps["status"] == "open"
    assert gaps["open_count"] > 0
    assert "source_missing" in gap_ids
    assert gaps["top_suggested_command"].startswith("openrepro ingest")


def test_cli_gaps_todo_and_evidence_package_include_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)

    gaps_result = runner.invoke(app, ["gaps", "boc_demo"])
    todo_result = runner.invoke(app, ["todo", "boc_demo"])
    package = generate_evidence_package(project)

    assert gaps_result.exit_code == 0, gaps_result.output
    assert todo_result.exit_code == 0, todo_result.output
    assert "Reproduction gaps generated" in gaps_result.output
    assert "Reproduction to-dos generated" in todo_result.output
    assert package["gaps"]["status"] == "clear"
    assert package["gaps"]["open_count"] == 0
    assert any(item["name"] == "reproduction_gaps.json" and item["present"] for item in package["workspace_artifacts"])
