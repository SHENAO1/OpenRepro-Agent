from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.cli import app
from openrepro.data_registry import data_contract, data_index_summary, register_data, validate_data_index
from openrepro.document_loader import ingest_source
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.experiment_spec import validate_experiment_spec
from openrepro.lineage import generate_run_lineage
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.utils import read_json

runner = CliRunner()


def _prepare_project(tmp_path: Path, register: bool = False) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Data Registry Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="data-test")
    if register:
        data_file = project / "data" / "dataset.json"
        data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
        register_data(project, data_file, role="dataset", note="Fixture dataset")
    scaffold_experiment(project, experiment_id="data_exp", template="boc-like")
    return project


def test_register_and_validate_data_index(tmp_path: Path):
    project = _prepare_project(tmp_path)
    data_file = project / "data" / "dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")

    record = register_data(project, data_file, role="dataset", note="Fixture dataset")
    summary = data_index_summary(project)
    validation = validate_data_index(project)
    contract = data_contract(project)

    assert record["data_id"]
    assert record["path"] == "data/dataset.json"
    assert record["path_mode"] == "project_relative"
    assert summary["registered_count"] == 1
    assert summary["status_counts"] == {"current": 1}
    assert validation["valid"] is True
    assert contract["registered_data"][0]["sha256"] == record["sha256"]
    assert (project / "workspace" / "DATA_INDEX.md").exists()
    assert (project / "workspace" / "DATA_VALIDATION.md").exists()

    data_file.write_text('{"samples": [1, 2, 3, 4]}', encoding="utf-8")
    stale_validation = validate_data_index(project)

    assert stale_validation["valid"] is False
    assert stale_validation["summary"]["hash_mismatch_count"] == 1


def test_cli_register_and_validate_data(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_project(tmp_path)
    data_file = project / "data" / "labels.csv"
    data_file.write_text("id,label\n1,a\n", encoding="utf-8")

    registered = runner.invoke(
        app,
        ["register-data", "boc_demo", "--path", str(data_file), "--role", "labels", "--note", "Smoke labels"],
    )
    valid = runner.invoke(app, ["validate-data", "boc_demo"])

    assert registered.exit_code == 0, registered.output
    assert "Registered data" in registered.output
    assert valid.exit_code == 0, valid.output
    assert (project / "workspace" / "data_index.json").exists()
    assert (project / "workspace" / "data_validation.json").exists()

    data_file.write_text("id,label\n1,b\n", encoding="utf-8")
    invalid = runner.invoke(app, ["validate-data", "boc_demo"])

    assert invalid.exit_code == 1, invalid.output
    assert "hash_mismatch" in invalid.output


def test_run_experiment_snapshots_data_index(tmp_path: Path):
    project = _prepare_project(tmp_path, register=True)
    validation = validate_experiment_spec(project, "data_exp")
    metadata = run_experiment(project, "data_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    manifest = read_json(run_dir / "manifest.json")
    spec_snapshot = read_json(run_dir / "configs" / "experiment_spec_snapshot.json")
    data_snapshot = read_json(run_dir / "configs" / "data_index_snapshot.json")
    lineage = generate_run_lineage(project)

    assert validation["valid"] is True
    assert len(validation["source_fingerprint"]["current_sha256"]) == 64
    assert "configs/data_index_snapshot.json" in manifest["required_artifacts"]
    assert len(data_snapshot["sources"]) == 1
    assert len(spec_snapshot["data_contract"]["registered_data"]) == 1
    assert metadata["data_index"]["registered_count"] == 1
    assert lineage["runs"][0]["hashes"]["data_index_sha256"]
