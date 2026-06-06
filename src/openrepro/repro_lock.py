"""Project reproducibility lockfile generation and validation."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .data_registry import data_index_summary, validate_data_index
from .environment_snapshot import DEPENDENCY_PACKAGES
from .utils import iso_now, read_json, safe_write_text, write_json

REPRO_LOCK_SCHEMA_VERSION = "1.29.0"
LOCKFILE_NAME = "openrepro.lock.json"


def generate_repro_lock(project_dir: Path) -> dict[str, Any]:
    """Write openrepro.lock.json and workspace/REPRO_LOCK.md."""
    project_dir = Path(project_dir)
    data_validation = validate_data_index(project_dir)
    lock = build_repro_lock(project_dir, data_validation=data_validation)
    write_json(project_dir / LOCKFILE_NAME, lock)
    safe_write_text(project_dir / "workspace" / "REPRO_LOCK.md", _render_lock_markdown(lock))
    return lock


def build_repro_lock(project_dir: Path, data_validation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the lockfile payload without writing it."""
    project_dir = Path(project_dir)
    data_summary = data_index_summary(project_dir)
    data_validation = data_validation or read_json(project_dir / "workspace" / "data_validation.json", default={}) or {}
    experiments = _experiment_locks(project_dir)
    status = "locked"
    if int(data_summary.get("invalid_count", 0) or 0) > 0:
        status = "data_invalid"
    return {
        "schema_version": REPRO_LOCK_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "config": _file_lock(project_dir / "project_config.yaml", project_dir),
        "data": {
            "validation_valid": data_validation.get("valid"),
            "registered_count": data_summary.get("registered_count", 0),
            "invalid_count": data_summary.get("invalid_count", 0),
            "sources": [
                {
                    "data_id": source.get("data_id"),
                    "role": source.get("role"),
                    "path": source.get("registered_path"),
                    "path_mode": source.get("path_mode"),
                    "size_bytes": source.get("size_bytes"),
                    "sha256": source.get("sha256"),
                    "status": source.get("status"),
                }
                for source in data_summary.get("sources", [])
            ],
        },
        "environment": _environment_lock(),
        "experiments": experiments,
        "experiment_count": len(experiments),
        "policy": "Repro locks capture file hashes and environment metadata only; they do not verify scientific correctness.",
    }


def validate_repro_lock(project_dir: Path, strict_dependencies: bool = False) -> dict[str, Any]:
    """Validate openrepro.lock.json against the current workspace."""
    project_dir = Path(project_dir)
    lock_path = project_dir / LOCKFILE_NAME
    lock = read_json(lock_path, default=None)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    if not isinstance(lock, dict):
        result = {
            "schema_version": REPRO_LOCK_SCHEMA_VERSION,
            "created_at": iso_now(),
            "project_name": project_dir.name,
            "project_dir": str(project_dir),
            "valid": False,
            "errors": [f"Lockfile not found or invalid: {lock_path}"],
            "warnings": [],
            "checks": [],
            "policy": "Lock validation checks engineering reproducibility metadata only.",
        }
        _write_validation(project_dir, result)
        return result

    _check_file_lock(project_dir, lock.get("config", {}), "config", errors, checks)
    _check_data_locks(project_dir, lock.get("data", {}), errors, checks)
    _check_experiment_locks(project_dir, lock.get("experiments", []), errors, checks)
    _check_environment_lock(lock.get("environment", {}), strict_dependencies, errors, warnings, checks)
    result = {
        "schema_version": REPRO_LOCK_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "lock_schema_version": lock.get("schema_version"),
        "valid": not errors,
        "strict_dependencies": strict_dependencies,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "policy": "Lock validation checks file hashes, data provenance, experiment contracts, and environment metadata only.",
    }
    _write_validation(project_dir, result)
    return result


