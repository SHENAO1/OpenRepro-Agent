from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.claim_trace import generate_claim_trace
from openrepro.cli import app
from openrepro.data_registry import register_data
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_project(tmp_path: Path, with_data: bool = True) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Claim Trace Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="claim-test")
    if with_data:
        data_file = project / "data" / "trace_dataset.json"
        data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
        register_data(project, data_file, role="dataset", note="Trace fixture data")
    scaffold_experiment(project, experiment_id="trace_exp", template="boc-like")
    return project


def test_generate_claim_trace_links_claims_experiments_data_and_runs(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_experiment(project, "trace_exp", confirm=True)

    trace = generate_claim_trace(project)
    experiment = trace["experiments"][0]
    run = trace["runs"][0]

    assert trace["schema_version"] == "1.6.1"
    assert trace["claim_count"] >= 1
    assert trace["verified_claim_count"] >= 1
    assert experiment["verified_claim_ids"]
    assert experiment["registered_data_ids"]
    assert run["experiment_id"] == "trace_exp"
    assert run["quality_gate_status"] == "passed"
    assert (project / "workspace" / "CLAIM_TRACE.md").exists()


def test_cli_trace_claims_and_status(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)
    run_experiment(project, "trace_exp", confirm=True)

    result = runner.invoke(app, ["trace-claims", "boc_demo"])
    status = get_status(project)

    assert result.exit_code == 0, result.output
    assert "Claim trace generated" in result.output
    assert status.claim_trace_exists is True
    assert status.claim_trace_claim_count >= 1


def test_evidence_package_includes_claim_trace(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_experiment(project, "trace_exp", confirm=True)

    package = generate_evidence_package(project)
    trace = read_json(project / "workspace" / "claim_trace.json")

    assert package["claim_trace"]["claim_count"] == trace["claim_count"]
    assert package["claim_trace"]["experiment_trace_count"] == 1
    assert any(item["name"] == "claim_trace.json" and item["present"] for item in package["workspace_artifacts"])
