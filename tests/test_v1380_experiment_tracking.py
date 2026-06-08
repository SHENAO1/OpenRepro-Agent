from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.experiment_tracking import (
    compare_tracked_experiments,
    experiment_tracking_summary,
    generate_experiment_tracking,
    list_tracked_experiments,
    tracked_experiment,
)
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_experiment_tracking_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)

    tracking = generate_experiment_tracking(project, export_zip=True)
    summary = experiment_tracking_summary(project)

    assert tracking["schema_version"] == "1.38.0"
    assert tracking["status"] == "ready"
    assert tracking["experiment_count"] >= 1
    assert tracking["run_count"] >= 1
    assert (project / "workspace" / "experiment_tracking.json").exists()
    assert (project / "workspace" / "EXPERIMENT_TRACKING.md").exists()
    assert (project / "reports" / "experiments" / "index.html").exists()
    assert (project / "reports" / "experiment_tracking_manifest.json").exists()
    assert (project / "reports" / "experiment_tracking.zip").exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.38.0"


def test_list_show_and_compare_tracked_experiments(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    tracking = generate_experiment_tracking(project)
    experiment_id = tracking["experiments"][0]["experiment_id"]

    listed = list_tracked_experiments(project)
    shown = tracked_experiment(project, experiment_id)
    comparison = compare_tracked_experiments(project, experiment_id, experiment_id)

    assert listed["experiment_count"] >= 1
    assert shown["experiment_id"] == experiment_id
    assert comparison["schema_version"] == "1.38.0"
    assert comparison["all_metrics_equal"] is True
    assert (project / "workspace" / "experiment_tracking_comparison.json").exists()


def test_refresh_generates_experiment_tracking(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    tracking = read_json(project / "workspace" / "experiment_tracking.json")

    assert refresh["status"] == "complete"
    assert any(step["name"] == "experiment_tracking" and step["status"] == "passed" for step in refresh["steps"])
    assert tracking["schema_version"] == "1.38.0"
    assert tracking["experiment_count"] >= 1


def test_cli_experiment_tracking(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    tracking = read_json(project / "workspace" / "experiment_tracking.json")
    experiment_id = tracking["experiments"][0]["experiment_id"]

    track = runner.invoke(app, ["experiments", "track", "boc_demo"])
    listed = runner.invoke(app, ["experiments", "list", "boc_demo"])
    shown = runner.invoke(app, ["experiments", "show", "boc_demo", experiment_id])
    compared = runner.invoke(app, ["experiments", "compare", "boc_demo", "--left", experiment_id, "--right", experiment_id])

    assert track.exit_code == 0, track.output
    assert "Experiment tracking generated" in track.output
    assert listed.exit_code == 0, listed.output
    assert shown.exit_code == 0, shown.output
    assert compared.exit_code == 0, compared.output
