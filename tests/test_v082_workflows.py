from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.document_loader import ingest_source
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.experiment_templates import inspect_experiment_scaffolds, list_experiment_templates
from openrepro.inspector import inspect_project
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.utils import read_json, write_json

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


def test_list_templates_exposes_metadata():
    templates = list_experiment_templates()
    names = {item["name"] for item in templates}
    boc_template = next(item for item in templates if item["name"] == "boc-like")
    cli_result = runner.invoke(app, ["list-templates"])

    assert names == {"basic", "boc-like", "numeric-sweep"}
    assert "data/boc_trace.csv" in boc_template["required"]
    assert "code_length" in boc_template["input_hints"]
    assert cli_result.exit_code == 0, cli_result.output
    assert "boc-like" in cli_result.output
    assert "numeric-sweep" in cli_result.output


def test_inspect_and_status_surface_template_scaffolds(tmp_path: Path):
    project = _prepare_project(tmp_path)
    scaffold_experiment(project, experiment_id="boc_exp", template="boc-like")

    summary = inspect_project(project)
    status = get_status(project)
    scaffold_summary = inspect_experiment_scaffolds(project)

    assert summary["schema_version"] == "0.9.2"
    assert summary["experiment_scaffold_count"] == 1
    assert summary["experiment_template_counts"] == {"boc-like": 1}
    assert summary["experiment_expected_artifacts_attention_count"] == 0
    assert status.experiment_scaffold_count == 1
    assert status.experiment_template_counts == {"boc-like": 1}
    assert scaffold_summary["expected_artifacts_valid_count"] == 1


def test_expected_artifact_diagnostics_find_tampered_scaffold(tmp_path: Path):
    project = _prepare_project(tmp_path)
    summary = scaffold_experiment(project, experiment_id="tampered_exp", template="numeric-sweep")
    exp_dir = Path(summary["experiment_dir"])
    expected_path = exp_dir / "expected_artifacts.json"
    expected = read_json(expected_path)
    expected["required"] = [path for path in expected["required"] if path != "data/sweep.csv"]
    write_json(expected_path, expected)

    scaffold_summary = inspect_experiment_scaffolds(project)
    inspect_summary = inspect_project(project)

    assert scaffold_summary["expected_artifacts_attention_count"] == 1
    assert scaffold_summary["issue_counts"]["missing_expected_required_artifacts"] == 1
    assert inspect_summary["experiment_expected_artifacts_attention_count"] == 1
    assert inspect_summary["experiment_scaffold_issue_counts"]["missing_expected_required_artifacts"] == 1
