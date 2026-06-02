from pathlib import Path
import time

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.demo_runner import run_demo
from openrepro.diagnostics import diagnose_project
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.quality_gate import evaluate_run_quality
from openrepro.utils import read_json, write_json

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Quality Gate Batch Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="gate-batch-test")
    scaffold_experiment(project, experiment_id="gate_exp", template="boc-like")
    return project


def _tamper_required_metric(run_dir: Path) -> None:
    metrics_path = run_dir / "data" / "metrics.json"
    metrics = read_json(metrics_path)
    metrics.pop("signal_energy")
    write_json(metrics_path, metrics)


def test_quality_gate_all_reports_failed_check_names(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)
    run_dir = Path(run_experiment(project, "gate_exp", confirm=True)["run_dir"])
    _tamper_required_metric(run_dir)

    result = runner.invoke(app, ["quality-gate", "boc_demo", "--all"])
    summary = read_json(project / "workspace" / "quality_gate_summary.json")

    assert result.exit_code == 1, result.output
    assert "required_metrics_present" in result.output
    assert summary["failed_count"] == 1
    assert "required_metrics_present" in summary["failed_gate_check_names"]
    assert (project / "workspace" / "QUALITY_GATE_SUMMARY.md").exists()


def test_diagnose_reports_quality_gate_failure(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_dir = Path(run_experiment(project, "gate_exp", confirm=True)["run_dir"])
    _tamper_required_metric(run_dir)
    evaluate_run_quality(project, run_dir)

    diagnosis = diagnose_project(project, run_dir)

    assert diagnosis["healthy"] is False
    assert any(issue["code"] == "quality_gate_failed" for issue in diagnosis["issues"])


def test_status_distinguishes_latest_run_and_experiment_gate(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_experiment(project, "gate_exp", confirm=True)
    time.sleep(1.1)
    run_demo(project)

    status = get_status(project)

    assert status.latest_quality_gate_status == "missing"
    assert status.latest_experiment_quality_gate_status == "passed"


def test_evidence_package_keeps_failed_quality_gate_names(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_dir = Path(run_experiment(project, "gate_exp", confirm=True)["run_dir"])
    _tamper_required_metric(run_dir)
    evaluate_run_quality(project, run_dir)

    package = generate_evidence_package(project)
    failed_names = {name for gate in package["quality_gates"] for name in gate.get("failed_check_names", [])}

    assert "required_metrics_present" in failed_names
    assert package["runs"][0]["quality_gate_failed_check_names"]
