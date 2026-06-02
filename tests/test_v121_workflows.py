from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.experiment_compare import compare_experiments
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.experiment_spec import inspect_experiment_specs, validate_experiment_spec
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.utils import read_json, write_json

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Spec Freshness Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="freshness-test")
    scaffold_experiment(project, experiment_id="spec_exp", template="boc-like")
    return project


def _make_spec_stale(project: Path) -> None:
    expected_path = project / "experiments" / "spec_exp" / "expected_artifacts.json"
    expected = read_json(expected_path)
    expected["optional"] = list(expected.get("optional", [])) + ["data/extra_optional.json"]
    write_json(expected_path, expected)


def test_spec_freshness_inspection_and_strict_validation(tmp_path: Path):
    project = _prepare_project(tmp_path)
    validation = validate_experiment_spec(project, "spec_exp")

    assert validation["valid"] is True
    assert validation["freshness_status"] == "current"
    assert validation["source_fingerprint"]["package_sha256"] == validation["source_fingerprint"]["current_sha256"]

    _make_spec_stale(project)
    summary = inspect_experiment_specs(project)
    strict = validate_experiment_spec(project, "spec_exp", strict=True)

    assert summary["stale_count"] == 1
    assert summary["specs"][0]["status"] == "stale"
    assert strict["valid"] is False
    assert strict["stale"] is True
    assert strict["freshness_status"] == "stale"

    refreshed = validate_experiment_spec(project, "spec_exp")

    assert refreshed["valid"] is True
    assert refreshed["freshness_status"] == "current"
    assert refreshed["source_fingerprint"]["package_sha256"] == refreshed["source_fingerprint"]["current_sha256"]


def test_cli_strict_validation_fails_on_stale_spec(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)
    validate_experiment_spec(project, "spec_exp")
    _make_spec_stale(project)

    strict = runner.invoke(app, ["validate-experiment-spec", "boc_demo", "--experiment-id", "spec_exp", "--strict"])
    refresh = runner.invoke(app, ["validate-experiment-spec", "boc_demo", "--experiment-id", "spec_exp"])

    assert strict.exit_code == 1, strict.output
    assert "stale" in strict.output
    assert refresh.exit_code == 0, refresh.output
    assert "current" in refresh.output


def test_compare_experiments_warns_when_spec_hash_changes(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_experiment(project, "spec_exp", confirm=True)
    _make_spec_stale(project)
    validate_experiment_spec(project, "spec_exp")
    run_experiment(project, "spec_exp", confirm=True)

    comparison = compare_experiments(project, "spec_exp")

    assert comparison["hash_comparison"]["spec_sha256"]["equal"] is False
    assert comparison["warnings"] == ["Experiment spec hash differs between compared runs."]
