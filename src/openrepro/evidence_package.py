"""Project-level evidence package generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from . import __version__
from .artifact_manager import list_run_dirs, required_handoff_files, sha256_file, validate_run_manifest
from .evidence_fingerprint import evidence_package_status, evidence_source_fingerprint
from .inspector import inspect_project
from .lineage import generate_run_lineage
from .project_manager import get_status
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
        "all_metrics_equal",
        "action_count",
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
                "manifest_sha256": sha256_file(run_dir / "manifest.json") if (run_dir / "manifest.json").exists() else None,
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

    inspect_summary = inspect_project(project_dir)
    lineage = generate_run_lineage(project_dir)
    status = get_status(project_dir).to_dict()
    status["evidence_package_exists"] = True
    workspace_artifacts = _workspace_artifacts(project_dir)
    experiments = _experiment_summaries(project_dir)
    runs = _run_summaries(project_dir)
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
        "| Run | Command | Valid | Experiment | Metrics |",
        "| --- | --- | --- | --- | --- |",
    ]
    for run in package["runs"]:
        run_lines.append(
            "| {run_id} | {command} | {valid} | {experiment_id} | {metric_files} |".format(
                run_id=_cell(run["run_id"]),
                command=_cell(run["command"]),
                valid=_cell(run["valid"]),
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
