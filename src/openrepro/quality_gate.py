"""Run quality gates for execution evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import latest_run_dir, list_run_dirs, sha256_file, validate_run_manifest
from .utils import iso_now, read_json, safe_write_text, write_json

QUALITY_GATE_SCHEMA_VERSION = "1.4.1"


def _check(name: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "status": "passed" if passed else "failed",
        "message": message,
        "details": details or {},
    }


def _metric_payload(run_dir: Path) -> dict[str, Any]:
    metrics_path = run_dir / "data" / "metrics.json"
    metrics = read_json(metrics_path, default={}) or {}
    return metrics if isinstance(metrics, dict) else {}


def _run_dir(project_dir: Path, run_dir: Path | None) -> Path:
    if run_dir is None:
        latest = latest_run_dir(project_dir)
        if latest is None:
            raise FileNotFoundError(f"No run directories found under {project_dir / 'outputs'}")
        return latest
    run_dir = Path(run_dir)
    if run_dir.is_absolute() or run_dir.exists():
        return run_dir
    return project_dir / run_dir


def evaluate_run_quality(project_dir: Path, run_dir: Path | None = None) -> dict[str, Any]:
    """Evaluate run evidence and write reports/quality_gate.json and .md."""
    project_dir = Path(project_dir).resolve()
    run_path = _run_dir(project_dir, run_dir).resolve()
    manifest = read_json(run_path / "manifest.json", default={}) or {}
    manifest = manifest if isinstance(manifest, dict) else {}
    command = str(manifest.get("command") or "unknown")
    validation = validate_run_manifest(run_path)
    checks = [
        _check(
            "manifest_valid",
            bool(validation.get("valid")),
            "Run manifest validates against files on disk.",
            {"errors": validation.get("errors", []), "warnings": validation.get("warnings", [])},
        ),
        _check(
            "metadata_present",
            (run_path / "metadata.json").exists(),
            "Run metadata file is present.",
            {"path": str(run_path / "metadata.json")},
        ),
    ]

    if command == "run-experiment":
        checks.extend(_experiment_checks(run_path))
    else:
        checks.append(
            _check(
                "command_supported",
                command in {"run-demo", "run-sweep", "run-experiment"},
                "Quality gate applied a manifest-level check for this command.",
                {"command": command},
            )
        )

    failed_checks = [check for check in checks if not check["passed"]]
    result = {
        "schema_version": QUALITY_GATE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "run_dir": str(run_path),
        "run_id": run_path.name,
        "command": command,
        "status": "passed" if not failed_checks else "failed",
        "valid": not failed_checks,
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
        "failed_check_names": [str(check["name"]) for check in failed_checks],
        "checks": checks,
        "policy": "Quality gates check execution evidence completeness only; they do not claim scientific reproduction success.",
    }
    reports = run_path / "reports"
    write_json(reports / "quality_gate.json", result)
    safe_write_text(reports / "quality_gate.md", _render_quality_gate_markdown(result))
    return result


def _experiment_checks(run_dir: Path) -> list[dict[str, Any]]:
    execution = read_json(run_dir / "data" / "execution_result.json", default={}) or {}
    execution = execution if isinstance(execution, dict) else {}
    spec = read_json(run_dir / "configs" / "experiment_spec_snapshot.json", default={}) or {}
    spec = spec if isinstance(spec, dict) else {}
    metrics = _metric_payload(run_dir)
    required_metrics = []
    metric_contract = spec.get("metric_contract", {}) if isinstance(spec.get("metric_contract"), dict) else {}
    if isinstance(metric_contract.get("required_metrics"), list):
        required_metrics = [str(item) for item in metric_contract["required_metrics"]]
    missing_metrics = [metric for metric in required_metrics if metric not in metrics]
    checks = [
        _check(
            "runner_completed",
            execution.get("status") == "completed" and execution.get("exit_code") == 0,
            "Experiment runner completed with exit code 0.",
            {"status": execution.get("status"), "exit_code": execution.get("exit_code")},
        ),
        _check(
            "spec_snapshot_present",
            bool(spec),
            "Experiment spec snapshot is present.",
            {"path": str(run_dir / "configs" / "experiment_spec_snapshot.json")},
        ),
        _check(
            "data_index_snapshot_present",
            (run_dir / "configs" / "data_index_snapshot.json").exists(),
            "Data index snapshot is present.",
            {"path": str(run_dir / "configs" / "data_index_snapshot.json")},
        ),
        _check(
            "environment_snapshot_present",
            (run_dir / "configs" / "environment_snapshot.json").exists(),
            "Environment snapshot is present.",
            {"path": str(run_dir / "configs" / "environment_snapshot.json")},
        ),
        _check(
            "required_metrics_present",
            not missing_metrics,
            "Required template metrics are present in data/metrics.json.",
            {"required_metrics": required_metrics, "missing_metrics": missing_metrics},
        ),
    ]
    return checks


def quality_gate_summaries(project_dir: Path) -> list[dict[str, Any]]:
    """Return quality gate summaries for all run directories, newest last."""
    summaries: list[dict[str, Any]] = []
    for run_dir in reversed(list_run_dirs(Path(project_dir))):
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        manifest = manifest if isinstance(manifest, dict) else {}
        path = run_dir / "reports" / "quality_gate.json"
        gate = read_json(path, default={}) or {}
        gate = gate if isinstance(gate, dict) else {}
        summaries.append(
            {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "command": gate.get("command") if gate else manifest.get("command", "unknown"),
                "present": path.exists(),
                "path": str(path) if path.exists() else None,
                "status": gate.get("status") if gate else "missing",
                "valid": gate.get("valid") if gate else None,
                "failed_check_count": int(gate.get("failed_check_count", 0) or 0) if gate else None,
                "failed_check_names": list(gate.get("failed_check_names", [])) if gate else [],
                "sha256": sha256_file(path) if path.exists() else None,
            }
        )
    return summaries


def evaluate_all_quality_gates(project_dir: Path) -> dict[str, Any]:
    """Evaluate quality gates for every run and write a project summary."""
    project_dir = Path(project_dir).resolve()
    gates = [evaluate_run_quality(project_dir, run_dir) for run_dir in reversed(list_run_dirs(project_dir))]
    failed = [gate for gate in gates if not gate["valid"]]
    summary = {
        "schema_version": QUALITY_GATE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "run_count": len(gates),
        "passed_count": sum(1 for gate in gates if gate["valid"]),
        "failed_count": len(failed),
        "failed_gate_check_names": sorted({name for gate in failed for name in gate.get("failed_check_names", [])}),
        "runs": [
            {
                "run_id": gate["run_id"],
                "run_dir": gate["run_dir"],
                "command": gate["command"],
                "status": gate["status"],
                "valid": gate["valid"],
                "failed_check_count": gate["failed_check_count"],
                "failed_check_names": gate["failed_check_names"],
            }
            for gate in gates
        ],
        "policy": "Quality gate summaries aggregate execution evidence completeness only; they do not claim scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "quality_gate_summary.json", summary)
    safe_write_text(project_dir / "workspace" / "QUALITY_GATE_SUMMARY.md", _render_quality_gate_summary_markdown(summary))
    return summary


def latest_quality_gate_summary(project_dir: Path) -> dict[str, Any]:
    """Return the latest run quality gate summary."""
    summaries = quality_gate_summaries(project_dir)
    if not summaries:
        return {
            "status": "missing",
            "present": False,
            "run_id": None,
            "run_dir": None,
            "failed_check_count": None,
            "sha256": None,
        }
    return summaries[-1]


def latest_experiment_quality_gate_summary(project_dir: Path) -> dict[str, Any]:
    """Return the latest run-experiment quality gate summary."""
    for summary in reversed(quality_gate_summaries(project_dir)):
        if summary.get("command") == "run-experiment":
            return summary
    return {
        "status": "missing",
        "present": False,
        "run_id": None,
        "run_dir": None,
        "command": "run-experiment",
        "failed_check_count": None,
        "failed_check_names": [],
        "sha256": None,
    }


def _render_quality_gate_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Run Quality Gate",
        "",
        f"- run_id: {result['run_id']}",
        f"- command: {result['command']}",
        f"- status: {result['status']}",
        f"- failed_check_count: {result['failed_check_count']}",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in result["checks"]:
        lines.append(f"| {check['name']} | {check['status']} | {check['message']} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _render_quality_gate_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Quality Gate Summary",
        "",
        f"- schema_version: {summary['schema_version']}",
        f"- run_count: {summary['run_count']}",
        f"- passed_count: {summary['passed_count']}",
        f"- failed_count: {summary['failed_count']}",
        f"- failed_gate_check_names: {summary['failed_gate_check_names']}",
        "",
        "| Run | Command | Status | Failed Checks |",
        "| --- | --- | --- | --- |",
    ]
    for run in summary["runs"]:
        lines.append(
            "| {run_id} | {command} | {status} | {failed} |".format(
                run_id=run["run_id"],
                command=run["command"],
                status=run["status"],
                failed=", ".join(run["failed_check_names"]),
            )
        )
    lines.extend(["", "## Policy", "", summary["policy"], ""])
    return "\n".join(lines)