def repro_lock_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing lockfile summary without mutating files."""
    project_dir = Path(project_dir)
    lock_path = project_dir / LOCKFILE_NAME
    validation_path = project_dir / "workspace" / "repro_lock_validation.json"
    lock = read_json(lock_path, default={}) or {}
    lock = lock if isinstance(lock, dict) else {}
    validation = read_json(validation_path, default={}) or {}
    validation = validation if isinstance(validation, dict) else {}
    return {
        "present": lock_path.exists(),
        "path": str(lock_path) if lock_path.exists() else None,
        "schema_version": lock.get("schema_version"),
        "status": lock.get("status", "present" if lock_path.exists() else "missing"),
        "registered_data_count": (lock.get("data", {}) or {}).get("registered_count") if isinstance(lock.get("data"), dict) else 0,
        "experiment_count": int(lock.get("experiment_count", 0) or 0),
        "validation_present": validation_path.exists(),
        "validation_valid": validation.get("valid") if validation else None,
        "validation_error_count": int(validation.get("error_count", 0) or 0),
        "sha256": sha256_file(lock_path) if lock_path.exists() else None,
    }


def _write_validation(project_dir: Path, result: dict[str, Any]) -> None:
    write_json(project_dir / "workspace" / "repro_lock_validation.json", result)
    safe_write_text(project_dir / "workspace" / "REPRO_LOCK_VALIDATION.md", _render_validation_markdown(result))


def _environment_lock() -> dict[str, Any]:
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "dependencies": _dependency_versions(),
    }


def _dependency_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name, package in DEPENDENCY_PACKAGES.items():
        try:
            versions[name] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _experiment_locks(project_dir: Path) -> list[dict[str, Any]]:
    experiments_dir = project_dir / "experiments"
    if not experiments_dir.exists():
        return []
    locks: list[dict[str, Any]] = []
    for exp_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
        locks.append(
            {
                "experiment_id": exp_dir.name,
                "runner": _file_lock(exp_dir / "runner.py", project_dir),
                "spec": _file_lock(exp_dir / "experiment_spec.json", project_dir),
                "inputs": _file_lock(exp_dir / "experiment_inputs.json", project_dir),
                "expected_artifacts": _file_lock(exp_dir / "expected_artifacts.json", project_dir),
            }
        )
    return locks


def _file_lock(path: Path, project_dir: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return {
        "path": _relative(path, project_dir),
        "present": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": sha256_file(path) if exists else None,
    }


def _relative(path: Path, project_dir: Path) -> str:
    try:
        return str(path.relative_to(project_dir)).replace("\\", "/")
    except ValueError:
        return str(path)


def _check_file_lock(
    project_dir: Path,
    locked: Any,
    label: str,
    errors: list[str],
    checks: list[dict[str, Any]],
) -> None:
    if not isinstance(locked, dict):
        errors.append(f"Missing lock record for {label}.")
        checks.append({"name": label, "passed": False, "reason": "missing_lock_record"})
        return
    path = project_dir / str(locked.get("path") or "")
    present = path.exists() and path.is_file()
    current_hash = sha256_file(path) if present else None
    passed = present == bool(locked.get("present")) and current_hash == locked.get("sha256")
    if not passed:
        errors.append(f"Locked file changed or is missing: {label} ({locked.get('path')})")
    checks.append(
        {
            "name": label,
            "path": locked.get("path"),
            "passed": passed,
            "locked_sha256": locked.get("sha256"),
            "current_sha256": current_hash,
        }
    )


def _check_data_locks(project_dir: Path, data: Any, errors: list[str], checks: list[dict[str, Any]]) -> None:
    if not isinstance(data, dict):
        errors.append("Missing data lock section.")
        checks.append({"name": "data", "passed": False, "reason": "missing_lock_section"})
        return
    current = {source.get("data_id"): source for source in data_index_summary(project_dir).get("sources", [])}
    for locked in data.get("sources", []) if isinstance(data.get("sources"), list) else []:
        data_id = locked.get("data_id")
        current_source = current.get(data_id)
        passed = bool(current_source) and current_source.get("sha256") == locked.get("sha256") and current_source.get("status") == "current"
        if not passed:
            errors.append(f"Registered data changed or is invalid: {data_id}")
        checks.append(
            {
                "name": f"data:{data_id}",
                "passed": passed,
                "locked_sha256": locked.get("sha256"),
                "current_sha256": current_source.get("current_sha256") if current_source else None,
                "current_status": current_source.get("status") if current_source else "missing",
            }
        )


def _check_experiment_locks(project_dir: Path, experiments: Any, errors: list[str], checks: list[dict[str, Any]]) -> None:
    if not isinstance(experiments, list):
        errors.append("Missing experiment lock section.")
        checks.append({"name": "experiments", "passed": False, "reason": "missing_lock_section"})
        return
    for experiment in experiments:
        if not isinstance(experiment, dict):
            continue
        experiment_id = str(experiment.get("experiment_id") or "unknown")
        for key in ["runner", "spec", "inputs", "expected_artifacts"]:
            _check_file_lock(project_dir, experiment.get(key, {}), f"experiment:{experiment_id}:{key}", errors, checks)


def _check_environment_lock(
    environment: Any,
    strict_dependencies: bool,
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, Any]],
) -> None:
    if not isinstance(environment, dict):
        errors.append("Missing environment lock section.")
        checks.append({"name": "environment", "passed": False, "reason": "missing_lock_section"})
        return
    current = _environment_lock()
    python_match = (environment.get("python") or {}).get("version") == current["python"]["version"]
    checks.append(
        {
            "name": "environment:python_version",
            "passed": python_match,
            "locked": (environment.get("python") or {}).get("version"),
            "current": current["python"]["version"],
        }
    )
    if not python_match:
        message = "Python version differs from lockfile."
        (errors if strict_dependencies else warnings).append(message)
    locked_deps = environment.get("dependencies", {}) if isinstance(environment.get("dependencies"), dict) else {}
    current_deps = current["dependencies"]
    for name in sorted(set(locked_deps) | set(current_deps)):
        passed = locked_deps.get(name) == current_deps.get(name)
        checks.append(
            {
                "name": f"dependency:{name}",
                "passed": passed,
                "locked": locked_deps.get(name),
                "current": current_deps.get(name),
            }
        )
        if not passed:
            message = f"Dependency version differs from lockfile: {name}"
            (errors if strict_dependencies else warnings).append(message)


def _render_lock_markdown(lock: dict[str, Any]) -> str:
    lines = [
        "# Repro Lock",
        "",
        f"- Project: `{lock['project_name']}`",
        f"- Status: `{lock['status']}`",
        f"- Registered data: {lock['data']['registered_count']}",
        f"- Experiments: {lock['experiment_count']}",
        "",
        "## Data",
        "",
        "| Data ID | Role | Status | SHA-256 |",
        "| --- | --- | --- | --- |",
    ]
    for source in lock["data"]["sources"]:
        lines.append(f"| {source.get('data_id')} | {source.get('role')} | {source.get('status')} | `{source.get('sha256')}` |")
    lines.extend(["", "## Dependencies", "", "```json", json.dumps(lock["environment"]["dependencies"], indent=2), "```"])
    lines.extend(["", "## Policy", "", lock["policy"], ""])
    return "\n".join(lines)


def _render_validation_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Repro Lock Validation",
        "",
        f"- valid: {result['valid']}",
        f"- errors: {len(result.get('errors', []))}",
        f"- warnings: {len(result.get('warnings', []))}",
        "",
        "## Checks",
        "",
        "| Check | Passed | Details |",
        "| --- | --- | --- |",
    ]
    for check in result.get("checks", []):
        detail = check.get("path") or check.get("current_status") or check.get("current") or ""
        lines.append(f"| {check.get('name')} | {check.get('passed')} | `{detail}` |")
    if result.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in result["errors"])
    if result.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in result["warnings"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
