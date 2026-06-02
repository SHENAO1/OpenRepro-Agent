from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.experiment_compare import compare_experiments, rerun_experiment
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.lineage import generate_run_lineage
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC Repeatability Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="repeat-test")
    scaffold_experiment(project, experiment_id="repeat_exp", template="boc-like")
    return project


def test_rerun_and_compare_experiments(tmp_path: Path):
    project = _prepare_project(tmp_path)

    first = run_experiment(project, "repeat_exp", confirm=True)
    second = rerun_experiment(project, "repeat_exp", confirm=True)
    comparison = compare_experiments(project, "repeat_exp")

    assert comparison["schema_version"] == "0.9.3"
    assert comparison["left"]["run_dir"] == first["run_dir"]
    assert comparison["right"]["run_dir"] == second["run_dir"]
    assert comparison["all_metrics_equal"] is True
    assert comparison["hash_comparison"]["runner_sha256"]["equal"] is True
    assert comparison["hash_comparison"]["normalized_inputs_sha256"]["equal"] is True
    assert (project / "workspace" / "experiment_comparison.json").exists()
    assert (project / "workspace" / "EXPERIMENT_COMPARISON.md").exists()


def test_cli_rerun_and_compare_experiments(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    commands = [
        ["run-experiment", "boc_demo", "--experiment-id", "repeat_exp", "--confirm"],
        ["rerun-experiment", "boc_demo", "--experiment-id", "repeat_exp", "--confirm"],
        ["compare-experiments", "boc_demo", "--experiment-id", "repeat_exp"],
    ]
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 0, result.output

    assert "Experiment comparison written" in result.output
    assert "All metrics equal: True" in result.output


def test_lineage_marks_experiment_repeat_groups(tmp_path: Path):
    project = _prepare_project(tmp_path)

    run_experiment(project, "repeat_exp", confirm=True)
    rerun_experiment(project, "repeat_exp", confirm=True)
    lineage = generate_run_lineage(project)
    experiment_runs = [entry for entry in lineage["runs"] if entry["parent_command"] == "run-experiment"]

    assert lineage["schema_version"] == "1.4.0"
    assert [entry["repeat_group_id"] for entry in experiment_runs] == [
        "experiment:repeat_exp",
        "experiment:repeat_exp",
    ]
    assert [entry["repeat_run_index"] for entry in experiment_runs] == [1, 2]
    assert [entry["repeat_run_count"] for entry in experiment_runs] == [2, 2]
