from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.document_loader import ingest_source
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.quality_gate import evaluate_all_quality_gates, evaluate_run_quality
from openrepro.repair import create_repair_plan, preview_repair_actions
from openrepro.utils import read_json, write_json


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Repair Gate Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    approve_candidates(project, approve_all=True, reviewer="repair-gate-test")
    scaffold_experiment(project, experiment_id="repair_exp", template="boc-like")
    return project


def _tamper_required_metric(run_dir: Path) -> None:
    metrics_path = run_dir / "data" / "metrics.json"
    metrics = read_json(metrics_path)
    metrics.pop("signal_energy")
    write_json(metrics_path, metrics)


def test_repair_plan_maps_quality_gate_checks_to_actions(tmp_path: Path):
    project = _prepare_project(tmp_path)
    run_dir = Path(run_experiment(project, "repair_exp", confirm=True)["run_dir"])
    _tamper_required_metric(run_dir)
    evaluate_run_quality(project, run_dir)
    evaluate_all_quality_gates(project)

    plan = create_repair_plan(project, run_dir)
    preview = preview_repair_actions(project, run_dir)
    plan_actions = {action["code"]: action for action in plan["actions"]}
    preview_actions = {action["code"]: action for action in preview["actions"]}

    assert plan["healthy"] is False
    assert plan["quality_gate_summary"]["failed_count"] == 1
    assert plan_actions["quality_gate_metrics_missing"]["automation"] == "rerun_experiment_or_restore_metrics"
    assert plan_actions["quality_gate_manifest_failed"]["automation"] == "preview_manifest_repair"
    assert preview_actions["quality_gate_metrics_missing"]["quality_gate_check"] == "required_metrics_present"
    assert "no metrics are fabricated" in preview_actions["quality_gate_metrics_missing"]["preview"]
    assert (project / "workspace" / "REPAIR_PLAN.md").exists()
    assert (project / "workspace" / "REPAIR_DRY_RUN.md").exists()
