from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.claim_trace import generate_claim_trace, validate_claim_trace
from openrepro.cli import app
from openrepro.data_registry import register_data
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.inspector import inspect_project
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Claim Validation Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="claim-validation-test")
    data_file = project / "data" / "trace_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Trace validation fixture data")
    scaffold_experiment(project, experiment_id="trace_exp", template="boc-like")
    run_experiment(project, "trace_exp", confirm=True)
    return project


def test_validate_claim_trace_passes_for_current_trace(tmp_path: Path):
    project = _prepare_project(tmp_path)
    generate_claim_trace(project)

    validation = validate_claim_trace(project)
    status = get_status(project)
    summary = inspect_project(project)

    assert validation["schema_version"] == "1.6.1"
    assert validation["valid"] is True
    assert validation["issue_count"] == 0
    assert (project / "workspace" / "CLAIM_TRACE_VALIDATION.md").exists()
    assert status.claim_trace_validation_status == "passed"
    assert status.claim_trace_validation_issue_count == 0
    assert summary["claim_trace_validation_status"] == "passed"


def test_validate_claim_trace_detects_stale_trace(tmp_path: Path):
    project = _prepare_project(tmp_path)
    generate_claim_trace(project)
    data_file = project / "data" / "trace_dataset.json"
    data_file.write_text('{"samples": [9, 9, 9]}', encoding="utf-8")

    validation = validate_claim_trace(project)
    codes = {item["code"] for item in validation["issues"]}

    assert validation["valid"] is False
    assert "claim_trace_stale" in codes


def test_cli_validate_claims_and_evidence_package_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)

    result = runner.invoke(app, ["trace-claims", "boc_demo", "--validate"])
    second = runner.invoke(app, ["validate-claims", "boc_demo"])
    package = generate_evidence_package(project)
    validation = read_json(project / "workspace" / "claim_trace_validation.json")

    assert result.exit_code == 0, result.output
    assert second.exit_code == 0, second.output
    assert "Claim trace validation passed" in second.output
    assert validation["status"] == "passed"
    assert package["claim_trace"]["validation_status"] == "passed"
    assert package["claim_trace"]["validation_issue_count"] == 0
    assert any(item["name"] == "claim_trace_validation.json" and item["present"] for item in package["workspace_artifacts"])
