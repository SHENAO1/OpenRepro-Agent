from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.experiment_compare import compare_experiments
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.experiment_spec import validate_experiment_spec
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Spec Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="spec-test")
    scaffold_experiment(project, experiment_id="spec_exp", template="boc-like")
    return project


def test_experiment_spec_validation_and_run_snapshot(tmp_path: Path):
    project = _prepare_project(tmp_path)

    validation = validate_experiment_spec(project, "spec_exp")
    metadata = run_experiment(project, "spec_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    manifest = read_json(run_dir / "manifest.json")

    assert validation["valid"] is True
    assert validation["spec_sha256"]
    assert (project / "experiments" / "spec_exp" / "experiment_spec.json").exists()
    assert (run_dir / "configs" / "experiment_spec_snapshot.json").exists()
    assert "configs/experiment_spec_snapshot.json" in manifest["required_artifacts"]
    assert metadata["experiment_spec"]["sha256"] == validation["spec_sha256"]


def test_compare_experiments_reports_spec_hash(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_experiment(project, "spec_exp", confirm=True)
    run_experiment(project, "spec_exp", confirm=True)

    comparison = compare_experiments(project, "spec_exp")

    assert comparison["hash_comparison"]["spec_sha256"]["equal"] is True


def test_cli_validate_experiment_spec(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    result = runner.invoke(app, ["validate-experiment-spec", "boc_demo", "--experiment-id", "spec_exp"])

    assert result.exit_code == 0, result.output
    assert "Experiment spec is valid" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "experiment_spec_validation.json").exists()
