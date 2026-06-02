from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.artifact_manager import validate_run_manifest
from openrepro.demo_runner import run_demo
from openrepro.document_loader import ingest_source
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.repair import preview_repair_actions
from openrepro.utils import read_json


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
    return project


def test_approve_candidates_promotes_scaffold_inputs(tmp_path: Path):
    project = _prepare_project(tmp_path)

    approval = approve_candidates(project, approve_all=True, reviewer="test-reviewer", verification_note="checked")
    summary = scaffold_experiment(project, experiment_id="verified_exp")
    exp_dir = Path(summary["experiment_dir"])
    config = read_json(exp_dir / "experiment_config.json")

    assert approval["schema_version"] == "0.5.0"
    assert approval["status"] == "verified_candidates_available"
    assert (project / "workspace" / "verified_candidates.json").exists()
    assert (project / "workspace" / "VERIFIED_CANDIDATES.md").exists()
    assert summary["status"] == "verified_inputs_ready"
    assert summary["runnable"] is True
    assert config["verified_candidates_path"] == "workspace/verified_candidates.json"
    assert config["verified_formula_candidate_ids"]
    assert config["verified_parameter_candidate_ids"]


def test_repair_dry_run_previews_manifest_diff_without_mutating_run(tmp_path: Path):
    project = _prepare_project(tmp_path)
    metadata = run_demo(project)
    run_dir = Path(metadata["run_dir"])
    (run_dir / "data" / "demo_metrics.json").write_text("{}", encoding="utf-8")

    before = validate_run_manifest(run_dir)
    preview = preview_repair_actions(project, run_dir)
    after = validate_run_manifest(run_dir)

    assert before["valid"] is False
    assert after["valid"] is False
    assert preview["schema_version"] == "0.5.0"
    assert preview["action_count"] >= 1
    assert any(action.get("diff") for action in preview["actions"])
    assert (project / "workspace" / "repair_dry_run.json").exists()
    assert (project / "workspace" / "REPAIR_DRY_RUN.md").exists()
