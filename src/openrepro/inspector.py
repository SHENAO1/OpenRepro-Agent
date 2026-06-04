"""Project inspection summary for humans and agents."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .advance import advance_summary
from .artifact_manager import latest_run_dir, list_run_dirs, validate_run_manifest
from .benchmark_runner import collect_benchmark_results
from .checkpoints import checkpoint_summary
from .claim_evidence_binder import claim_evidence_binder_summary, claim_evidence_binder_validation_summary
from .claim_evidence_report import claim_evidence_report_summary
from .claim_evidence_report_validation import claim_evidence_report_validation_summary
from .claim_signoff import claim_signoff_summary
from .claim_signoff_validation import claim_signoff_validation_summary
from .claim_trace import claim_trace_summary
from .collaboration_pack import collaboration_pack_summary
from .data_registry import data_index_summary
from .diagnostics import diagnose_project
from .document_loader import load_source_index
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .gaps import gaps_summary
from .project_manager import get_status
from .protocol_coverage import protocol_coverage_summary
from .protocol_plan import protocol_plan_summary
from .protocol_preflight import protocol_preflight_summary
from .quality_gate import latest_experiment_quality_gate_summary, latest_quality_gate_summary, quality_gate_summaries
from .refresh import refresh_run_summary
from .reproduction_protocol import protocol_summary
from .review_board import review_board_summary
from .review_decisions import review_decision_summary
from .review_site import review_site_summary
from .reviewer_packet import reviewer_packet_summary
from .scorecard import scorecard_summary
from .timeline import project_timeline_summary
from .utils import iso_now, read_json, write_json


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _candidate_count(project_dir: Path, filename: str) -> int:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    return len(data.get("candidates", [])) if isinstance(data, dict) else 0


def _candidate_risk_summary(project_dir: Path) -> dict[str, Any]:
    level_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    for filename in ["formula_candidates.json", "parameter_candidates.json"]:
        data = read_json(project_dir / "workspace" / filename, default={}) or {}
        candidates = data.get("candidates", []) if isinstance(data, dict) else []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            level_counts[str(candidate.get("risk_level") or "unknown")] += 1
            for flag in candidate.get("risk_flags", []):
                flag_counts[str(flag)] += 1
    return {
        "level_counts": dict(level_counts),
        "flag_counts": dict(flag_counts),
        "high_risk_count": int(level_counts.get("high", 0)),
    }


def _verified_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(data, dict):
        data = {}
    return {
        "status": data.get("status", "missing"),
        "formula_candidate_count": int(data.get("formula_candidate_count", 0) or 0),
        "parameter_candidate_count": int(data.get("parameter_candidate_count", 0) or 0),
        "path": str(project_dir / "workspace" / "verified_candidates.json") if data else None,
    }


def _candidate_review_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews = data.get("reviews", []) if isinstance(data, dict) else []
    counts = Counter(str(item.get("status")) for item in reviews if isinstance(item, dict))
    return {
        "status": "present" if reviews else "missing",
        "review_count": len(reviews),
        "status_counts": dict(counts),
    }


def _repair_dry_run_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "repair_dry_run.json", default={}) or {}
    if not isinstance(data, dict):
        data = {}
    return {
        "status": "present" if data else "missing",
        "created_at": data.get("created_at"),
        "healthy": data.get("healthy"),
        "action_count": int(data.get("action_count", 0) or 0),
        "path": str(project_dir / "workspace" / "repair_dry_run.json") if data else None,
    }


def _lineage_summary(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "run_lineage.json", default={}) or {}
    if not isinstance(data, dict):
        data = {}
    complete_runs = 0
    for item in data.get("runs", []) if isinstance(data.get("runs", []), list) else []:
        if isinstance(item, dict) and item.get("provenance_complete"):
            complete_runs += 1
    return {
        "status": "present" if data else "missing",
        "created_at": data.get("created_at"),
        "run_count": int(data.get("run_count", 0) or 0),
        "complete_run_count": complete_runs,
        "path": str(project_dir / "workspace" / "run_lineage.json") if data else None,
    }


def _run_command_counts(run_dirs: list[Path]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for run_dir in run_dirs:
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        if isinstance(manifest, dict):
            counts[str(manifest.get("command") or "unknown")] += 1
        else:
            counts["unknown"] += 1
    return dict(counts)


def _benchmark_runs_for_project(project_dir: Path) -> list[dict[str, Any]]:
    runs_dirs = [Path.cwd() / "benchmarks" / "runs", _repo_root() / "benchmarks" / "runs"]
    seen: set[str] = set()
    matches: list[dict[str, Any]] = []
    project_name = project_dir.name
    project_strings = {str(project_dir), str(project_dir.resolve())}
    for runs_dir in runs_dirs:
        for result in collect_benchmark_results(runs_dir):
            result_path = str(result.get("_result_path", ""))
            if result_path in seen:
                continue
            seen.add(result_path)
            result_project = str(result.get("project_dir", ""))
            if result_project in project_strings or Path(result_project).name == project_name:
                matches.append(result)
    return matches


def inspect_project(project_dir: Path) -> dict[str, Any]:
    """Inspect a project and write workspace/inspect_summary.json."""
    project_dir = Path(project_dir)
    status = get_status(project_dir)
    source_index = load_source_index(project_dir)
    sources = source_index.get("sources", [])
    pdf_sources = [source for source in sources if source.get("suffix") == ".pdf"]
    pdf_status_counts = Counter(str(source.get("extraction_status") or "not_pdf") for source in pdf_sources)

    run_dirs = list_run_dirs(project_dir)
    latest = latest_run_dir(project_dir)
    latest_validation = validate_run_manifest(latest) if latest is not None else None
    latest_manifest_status = "missing"
    if latest_validation is not None:
        latest_manifest_status = "valid" if latest_validation.get("valid") else "invalid"
    diagnosis = diagnose_project(project_dir, latest)
    benchmark_runs = _benchmark_runs_for_project(project_dir)
    verified = _verified_summary(project_dir)
    candidate_risk = _candidate_risk_summary(project_dir)
    reviews = _candidate_review_summary(project_dir)
    repair_dry_run = _repair_dry_run_summary(project_dir)
    lineage = _lineage_summary(project_dir)
    scaffolds = inspect_experiment_scaffolds(project_dir)
    spec_summary = inspect_experiment_specs(project_dir)
    data_summary = data_index_summary(project_dir)
    quality_gates = quality_gate_summaries(project_dir)
    latest_quality_gate = latest_quality_gate_summary(project_dir)
    latest_experiment_quality_gate = latest_experiment_quality_gate_summary(project_dir)
    trace_summary = claim_trace_summary(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    checkpoints = checkpoint_summary(project_dir)
    advance = advance_summary(project_dir)
    review_board = review_board_summary(project_dir)
    review_decisions = review_decision_summary(project_dir)
    protocol = protocol_summary(project_dir)
    protocol_coverage = protocol_coverage_summary(project_dir)
    protocol_plan = protocol_plan_summary(project_dir)
    protocol_preflight = protocol_preflight_summary(project_dir)
    claim_binder = claim_evidence_binder_summary(project_dir)
    binder_validation = claim_evidence_binder_validation_summary(project_dir)
    claim_signoff = claim_signoff_summary(project_dir)
    claim_signoff_validation = claim_signoff_validation_summary(project_dir)
    claim_evidence_report = claim_evidence_report_summary(project_dir)
    claim_evidence_report_validation = claim_evidence_report_validation_summary(project_dir)
    reviewer_packet = reviewer_packet_summary(project_dir)
    review_site = review_site_summary(project_dir)
    project_timeline = project_timeline_summary(project_dir)
    collaboration_pack = collaboration_pack_summary(project_dir)
    refresh_run = refresh_run_summary(project_dir)
    run_command_counts = _run_command_counts(run_dirs)

    summary = {
        "schema_version": "0.9.2",
        "created_at": iso_now(),
        "project_name": status.project_name,
        "project_dir": str(project_dir),
        "source_count": len(sources),
        "pdf_source_count": len(pdf_sources),
        "pdf_extraction_statuses": dict(pdf_status_counts),
        "formula_candidate_count": _candidate_count(project_dir, "formula_candidates.json"),
        "parameter_candidate_count": _candidate_count(project_dir, "parameter_candidates.json"),
        "candidate_high_risk_count": candidate_risk["high_risk_count"],
        "candidate_risk_level_counts": candidate_risk["level_counts"],
        "candidate_risk_flag_counts": candidate_risk["flag_counts"],
        "verified_formula_candidate_count": verified["formula_candidate_count"],
        "verified_parameter_candidate_count": verified["parameter_candidate_count"],
        "verified_candidates_status": verified["status"],
        "candidate_review_status": reviews["status"],
        "candidate_review_count": reviews["review_count"],
        "candidate_review_status_counts": reviews["status_counts"],
        "experiment_scaffold_count": scaffolds["scaffold_count"],
        "experiment_template_counts": scaffolds["template_counts"],
        "experiment_input_completeness_counts": scaffolds["input_completeness_counts"],
        "experiment_missing_required_input_count": scaffolds["missing_required_input_count"],
        "experiment_expected_artifacts_valid_count": scaffolds["expected_artifacts_valid_count"],
        "experiment_expected_artifacts_attention_count": scaffolds["expected_artifacts_attention_count"],
        "experiment_scaffold_issue_counts": scaffolds["issue_counts"],
        "experiment_scaffolds": scaffolds["scaffolds"],
        "experiment_spec_status_counts": spec_summary["status_counts"],
        "experiment_spec_stale_count": spec_summary["stale_count"],
        "experiment_spec_invalid_count": spec_summary["invalid_count"],
        "experiment_spec_missing_count": spec_summary["missing_count"],
        "experiment_specs": spec_summary["specs"],
        "data_registered_count": data_summary["registered_count"],
        "data_valid_count": data_summary["valid_count"],
        "data_invalid_count": data_summary["invalid_count"],
        "data_missing_count": data_summary["missing_count"],
        "data_hash_mismatch_count": data_summary["hash_mismatch_count"],
        "data_role_counts": data_summary["role_counts"],
        "data_status_counts": data_summary["status_counts"],
        "data_sources": data_summary["sources"],
        "run_count": len(run_dirs),
        "run_command_counts": run_command_counts,
        "experiment_run_count": run_command_counts.get("run-experiment", 0),
        "quality_gate_status": latest_quality_gate["status"],
        "quality_gate_failed_check_count": latest_quality_gate["failed_check_count"],
        "experiment_quality_gate_status": latest_experiment_quality_gate["status"],
        "experiment_quality_gate_failed_check_count": latest_experiment_quality_gate["failed_check_count"],
        "failed_quality_gate_check_names": sorted({name for gate in quality_gates for name in gate.get("failed_check_names", [])}),
        "quality_gate_passed_count": sum(1 for gate in quality_gates if gate.get("status") == "passed"),
        "quality_gate_failed_count": sum(1 for gate in quality_gates if gate.get("status") == "failed"),
        "quality_gates": quality_gates,
        "claim_trace_status": "present" if trace_summary["present"] else "missing",
        "claim_trace_claim_count": trace_summary["claim_count"],
        "claim_trace_verified_claim_count": trace_summary["verified_claim_count"],
        "claim_trace_experiment_count": trace_summary["experiment_trace_count"],
        "claim_trace_run_count": trace_summary["run_trace_count"],
        "claim_trace_validation_status": trace_summary["validation_status"],
        "claim_trace_validation_issue_count": trace_summary["validation_issue_count"],
        "claim_trace_validation_warning_count": trace_summary["validation_warning_count"],
        "scorecard_status": scorecard["overall_status"],
        "scorecard_overall_score": scorecard["overall_score"],
        "scorecard_blocking_dimension_count": scorecard["blocking_dimension_count"],
        "scorecard_partial_dimension_count": scorecard["partial_dimension_count"],
        "gaps_status": gaps["status"],
        "gaps_open_count": gaps["open_count"],
        "gaps_critical_count": gaps["critical_count"],
        "gaps_high_count": gaps["high_count"],
        "gaps_top_suggested_command": gaps["top_suggested_command"],
        "checkpoint_status": checkpoints["status"],
        "checkpoint_complete_count": checkpoints["complete_count"],
        "checkpoint_blocked_count": checkpoints["blocked_count"],
        "checkpoint_partial_count": checkpoints["partial_count"],
        "checkpoint_missing_count": checkpoints["missing_count"],
        "checkpoint_next_checkpoint": checkpoints["next_checkpoint"],
        "checkpoint_next_command": checkpoints["next_command"],
        "advance_status": advance["status"],
        "advance_action_count": advance["action_count"],
        "advance_top_command": advance["top_command"],
        "review_board_status": review_board["status"],
        "review_board_item_count": review_board["item_count"],
        "review_board_critical_count": review_board["critical_count"],
        "review_board_high_count": review_board["high_count"],
        "review_board_top_item": review_board["top_item"],
        "review_board_top_command": review_board["top_command"],
        "review_decision_status": review_decisions["status"],
        "review_decision_count": review_decisions["decision_count"],
        "review_decision_closed_count": review_decisions["closed_count"],
        "review_decision_unresolved_item_count": review_decisions["unresolved_item_count"],
        "review_decision_top_command": review_decisions["top_command"],
        "protocol_status": protocol["status"],
        "protocol_criterion_count": protocol["criterion_count"],
        "protocol_blocking_criterion_count": protocol["blocking_criterion_count"],
        "protocol_top_command": protocol["top_command"],
        "protocol_coverage_status": protocol_coverage["status"],
        "protocol_coverage_score": protocol_coverage["coverage_score"],
        "protocol_coverage_uncovered_count": protocol_coverage["uncovered_count"],
        "protocol_coverage_top_command": protocol_coverage["top_command"],
        "protocol_plan_status": protocol_plan["status"],
        "protocol_plan_action_count": protocol_plan["action_count"],
        "protocol_plan_critical_count": protocol_plan["critical_count"],
        "protocol_plan_high_count": protocol_plan["high_count"],
        "protocol_plan_top_command": protocol_plan["top_command"],
        "protocol_preflight_status": protocol_preflight["status"],
        "protocol_preflight_check_count": protocol_preflight["check_count"],
        "protocol_preflight_blocking_count": protocol_preflight["blocking_count"],
        "protocol_preflight_warning_count": protocol_preflight["warning_count"],
        "protocol_preflight_top_command": protocol_preflight["top_command"],
        "claim_evidence_binder_status": claim_binder["status"],
        "claim_evidence_binder_claim_count": claim_binder["claim_count"],
        "claim_evidence_binder_complete_claim_count": claim_binder["complete_claim_count"],
        "claim_evidence_binder_incomplete_claim_count": claim_binder["incomplete_claim_count"],
        "claim_evidence_binder_top_command": claim_binder["top_command"],
        "claim_evidence_binder_validation_status": binder_validation["status"],
        "claim_evidence_binder_validation_issue_count": binder_validation["issue_count"],
        "claim_evidence_binder_validation_warning_count": binder_validation["warning_count"],
        "claim_evidence_binder_validation_top_command": binder_validation["top_command"],
        "claim_signoff_status": claim_signoff["status"],
        "claim_signoff_signed_claim_count": claim_signoff["signed_claim_count"],
        "claim_signoff_open_claim_count": claim_signoff["open_claim_count"],
        "claim_signoff_accepted_count": claim_signoff["accepted_count"],
        "claim_signoff_top_command": claim_signoff["top_command"],
        "claim_signoff_validation_status": claim_signoff_validation["status"],
        "claim_signoff_validation_issue_count": claim_signoff_validation["issue_count"],
        "claim_signoff_validation_warning_count": claim_signoff_validation["warning_count"],
        "claim_signoff_validation_top_command": claim_signoff_validation["top_command"],
        "claim_evidence_report_status": claim_evidence_report["status"],
        "claim_evidence_report_claim_count": claim_evidence_report["claim_count"],
        "claim_evidence_report_open_action_count": claim_evidence_report["open_action_count"],
        "claim_evidence_report_top_command": claim_evidence_report["top_command"],
        "claim_evidence_report_validation_status": claim_evidence_report_validation["status"],
        "claim_evidence_report_validation_issue_count": claim_evidence_report_validation["issue_count"],
        "claim_evidence_report_validation_warning_count": claim_evidence_report_validation["warning_count"],
        "claim_evidence_report_validation_top_command": claim_evidence_report_validation["top_command"],
        "reviewer_packet_status": reviewer_packet["status"],
        "reviewer_packet_open_action_count": reviewer_packet["open_action_count"],
        "reviewer_packet_validation_issue_count": reviewer_packet["validation_issue_count"],
        "reviewer_packet_top_command": reviewer_packet["top_command"],
        "review_site_status": review_site["status"],
        "review_site_open_action_count": review_site["open_action_count"],
        "review_site_blocker_count": review_site["blocker_count"],
        "review_site_top_command": review_site["top_command"],
        "project_timeline_status": project_timeline["status"],
        "project_timeline_event_count": project_timeline["event_count"],
        "project_timeline_human_decision_count": project_timeline["human_decision_count"],
        "project_timeline_latest_event_title": project_timeline["latest_event_title"],
        "collaboration_pack_status": collaboration_pack["status"],
        "collaboration_pack_unresolved_decision_count": collaboration_pack["unresolved_decision_count"],
        "collaboration_pack_next_safe_command_count": collaboration_pack["next_safe_command_count"],
        "collaboration_pack_top_command": collaboration_pack["top_command"],
        "refresh_run_status": refresh_run["status"],
        "refresh_run_step_count": refresh_run["step_count"],
        "refresh_run_failed_step_count": refresh_run["failed_step_count"],
        "refresh_run_top_failed_step": refresh_run["top_failed_step"],
        "refresh_run_top_command": refresh_run["top_command"],
        "latest_run_dir": str(latest) if latest else None,
        "latest_manifest_status": latest_manifest_status,
        "latest_manifest_valid": latest_validation.get("valid") if latest_validation else None,
        "benchmark_run_count": len(benchmark_runs),
        "diagnosis_healthy": diagnosis.get("healthy"),
        "diagnosis_issue_count": len(diagnosis.get("issues", [])),
        "latest_repair_dry_run_status": repair_dry_run["status"],
        "latest_repair_dry_run_action_count": repair_dry_run["action_count"],
        "latest_repair_dry_run_healthy": repair_dry_run["healthy"],
        "lineage_status": lineage["status"],
        "lineage_run_count": lineage["run_count"],
        "lineage_complete_run_count": lineage["complete_run_count"],
        "next_step": status.next_step,
    }
    write_json(project_dir / "workspace" / "inspect_summary.json", summary)
    return summary
