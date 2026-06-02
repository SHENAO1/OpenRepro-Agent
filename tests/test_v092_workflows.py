from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.experiment_inputs import set_experiment_input, validate_experiment_inputs
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.inspector import inspect_project
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_formula_only_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nBOC correlation evidence.",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="input-calibration-test")
    scaffold_experiment(project, experiment_id="calibration_exp", template="boc-like")
    return project


def test_validate_inputs_reports_missing_required_values(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_formula_only_project(tmp_path)

    validation = validate_experiment_inputs(project, "calibration_exp")
    cli_result = runner.invoke(app, ["validate-inputs", "boc_demo", "--experiment-id", "calibration_exp"])
    inspect_summary = inspect_project(project)
    status = get_status(project)

    assert validation["status"] == "needs_attention"
    assert set(validation["missing"]) == {"code_length", "noise_std"}
    assert cli_result.exit_code == 1
    assert "needs_attention" in cli_result.output
    assert inspect_summary["experiment_missing_required_input_count"] == 2
    assert status.experiment_missing_required_input_count == 2


def test_set_input_completes_and_runner_uses_manual_overrides(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_formula_only_project(tmp_path)

    first = set_experiment_input(project, "calibration_exp", name="noise_std", value="0.02", note="manual noise")
    second = set_experiment_input(project, "calibration_exp", name="code_length", value="64", note="manual length")
    cli_result = runner.invoke(
        app,
        ["set-input", "boc_demo", "--experiment-id", "calibration_exp", "--name", "seed", "--value", "11"],
    )
    validation = validate_experiment_inputs(project, "calibration_exp")
    metadata = run_experiment(project, "calibration_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    metrics = read_json(run_dir / "data" / "metrics.json")
    inputs = read_json(project / "experiments" / "calibration_exp" / "experiment_inputs.json")

    assert first["status"] == "needs_attention"
    assert second["status"] == "complete"
    assert cli_result.exit_code == 0, cli_result.output
    assert validation["status"] == "complete"
    assert validation["source_counts"]["manual_override"] == 3
    assert inputs["schema_version"] == "0.9.2"
    assert inputs["input_sources"]["noise_std"]["source"] == "manual_override"
    assert metrics["noise_std"] == 0.02
    assert metrics["code_length"] == 64
    assert metrics["seed"] == 11
