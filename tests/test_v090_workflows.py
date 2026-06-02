from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.document_loader import ingest_source
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.handoff_generator import generate_handoff
from openrepro.inspector import inspect_project
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.utils import read_json, write_json


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
    approve_candidates(project, approve_all=True, reviewer="input-test")
    return project


def test_scaffold_writes_experiment_inputs_from_verified_candidates(tmp_path: Path):
    project = _prepare_project(tmp_path)

    summary = scaffold_experiment(project, experiment_id="input_exp", template="boc-like")
    exp_dir = Path(summary["experiment_dir"])
    inputs = read_json(exp_dir / "experiment_inputs.json")
    inspect_summary = inspect_project(project)

    assert summary["input_completeness_status"] == "complete"
    assert inputs["schema_version"] == "0.9.0"
    assert inputs["input_completeness"]["status"] == "complete"
    assert inputs["parameter_values"]["noise_std"] == 0.05
    assert inputs["parameter_values"]["code_length"] == 128
    assert inspect_summary["experiment_input_completeness_counts"] == {"complete": 1}


def test_template_runner_reads_experiment_inputs(tmp_path: Path):
    project = _prepare_project(tmp_path)
    summary = scaffold_experiment(project, experiment_id="reader_exp", template="boc-like")
    exp_dir = Path(summary["experiment_dir"])
    inputs_path = exp_dir / "experiment_inputs.json"
    inputs = read_json(inputs_path)
    inputs["parameter_values"]["code_length"] = 16
    inputs["parameter_values"]["noise_std"] = 0.0
    write_json(inputs_path, inputs)

    metadata = run_experiment(project, "reader_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    metrics = read_json(run_dir / "data" / "metrics.json")
    snapshot = read_json(run_dir / "configs" / "experiment_inputs_snapshot.json")
    report = (run_dir / "reports" / "experiment_report.md").read_text(encoding="utf-8")

    assert metrics["code_length"] == 16
    assert metrics["noise_std"] == 0.0
    assert snapshot["parameter_values"]["code_length"] == 16
    assert "experiment_inputs_path" in report
    assert "input_completeness: complete" in report


def test_handoff_surfaces_experiment_inputs(tmp_path: Path):
    project = _prepare_project(tmp_path)
    scaffold_experiment(project, experiment_id="handoff_exp", template="boc-like")

    generate_handoff(project)
    handoff = (project / "handoff" / "AGENT_HANDOFF.md").read_text(encoding="utf-8")
    code_status = (project / "handoff" / "CODE_STATUS.md").read_text(encoding="utf-8")

    assert "Experiment Inputs" in handoff
    assert "input_completeness" in handoff
    assert "parameter_values" in code_status
