from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.lineage import generate_run_lineage
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.quality_gate import evaluate_run_quality
from openrepro.utils import read_json, write_json

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Quality Gate Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="gate-test")
    scaffold_experiment(project, experiment_id="gate_exp", template="boc-like")
    return project


def test_run_experiment_writes_quality_gate(tmp_path: Path):
    project = _prepare_project(tmp_path)
    metadata = run_experiment(project, "gate_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    gate = read_json(run_dir / "reports" / "quality_gate.json")
    lineage = generate_run_lineage(project)

    assert gate["schema_version"] == "1.4.1"
    assert gate["status"] == "passed"
    assert gate["valid"] is True
    assert metadata["quality_gate"]["status"] == "passed"
    assert lineage["runs"][0]["hashes"]["quality_gate_sha256"]


def test_cli_quality_gate_latest_run(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)
    run_experiment(tmp_path / "boc_demo", "gate_exp", confirm=True)

    result = runner.invoke(app, ["quality-gate", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Run quality gate passed" in result.output
    assert (tmp_path / "boc_demo" / "outputs").exists()


def test_quality_gate_fails_when_required_metric_missing(tmp_path: Path):
    project = _prepare_project(tmp_path)
    metadata = run_experiment(project, "gate_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    metrics_path = run_dir / "data" / "metrics.json"
    metrics = read_json(metrics_path)
    metrics.pop("signal_energy")
    write_json(metrics_path, metrics)

    gate = evaluate_run_quality(project, run_dir)

    assert gate["valid"] is False
    assert gate["status"] == "failed"
    assert any(check["name"] == "required_metrics_present" and not check["passed"] for check in gate["checks"])
