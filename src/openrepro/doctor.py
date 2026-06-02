"""Project and environment doctor checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .config import provider_status
from .utils import iso_now, project_required_dirs, safe_write_text, write_json

DOCTOR_SCHEMA_VERSION = "0.6.2"
REQUIRED_MODULES = ["typer", "yaml", "numpy", "matplotlib", "rich", "pdfplumber"]


def _check(status: str, code: str, message: str) -> dict[str, str]:
    return {"status": status, "code": code, "message": message}


def _dependency_checks() -> list[dict[str, str]]:
    checks = []
    for module in REQUIRED_MODULES:
        if importlib.util.find_spec(module) is None:
            checks.append(_check("fail", "dependency_missing", f"Python module is missing: {module}"))
        else:
            checks.append(_check("ok", "dependency_present", f"Python module is available: {module}"))
    return checks


def _project_checks(project_dir: Path) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    if not project_dir.exists():
        return [_check("fail", "project_missing", f"Project directory not found: {project_dir}")]
    for directory in project_required_dirs(project_dir):
        if directory.exists() and directory.is_dir():
            checks.append(_check("ok", "project_dir_present", f"Directory exists: {directory.name}"))
        else:
            checks.append(_check("fail", "project_dir_missing", f"Directory missing: {directory.name}"))
    config_path = project_dir / "project_config.yaml"
    checks.append(
        _check("ok", "config_present", "project_config.yaml exists")
        if config_path.exists()
        else _check("fail", "config_missing", "project_config.yaml is missing")
    )
    if not (project_dir / "workspace" / "source_index.json").exists():
        checks.append(_check("warn", "source_index_missing", "No source_index.json yet; run ingest first."))
    return checks


def _provider_checks(project_dir: Path) -> list[dict[str, str]]:
    status = provider_status(project_dir)
    provider = str(status.get("default_provider"))
    if provider == "mock":
        return [_check("ok", "provider_mock", "Mock provider is configured.")]
    if status.get("ready_for_real_calls"):
        return [_check("ok", "provider_ready", f"Provider is ready: {provider}")]
    return [_check("warn", "provider_not_ready", f"Provider is configured but not ready: {provider}")]


def run_doctor(project_dir: Path) -> dict[str, Any]:
    """Run environment and project checks and write doctor artifacts."""
    project_dir = Path(project_dir)
    checks = _dependency_checks() + _project_checks(project_dir)
    if project_dir.exists():
        checks.extend(_provider_checks(project_dir))
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    result = {
        "schema_version": DOCTOR_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "healthy": fail_count == 0,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "check_count": len(checks),
        "checks": checks,
        "policy": "Doctor checks environment and workflow readiness only; it does not claim reproduction success.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "doctor.json", result)
    safe_write_text(workspace / "DOCTOR.md", _render_doctor(result))
    return result


def _render_doctor(result: dict[str, Any]) -> str:
    lines = [
        "# Doctor",
        "",
        f"- healthy: {result['healthy']}",
        f"- fail_count: {result['fail_count']}",
        f"- warn_count: {result['warn_count']}",
        f"- check_count: {result['check_count']}",
        "",
        "| Status | Code | Message |",
        "| --- | --- | --- |",
    ]
    for item in result["checks"]:
        lines.append(f"| {item['status']} | {item['code']} | {item['message']} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
