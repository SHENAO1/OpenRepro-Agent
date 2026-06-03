from pathlib import Path

from typer.testing import CliRunner

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
        "# Checkpoint Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="checkpoint-test")
    approve_candidates(project, approve_all=True, reviewer="checkpoint-test")
    data_file = project / "data" / "checkpoint_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Checkpoint fixture data")
    scaffold_experiment(project, experiment_id="checkpoint_exp", template="boc-like")
    run_experiment(project, "checkpoint_exp", confirm=True)
    rerun_experiment(project, "checkpoint_exp", confirm=True)
    compare_experiments(project, "checkpoint_exp")
    generate_run_lineage(project)
    generate_claim_trace(project)
    validate_claim_trace(project)
    generate_reproduction_scorecard(project)
    generate_reproduction_gaps(project)
    return project


def test_generate_workflow_checkpoints_for_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)

    checkpoints = generate_workflow_checkpoints(project)
    status = get_status(project)
    checkpoint_ids = {item["checkpoint_id"] for item in checkpoints["checkpoints"]}

    assert checkpoints["schema_version"] == "1.8.0"
    assert checkpoints["status"] == "complete"
    assert checkpoints["blocked_count"] == 0
    assert checkpoints["next_checkpoint"] is None
    assert "claim_trace" in checkpoint_ids
    assert "gaps" in checkpoint_ids
    assert (project / "workspace" / "WORKFLOW_CHECKPOINTS.md").exists()
    assert status.checkpoint_exists is True
    assert status.checkpoint_status == "complete"


def test_generate_workflow_checkpoints_surfaces_next_command(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    checkpoints = generate_workflow_checkpoints(project)

    assert checkpoints["status"] == "needs_attention"
    assert checkpoints["next_checkpoint"] == "source_ingested"
    assert checkpoints["next_command"].startswith("openrepro ingest")


def test_cli_checkpoints_and_evidence_package_include_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)

    result = runner.invoke(app, ["checkpoints", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Workflow checkpoints generated" in result.output
    assert package["checkpoints"]["status"] == "complete"
    assert package["checkpoints"]["next_checkpoint"] is None
    assert any(item["name"] == "workflow_checkpoints.json" and item["present"] for item in package["workspace_artifacts"])
