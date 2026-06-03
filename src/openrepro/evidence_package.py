"""Project-level evidence package generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from . import __version__
from .advance import generate_advance_plan
from .artifact_manager import list_run_dirs, required_handoff_files, sha256_file, validate_run_manifest
from .checkpoints import generate_workflow_checkpoints
from .claim_trace import generate_claim_trace, validate_claim_trace
from .data_registry import data_index_summary
from .evidence_fingerprint import evidence_package_status, evidence_source_fingerprint
from .experiment_spec import inspect_experiment_specs
from .gaps import generate_reproduction_gaps
from .inspector import inspect_project
from .lineage import generate_run_lineage
from .project_manager import get_status
from .quality_gate import quality_gate_summaries
from .review_board import generate_review_board
from .review_decisions import generate_review_decisions
from .scorecard import generate_reproduction_scorecard
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

EVIDENCE_PACKAGE_SCHEMA_VERSION = "1.0.1"

WORKSPACE_ARTIFACTS = [
    "source_index.json",
    "paper_metadata.json",
    "analysis_result.json",
    "formula_candidates.json",
    "parameter_candidates.json",
    "model_ledger.json",
    "caption_index.json",
    "verified_candidates.json",
    "candidate_reviews.json",
    "experiment_plan_validation.json",
    "experiment_scaffold_summary.json",
    "experiment_input_validation.json",
    "data_index.json",
    "data_validation.json",
    "quality_gate_summary.json",
    "claim_trace.json",
    "claim_trace_validation.json",
    "reproduction_scorecard.json",
    "reproduction_gaps.json",
    "workflow_checkpoints.json",
    "advance_plan.json",
    "review_board.json",
    "review_decisions.json",
    "experiment_comparison.json",
    "run_comparison.json",
    "run_lineage.json",
    "doctor.json",
    "repair_plan.json",
    "repair_dry_run.json",
    "repair_apply.json",
]


def _artifact_summary(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"type": type(data).__name__}
    summary: dict[str, Any] = {}
    for key in [
        "schema_version",
        "created_at",
        "status",
        "healthy",
        "valid",
        "project_name",
        "experiment_id",
        "template",
        "run_count",
        "source_count",
        "formula_candidate_count",
        "parameter_candidate_count",
        "candidate_review_count",
        "experiment_run_count",
        "benchmark_run_count",
        "registered_count",
        "invalid_count",
        "all_metrics_equal",
        "action_count",
        "item_count",
        "critical_count",
        "high_count",
        "top_command",
        "decision_count",
        "closed_count",
        "unresolved_item_count",
    ]:
        if key in data:
            summary[key] = data.get(key)
    if isinstance(data.get("sources"), list):
        summary["source_count"] = len(data["sources"])
    if isinstance(data.get("candidates"), list):
        summary["candidate_count"] = len(data["candidates"])
    if isinstance(data.get("reviews"), list):
        summary["review_count"] = len(data["reviews"])
    if isinstance(data.get("runs"), list):
        summary["run_count"] = len(data["runs"])
    if isinstance(data.get("issues"), list):
        summary["issue_count"] = len(data["issues"])
    if isinstance(data.get("metric_deltas"), list):
        summary["metric_delta_count"] = len(data["metric_deltas"])
    return summary


def _workspace_artifacts(project_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for name in WORKSPACE_ARTIFACTS:
        path = project_dir / "workspace" / name
        data = read_json(path, default=None)
        artifacts.append(
            {
                "name": name,
                "path": str(path),
                "present": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
                "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
                "summary": _artifact_summary(data) if path.exists() else {},
            }
        )
    return artifacts


def _experiment_summaries(project_dir: Path) -> list[dict[str, Any]]:
    experiments_dir = project_dir / "experiments"
    if not experiments_dir.exists():
        return []
    summaries: list[dict[str, Any]] = []
    for exp_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
        config = read_json(exp_dir / "experiment_config.json", default={}) or {}
        inputs = read_json(exp_dir / "experiment_inputs.json", default={}) or {}
        expected = read_json(exp_dir / "expected_artifacts.json", default={}) or {}
        spec = read_json(exp_dir / "experiment_spec.json", default={}) or {}
        input_completeness = inputs.get("input_completeness", {}) if isinstance(inputs, dict) else {}
        spec_path = exp_dir / "experiment_spec.json"
        summaries.append(
            {
                "experiment_id": exp_dir.name,
                "path": str(exp_dir),
                "status": config.get("status") if isinstance(config, dict) else None,
                "runnable": config.get("runnable") if isinstance(config, dict) else None,
                "template": config.get("template") if isinstance(config, dict) else None,
                "input_completeness": input_completeness.get("status") if isinstance(input_completeness, dict) else None,
                "missing_required_inputs": input_completeness.get("missing", []) if isinstance(input_completeness, dict) else [],
                "required_artifact_count": len(expected.get("required", [])) if isinstance(expected, dict) else 0,
                "has_spec": spec_path.exists(),
                "spec_schema_version": spec.get("schema_version") if isinstance(spec, dict) else None,
                "spec_sha256": sha256_file(spec_path) if spec_path.exists() else None,
                "has_runner": (exp_dir / "runner.py").exists(),
                "has_runner_stub": (exp_dir / "runner_stub.py").exists(),
            }
        )
    return summaries


def _run_metric_files(run_dir: Path) -> list[str]:
    candidates = [
        run_dir / "data" / "metrics.json",
        run_dir / "data" / "demo_metrics.json",
        run_dir / "data" / "sweep_results.json",
        run_dir / "data" / "execution_result.json",
    ]
    return [str(path) for path in candidates if path.exists()]


def _run_summaries(project_dir: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for run_dir in reversed(list_run_dirs(project_dir)):
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        manifest = manifest if isinstance(manifest, dict) else {}
        validation = validate_run_manifest(run_dir)
        metadata = manifest.get("metadata", {}) if isinstance(manifest.get("metadata"), dict) else {}
        quality_gate = read_json(run_dir / "reports" / "quality_gate.json", default={}) or {}
        quality_gate = quality_gate if isinstance(quality_gate, dict) else {}
        summaries.append(
            {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "command": manifest.get("command", "unknown"),
                "created_at": manifest.get("created_at"),
                "valid": validation.get("valid"),
                "checked_artifacts": validation.get("checked_artifacts"),
                "error_count": len(validation.get("errors", [])),
                "experiment_id": metadata.get("experiment_id"),
                "template": metadata.get("template"),
                "metric_files": _run_metric_files(run_dir),
                "quality_gate_status": quality_gate.get("status") if quality_gate else "missing",
                "quality_gate_failed_check_count": quality_gate.get("failed_check_count") if quality_gate else None,
                "quality_gate_failed_check_names": quality_gate.get("failed_check_names", []) if quality_gate else [],
                "manifest_sha256": sha256_file(run_dir / "manifest.json") if (run_dir / "manifest.json").exists() else None,
                "quality_gate_sha256": sha256_file(run_dir / "reports" / "quality_gate.json")
                if (run_dir / "reports" / "quality_gate.json").exists()
                else None,
            }
        )
    return summaries


def _benchmark_index_summary(project_dir: Path) -> dict[str, Any]:
    candidates = [
        Path.cwd() / "benchmarks" / "runs" / "benchmark_index.json",
        project_dir.parent / "benchmarks" / "runs" / "benchmark_index.json",
        Path(__file__).resolve().parents[2] / "benchmarks" / "runs" / "benchmark_index.json",
    ]
    seen: set[str] = set()
    indexes = []
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        data = read_json(path, default={}) or {}
        indexes.append(
            {
                "path": str(path),
                "present": path.exists(),
                "summary": _artifact_summary(data) if path.exists() else {},
            }
        )
    return {"indexes": indexes}


def _handoff_summary(project_dir: Path) -> dict[str, Any]:
    files = [
        {"name": name, "present": (project_dir / "handoff" / name).exists(), "path": str(project_dir / "handoff" / name)}
        for name in required_handoff_files()
    ]
    return {
        "complete": all(item["present"] for item in files),
        "present_count": sum(1 for item in files if item["present"]),
        "required_count": len(files),
        "files": files,
    }


def _write_handoff_evidence_summary(project_dir: Path, markdown: str) -> None:
    handoff = project_dir / "handoff"
    if handoff.exists():
        safe_write_text(handoff / "EVIDENCE_PACKAGE.md", markdown)


def export_evidence_package_zip(project_dir: Path, package: dict[str, Any]) -> Path:
    """Export a compact evidence package zip under reports/."""
    project_dir = Path(project_dir)
    zip_path = project_dir / "reports" / "evidence_package.zip"
    json_path = project_dir / "reports" / "evidence_package.json"
    markdown_path = project_dir / "reports" / "evidence_package.md"
    files = [json_path, markdown_path]
    files.extend(
        Path(item["path"])
        for item in package.get("workspace_artifacts", [])
        if item.get("present") and item.get("path")
    )
    files.extend(project_dir / "handoff" / item["name"] for item in package.get("handoff", {}).get("files", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def generate_evidence_package(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write reports/evidence_package.json and reports/evidence_package.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    claim_trace = generate_claim_trace(project_dir)
    claim_trace_validation = validate_claim_trace(project_dir)
    lineage = generate_run_lineage(project_dir)
    scorecard = generate_reproduction_scorecard(project_dir)
    gaps = generate_reproduction_gaps(project_dir)
    checkpoints = generate_workflow_checkpoints(project_dir)
    advance = generate_advance_plan(project_dir, dry_run=True)
    review_board = generate_review_board(project_dir)
    review_decisions = generate_review_decisions(project_dir)
    inspect_summary = inspect_project(project_dir)
    status = get_status(project_dir).to_dict()
    status["evidence_package_exists"] = True
    workspace_artifacts = _workspace_artifacts(project_dir)
    experiments = _experiment_summaries(project_dir)
    spec_summary = inspect_experiment_specs(project_dir)
    data_summary = data_index_summary(project_dir)
    runs = _run_summaries(project_dir)
    quality_gates = quality_gate_summaries(project_dir)
    source_fingerprint = evidence_source_fingerprint(project_dir)
    package = {
        "schema_version": EVIDENCE_PACKAGE_SCHEMA_VERSION,
        "openrepro_version": __version__,
        "created_at": iso_now(),
        "project_name": status["project_name"],
        "project_dir": str(project_dir),
        "status": status,
        "inspect_summary": inspect_summary,
        "source_fingerprint": source_fingerprint,
        "freshness": {
            "status": "current",
            "stale": False,
            "package_sha256": source_fingerprint["sha256"],
            "current_sha256": source_fingerprint["sha256"],
        },
        "workspace_artifacts": workspace_artifacts,
        "experiments": experiments,
        "experiment_specs": spec_summary,
        "data_registry": data_summary,
        "quality_gates": quality_gates,
        "claim_trace": {
            "schema_version": claim_trace.get("schema_version"),
            "claim_count": claim_trace.get("claim_count"),
            "verified_claim_count": claim_trace.get("verified_claim_count"),
            "experiment_trace_count": claim_trace.get("experiment_trace_count"),
            "run_trace_count": claim_trace.get("run_trace_count"),
            "validation_status": claim_trace_validation.get("status"),
            "validation_issue_count": claim_trace_validation.get("issue_count"),
            "validation_warning_count": claim_trace_validation.get("warning_count"),
            "path": str(project_dir / "workspace" / "claim_trace.json"),
            "validation_path": str(project_dir / "workspace" / "claim_trace_validation.json"),
        },
        "scorecard": {
            "schema_version": scorecard.get("schema_version"),
            "overall_score": scorecard.get("overall_score"),
            "overall_status": scorecard.get("overall_status"),
            "blocking_dimension_count": scorecard.get("blocking_dimension_count"),
            "partial_dimension_count": scorecard.get("partial_dimension_count"),
            "path": str(project_dir / "workspace" / "reproduction_scorecard.json"),
        },
        "gaps": {
            "schema_version": gaps.get("schema_version"),
            "status": gaps.get("status"),
            "open_count": gaps.get("open_count"),
            "critical_count": gaps.get("critical_count"),
            "high_count": gaps.get("high_count"),
            "top_suggested_command": gaps.get("top_suggested_command"),
            "path": str(project_dir / "workspace" / "reproduction_gaps.json"),
        },
        "checkpoints": {
            "schema_version": checkpoints.get("schema_version"),
            "status": checkpoints.get("status"),
            "complete_count": checkpoints.get("complete_count"),
            "blocked_count": checkpoints.get("blocked_count"),
            "partial_count": checkpoints.get("partial_count"),
            "missing_count": checkpoints.get("missing_count"),
            "next_checkpoint": checkpoints.get("next_checkpoint"),
            "next_command": checkpoints.get("next_command"),
            "path": str(project_dir / "workspace" / "workflow_checkpoints.json"),
        },
        "advance_plan": {
            "schema_version": advance.get("schema_version"),
            "status": advance.get("status"),
            "dry_run": advance.get("dry_run"),
            "action_count": advance.get("action_count"),
            "top_command": advance.get("top_command"),
            "source": advance.get("source"),
            "path": str(project_dir / "workspace" / "advance_plan.json"),
        },
        "review_board": {
            "schema_version": review_board.get("schema_version"),
            "status": review_board.get("status"),
            "item_count": review_board.get("item_count"),
            "critical_count": review_board.get("critical_count"),
            "high_count": review_board.get("high_count"),
            "top_command": review_board.get("top_command"),
            "path": str(project_dir / "workspace" / "review_board.json"),
        },
        "review_decisions": {
            "schema_version": review_decisions.get("schema_version"),
            "status": review_decisions.get("status"),
            "decision_count": review_decisions.get("decision_count"),
            "closed_count": review_decisions.get("closed_count"),
            "followup_count": review_decisions.get("followup_count"),
            "deferred_count": review_decisions.get("deferred_count"),
            "unresolved_item_count": review_decisions.get("unresolved_item_count"),
            "top_command": review_decisions.get("top_command"),
            "path": str(project_dir / "workspace" / "review_decisions.json"),
        },
        "runs": runs,
        "lineage": {
            "schema_version": lineage.get("schema_version"),
            "run_count": lineage.get("run_count"),
            "path": str(project_dir / "workspace" / "run_lineage.json"),
        },
        "benchmark_indexes": _benchmark_index_summary(project_dir),
        "reports": {
            "project_report": {
                "present": (project_dir / "reports" / "report.md").exists(),
                "path": str(project_dir / "reports" / "report.md"),
            },
            "evidence_package_json": str(project_dir / "reports" / "evidence_package.json"),
            "evidence_package_markdown": str(project_dir / "reports" / "evidence_package.md"),
            "evidence_package_zip": str(project_dir / "reports" / "evidence_package.zip") if export_zip else None,
        },
        "handoff": _handoff_summary(project_dir),
        "policy": "Evidence package records workflow evidence only; it does not claim paper reproduction success.",
        "evidence_limits": [
            "Candidate formulas and parameters remain unverified unless explicitly reviewed by a human.",
            "Successful runners and valid manifests are engineering evidence, not scientific validation.",
            "Benchmark artifacts report workflow compliance, not scientific benchmark scores.",
        ],
    }
    write_json(project_dir / "reports" / "evidence_package.json", package)
    markdown = _render_markdown(package)
    safe_write_text(project_dir / "reports" / "evidence_package.md", markdown)
    _write_handoff_evidence_summary(project_dir, markdown)
    if export_zip:
        zip_path = export_evidence_package_zip(project_dir, package)
        package["reports"]["evidence_package_zip"] = str(zip_path)
        write_json(project_dir / "reports" / "evidence_package.json", package)
    package["freshness"] = evidence_package_status(project_dir)
    return package


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(package: dict[str, Any]) -> str:
    artifact_lines = [
        "| Artifact | Present | SHA-256 | Summary |",
        "| --- | --- | --- | --- |",
    ]
    for artifact in package["workspace_artifacts"]:
        artifact_lines.append(
            f"| {artifact['name']} | {artifact['present']} | {_cell(artifact.get('sha256'))} | {_cell(artifact['summary'])} |"
        )

    experiment_lines = [
        "| Experiment | Template | Status | Inputs | Missing Inputs | Spec | Runner |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for experiment in package["experiments"]:
        experiment_lines.append(
            "| {experiment_id} | {template} | {status} | {inputs} | {missing} | {spec} | {runner} |".format(
                experiment_id=_cell(experiment["experiment_id"]),
                template=_cell(experiment["template"]),
                status=_cell(experiment["status"]),
                inputs=_cell(experiment["input_completeness"]),
                missing=_cell(experiment["missing_required_inputs"]),
                spec=_cell(experiment.get("has_spec")),
                runner=_cell(experiment["has_runner"]),
            )
        )

    run_lines = [
        "| Run | Command | Valid | Gate | Failed Checks | Experiment | Metrics |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in package["runs"]:
        run_lines.append(
            "| {run_id} | {command} | {valid} | {gate} | {failed} | {experiment_id} | {metric_files} |".format(
                run_id=_cell(run["run_id"]),
                command=_cell(run["command"]),
                valid=_cell(run["valid"]),
                gate=_cell(run.get("quality_gate_status")),
                failed=_cell(run.get("quality_gate_failed_check_names", [])),
                experiment_id=_cell(run["experiment_id"]),
                metric_files=_cell(len(run["metric_files"])),
            )
        )

    return f"""# Evidence Package

