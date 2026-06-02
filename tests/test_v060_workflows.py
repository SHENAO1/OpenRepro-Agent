from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.demo_runner import run_demo
from openrepro.document_loader import ingest_source
from openrepro.lineage import generate_run_lineage
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
    approve_candidates(project, approve_all=True, reviewer="lineage-test")
    run_demo(project)
    return project


def test_generate_run_lineage_records_hashes(tmp_path: Path):
    project = _prepare_project(tmp_path)

    lineage = generate_run_lineage(project)
    saved = read_json(project / "workspace" / "run_lineage.json")
    run = lineage["runs"][0]

    assert lineage["schema_version"] == "1.3.0"
    assert lineage["run_count"] == 1
    assert run["parent_command"] == "run-demo"
    assert run["provenance_complete"] is True
    assert run["experiment_provenance_complete"] is None
    assert run["verified_candidates_present"] is True
    assert run["hashes"]["manifest_sha256"]
    assert run["hashes"]["config_sha256"]
    assert run["hashes"]["source_index_sha256"]
    assert run["hashes"]["verified_candidates_sha256"]
    assert saved["run_count"] == 1
    assert (project / "workspace" / "RUN_LINEAGE.md").exists()


def test_lineage_cli_writes_outputs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    result = runner.invoke(app, ["lineage", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Run lineage written" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "run_lineage.json").exists()
