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
        "# Preflight Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="preflight-test")
    approve_candidates(project, approve_all=True, reviewer="preflight-test")
    data_file = project / "data" / "preflight_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Preflight fixture data")
    scaffold_experiment(project, experiment_id="preflight_exp", template="boc-like")
    run_experiment(project, "preflight_exp", confirm=True)
    rerun_experiment(project, "preflight_exp", confirm=True)
    compare_experiments(project, "preflight_exp")
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
    return project


def test_generate_protocol_preflight_ready_project(tmp_path: Path):
    project = _prepare_ready_project(tmp_path)

    preflight = generate_protocol_preflight(project)
    status = get_status(project)

    assert preflight["schema_version"] == "1.11.1"
    assert preflight["status"] == "ready"
    assert preflight["blocking_count"] == 0
    assert preflight["check_count"] >= 7
    assert preflight["top_command"] is None
    assert (project / "workspace" / "protocol_preflight.json").exists()
    assert (project / "workspace" / "PROTOCOL_PREFLIGHT.md").exists()
    assert status.protocol_preflight_exists is True
    assert status.protocol_preflight_status == "ready"
    assert status.protocol_preflight_blocking_count == 0


def test_generate_protocol_preflight_blocks_incomplete_project(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text("# Blocked Preflight\n\nFormula: x[n] = c[n] + noise.\n\nnoise_std = 0.05", encoding="utf-8")
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)

    preflight = generate_protocol_preflight(project)

    assert preflight["status"] == "blocked"
    assert preflight["blocking_count"] > 0
    assert preflight["top_command"] is not None
    assert any(check["check_id"] == "plan_clear" and check["status"] == "blocked" for check in preflight["checks"])


def test_cli_protocol_preflight_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_ready_project(tmp_path)

    result = runner.invoke(app, ["protocol-preflight", "boc_demo"])
    package = generate_evidence_package(project)

    assert result.exit_code == 0, result.output
    assert "Protocol preflight generated" in result.output
    assert package["protocol_preflight"]["status"] == "ready"
    assert package["protocol_preflight"]["blocking_count"] == 0
    assert any(item["name"] == "protocol_preflight.json" and item["present"] for item in package["workspace_artifacts"])