- schema_version: {package['schema_version']}
- openrepro_version: {package['openrepro_version']}
- created_at: {package['created_at']}
- project_name: {package['project_name']}
- project_dir: `{package['project_dir']}`
- freshness: {package['freshness']['status']}
- source_fingerprint: {package['source_fingerprint']['sha256']}

## Status

- initialized: {package['status']['initialized']}
- ingested: {package['status']['ingested']}
- analyzed: {package['status']['analyzed']}
- planned: {package['status']['planned']}
- experiment_scaffold_count: {package['status']['experiment_scaffold_count']}
- experiment_run_count: {package['status']['experiment_run_count']}
- experiment_spec_status_counts: {package['experiment_specs']['status_counts']}
- data_registered_count: {package['data_registry']['registered_count']}
- data_status_counts: {package['data_registry']['status_counts']}
- quality_gate_passed_count: {sum(1 for gate in package['quality_gates'] if gate.get('status') == 'passed')}
- quality_gate_failed_count: {sum(1 for gate in package['quality_gates'] if gate.get('status') == 'failed')}
- failed_quality_gate_check_names: {sorted({name for gate in package['quality_gates'] for name in gate.get('failed_check_names', [])})}
- claim_trace_claim_count: {package['claim_trace']['claim_count']}
- claim_trace_experiment_count: {package['claim_trace']['experiment_trace_count']}
- claim_trace_validation_status: {package['claim_trace']['validation_status']}
- claim_trace_validation_issue_count: {package['claim_trace']['validation_issue_count']}
- scorecard_overall_score: {package['scorecard']['overall_score']}
- scorecard_status: {package['scorecard']['overall_status']}
- gaps_status: {package['gaps']['status']}
- gaps_open_count: {package['gaps']['open_count']}
- checkpoint_status: {package['checkpoints']['status']}
- checkpoint_next_checkpoint: {package['checkpoints']['next_checkpoint']}
- advance_plan_status: {package['advance_plan']['status']}
- advance_plan_action_count: {package['advance_plan']['action_count']}
- review_board_status: {package['review_board']['status']}
- review_board_item_count: {package['review_board']['item_count']}
- review_decision_status: {package['review_decisions']['status']}
- review_decision_unresolved_item_count: {package['review_decisions']['unresolved_item_count']}
- lineage_exists: {package['status']['lineage_exists']}
- handoff_complete: {package['status']['handoff_complete']}
- source_file_count: {package['source_fingerprint']['file_count']}

## Workspace Artifacts

{chr(10).join(artifact_lines)}

## Experiments

{chr(10).join(experiment_lines)}

## Runs

{chr(10).join(run_lines)}

## Handoff

- complete: {package['handoff']['complete']}
- present_count: {package['handoff']['present_count']}
- required_count: {package['handoff']['required_count']}

## Policy

{package['policy']}

## Evidence Limits

{chr(10).join(f"- {item}" for item in package['evidence_limits'])}
"""
