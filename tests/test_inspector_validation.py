from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.artifact_manager import validate_all_run_manifests
from openrepro.cli import app
from openrepro.demo_runner import run_demo, run_sweep
from openrepro.document_loader import ingest_source
from openrepro.inspector import inspect_project
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


def test_inspect_summary_reports_project_health(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)
    run_demo(project)

    summary = inspect_project(project)
    saved = read_json(project / "workspace" / "inspect_summary.json")

    assert summary["source_count"] == 1
    assert summary["formula_candidate_count"] >= 1
    assert summary["parameter_candidate_count"] >= 1
    assert summary["run_count"] == 1
    assert summary["latest_manifest_status"] == "valid"
    assert summary["latest_manifest_valid"] is True
    assert summary["diagnosis_healthy"] is True
    assert saved["schema_version"] == "0.5.1"
    assert saved["verified_formula_candidate_count"] == 0
    assert saved["verified_parameter_candidate_count"] == 0
    assert saved["verified_candidates_status"] == "missing"
    assert saved["latest_repair_dry_run_status"] == "missing"


def test_validate_all_passes_when_all_manifests_are_valid(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)
    run_demo(project)
    run_sweep(project, noise_std_values=[0.0], seeds=[1])

    results = validate_all_run_manifests(project)
    cli_result = runner.invoke(app, ["validate", "boc_demo", "--all"])

    assert len(results) == 2
    assert all(result["valid"] for result in results)
    assert cli_result.exit_code == 0, cli_result.output


def test_validate_all_reports_diagnosis_for_tampered_run(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)
    metadata = run_demo(project)
    run_sweep(project, noise_std_values=[0.0], seeds=[1])
    run_dir = Path(metadata["run_dir"])
    (run_dir / "data" / "demo_metrics.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["validate", "boc_demo", "--all"])

    assert result.exit_code == 1
    assert "Diagnosis" in result.output
    assert "manifest_mismatch" in result.output
