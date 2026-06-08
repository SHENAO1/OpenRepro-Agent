from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.experiment_evaluation import (
    define_evaluation_suite,
    evaluation_registry_summary,
    evaluation_results_summary,
    generate_experiment_leaderboard,
    run_evaluation_suite,
)
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def _metric(project: Path) -> tuple[str, float]:
    tracking = read_json(project / "workspace" / "experiment_tracking.json")
    for experiment in tracking["experiments"]:
        for key, value in experiment.get("latest_metrics", {}).items():
            if isinstance(value, (int, float)):
                return key, float(value)
    raise AssertionError("No numeric metric found in experiment tracking.")


def test_define_run_and_leaderboard(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    metric, value = _metric(project)

    registry = define_evaluation_suite(project, metric=metric, threshold=value, operator=">=")
    results = run_evaluation_suite(project)
    leaderboard = generate_experiment_leaderboard(project, metric=metric)
    registry_summary = evaluation_registry_summary(project)
    results_summary = evaluation_results_summary(project)

    assert registry["schema_version"] == "1.42.0"
    assert registry["suite_count"] == 1
    assert results["schema_version"] == "1.42.0"
    assert results["experiment_count"] >= 1
    assert results["missing_metric_count"] == 0
    assert leaderboard["status"] == "ready"
    assert leaderboard["rankable_experiment_count"] >= 1
    assert registry_summary["present"] is True
    assert results_summary["present"] is True
    assert (project / "workspace" / "EVALUATION_RESULTS.md").exists()
    assert (project / "workspace" / "EXPERIMENT_LEADERBOARD.md").exists()


def test_cli_eval_and_leaderboard(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    metric, value = _metric(project)

    defined = runner.invoke(app, ["eval", "define", "boc_demo", "--metric", metric, "--threshold", str(value), "--operator", ">="])
    evaluated = runner.invoke(app, ["eval", "run", "boc_demo"])
    leaderboard = runner.invoke(app, ["experiments", "leaderboard", "boc_demo", "--metric", metric])

    assert defined.exit_code == 0, defined.output
    assert "Evaluation suite defined" in defined.output
    assert evaluated.exit_code == 0, evaluated.output
    assert "Evaluation suite passed" in evaluated.output
    assert leaderboard.exit_code == 0, leaderboard.output
    assert (project / "workspace" / "evaluation_registry.json").exists()
    assert (project / "workspace" / "experiment_leaderboard.json").exists()
