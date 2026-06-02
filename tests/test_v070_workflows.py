from pathlib import Path

import pytest
from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.artifact_manager import validate_run_manifest
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project

runner = CliRunner()


def _prepare_project(tmp_path: Path, approve: bool = True) -> Path:
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
    if approve:
        approve_candidates(project, approve_all=True, reviewer="run-test")
    scaffold_experiment(project, experiment_id="verified_exp")
    return project


def test_run_experiment_requires_confirm(tmp_path: Path):
    project = _prepare_project(tmp_path)

    with pytest.raises(ValueError, match="requires --confirm"):
        run_experiment(project, "verified_exp")


def test_run_experiment_requires_verified_inputs(tmp_path: Path):
    project = _prepare_project(tmp_path, approve=False)

    with pytest.raises(ValueError, match="verified_inputs_ready"):
        run_experiment(project, "verified_exp", confirm=True)


def test_run_experiment_generates_execution_manifest(tmp_path: Path):
    project = _prepare_project(tmp_path)

    metadata = run_experiment(project, "verified_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])

    assert metadata["status"] == "completed"
    assert (run_dir / "logs" / "run.log").exists()
    assert (run_dir / "data" / "execution_result.json").exists()
    assert (run_dir / "reports" / "experiment_report.md").exists()
    assert (run_dir / "configs" / "experiment_config_snapshot.json").exists()
    assert (run_dir / "code" / "runner.py").exists()
    assert validate_run_manifest(run_dir)["valid"] is True


def test_run_experiment_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    result = runner.invoke(app, ["run-experiment", "boc_demo", "--experiment-id", "verified_exp", "--confirm"])

    assert result.exit_code == 0, result.output
    assert "Experiment run completed" in result.output
