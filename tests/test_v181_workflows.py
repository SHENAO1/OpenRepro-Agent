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
from openrepro.scorecard import generate_reproduction_scorecard

runner = CliRunner()


def _prepare_ready_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Advance Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="advance-test")
    approve_candidates(project, approve_all=True, reviewer="advance-test")
    data_file = project / "data" / "advance_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Advance fixture data")
    scaffold_experiment(project, experiment_id="advance_exp", template="boc-like")
    run_experiment(project, "advance_exp", confirm=True)
    rerun_experiment(project, "advance_exp", confirm=True)
    compare_experiments(project, "advance_exp")
    generate_run_lineage(project)
    generate_claim_trace(project)
    validate_claim_trace(project)
    generate_reproduction_scorecard(project)
    generate_reproduction_gaps(project)
    generate_workflow_checkpoints(project)
    return project


def test_generate_advance_plan_complete_for_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)

    plan = generate_advance_plan(project, dry_run=True)
    status = get_status(project)

    assert plan["schema_version"] == "1.8.1"
    assert plan["status"] == "complete"
    assert plan["action_count"] == 0
    assert plan["top_command"] is None
    assert (project / "workspace" / "ADVANCE_PLAN.md").exists()
    assert status.advance_exists is True
    assert status.advance_status == "complete"


def test_generate_advance_plan_selects_missing_source_command(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    plan = generate_advance_plan(project, dry_run=True)

    assert plan["status"] == "ready"
    assert plan["action_count"] == 1
    assert plan["top_command"].startswith("openrepro ingest")
    assert plan["actions"][0]["will_execute"] is False
    assert plan["actions"][0]["requires_human_input"] is True


def test_cli_advance_requires_dry_run_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)

    missing_flag = runner.invoke(app, ["advance", "boc_demo"])
    result = runner.invoke(app, ["advance", "boc_demo", "--dry-run"])
    package = generate_evidence_package(project)

    assert missing_flag.exit_code == 1
    assert result.exit_code == 0, result.output
    assert "Advance dry-run plan generated" in result.output
    assert package["advance_plan"]["status"] == "complete"
    assert package["advance_plan"]["action_count"] == 0
    assert any(item["name"] == "advance_plan.json" and item["present"] for item in package["workspace_artifacts"])
