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
    approve_candidates(project, approve_all=True, reviewer="template-test")
    return project


def test_boc_like_template_writes_declared_artifacts(tmp_path: Path):
    project = _prepare_project(tmp_path)

    summary = scaffold_experiment(project, experiment_id="boc_exp", template="boc-like")
    exp_dir = Path(summary["experiment_dir"])
    expected = read_json(exp_dir / "expected_artifacts.json")

    assert summary["template"] == "boc-like"
    assert (exp_dir / "runner.py").exists()
    assert "data/metrics.json" in expected["required"]
    assert "data/boc_trace.csv" in expected["required"]

    metadata = run_experiment(project, "boc_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    manifest = read_json(run_dir / "manifest.json")

    assert (run_dir / "data" / "metrics.json").exists()
    assert (run_dir / "data" / "boc_trace.csv").exists()
    assert "data/boc_trace.csv" in manifest["required_artifacts"]
    assert validate_run_manifest(run_dir)["valid"] is True


def test_numeric_sweep_template_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)

    scaffold = runner.invoke(
        app,
        ["scaffold-experiment", "boc_demo", "--experiment-id", "sweep_exp", "--template", "numeric-sweep"],
    )
    assert scaffold.exit_code == 0, scaffold.output
    assert "Template: numeric-sweep" in scaffold.output

    result = runner.invoke(app, ["run-experiment", "boc_demo", "--experiment-id", "sweep_exp", "--confirm"])
    assert result.exit_code == 0, result.output

    run_dir = next(path for path in (project / "outputs").iterdir() if path.is_dir())
    manifest = read_json(run_dir / "manifest.json")

    assert (run_dir / "data" / "metrics.json").exists()
    assert (run_dir / "data" / "sweep.csv").exists()
    assert "data/sweep.csv" in manifest["required_artifacts"]
    assert validate_run_manifest(run_dir)["valid"] is True


def test_run_experiment_fails_when_template_artifact_is_missing(tmp_path: Path):
    project = _prepare_project(tmp_path)
    summary = scaffold_experiment(project, experiment_id="missing_artifact_exp", template="boc-like")
    exp_dir = Path(summary["experiment_dir"])
    (exp_dir / "runner.py").write_text('print("runner completed without template artifacts")\n', encoding="utf-8")

    with pytest.raises(ValueError, match="artifact validation failed"):
        run_experiment(project, "missing_artifact_exp", confirm=True)
