from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.document_loader import ingest_source
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.lineage import generate_run_lineage
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.utils import read_json


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="environment-test")
    scaffold_experiment(project, experiment_id="env_exp", template="boc-like")
    return project


def test_run_experiment_writes_environment_snapshot(tmp_path: Path):
    project = _prepare_project(tmp_path)

    metadata = run_experiment(project, "env_exp", confirm=True)
    run_dir = Path(metadata["run_dir"])
    snapshot = read_json(run_dir / "configs" / "environment_snapshot.json")
    manifest = read_json(run_dir / "manifest.json")

    assert snapshot["schema_version"] == "0.9.1"
    assert snapshot["python"]["version"]
    assert snapshot["dependencies"]["numpy"]
    assert snapshot["runner"]["sha256"]
    assert snapshot["random_seed"] == 7
    assert "configs/environment_snapshot.json" in manifest["required_artifacts"]


def test_same_seed_repeatability_check_matches_prior_run(tmp_path: Path):
    project = _prepare_project(tmp_path)

    first = Path(run_experiment(project, "env_exp", confirm=True)["run_dir"])
    second = Path(run_experiment(project, "env_exp", confirm=True)["run_dir"])
    first_snapshot = read_json(first / "configs" / "environment_snapshot.json")
    second_snapshot = read_json(second / "configs" / "environment_snapshot.json")

    assert first_snapshot["repeatability_check"]["status"] == "no_prior_same_seed_run"
    assert second_snapshot["repeatability_check"]["status"] == "matched"
    assert second_snapshot["repeatability_check"]["previous_run_dir"] == str(first)


def test_lineage_records_experiment_environment_hashes(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_experiment(project, "env_exp", confirm=True)

    lineage = generate_run_lineage(project)
    entry = lineage["runs"][0]
    hashes = entry["hashes"]

    assert lineage["schema_version"] == "1.3.0"
    assert hashes["experiment_spec_sha256"]
    assert hashes["data_index_sha256"]
    assert entry["parent_command"] == "run-experiment"
    assert entry["repeat_group_id"] == "experiment:env_exp"
    assert entry["repeat_run_index"] == 1
    assert entry["repeat_run_count"] == 1
    assert entry["experiment_provenance_complete"] is True
    assert hashes["experiment_config_sha256"]
    assert hashes["experiment_inputs_sha256"]
    assert hashes["environment_snapshot_sha256"]
    assert hashes["runner_sha256"]
