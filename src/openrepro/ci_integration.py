"""GitHub Actions CI scaffolding for OpenRepro projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, read_text, safe_write_text, write_json

CI_INTEGRATION_SCHEMA_VERSION = "1.44.0"
DEFAULT_TEST_COMMAND = "python -m pytest -q"


def init_ci_config(
    project_dir: Path,
    *,
    test_command: str = DEFAULT_TEST_COMMAND,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create a GitHub Actions workflow and local CI summary."""
    project_dir = Path(project_dir)
    workflow_path = project_dir / ".github" / "workflows" / "openrepro-ci.yml"
    written = safe_write_text(workflow_path, _workflow_yaml(test_command), overwrite=overwrite)
    result = {
        "schema_version": CI_INTEGRATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "written" if written else "preserved",
        "workflow_path": str(workflow_path),
        "workflow_relative_path": ".github/workflows/openrepro-ci.yml",
        "test_command": test_command,
        "overwrite": overwrite,
        "sha256": sha256_file(workflow_path) if workflow_path.exists() else None,
        "policy": "CI scaffolding writes a GitHub Actions workflow definition only; it does not claim remote CI has run.",
    }
    _write_summary(project_dir, result)
    return result


def validate_ci_config(project_dir: Path) -> dict[str, Any]:
    """Validate the generated GitHub Actions workflow contains required checks."""
    project_dir = Path(project_dir)
    workflow_path = project_dir / ".github" / "workflows" / "openrepro-ci.yml"
    content = read_text(workflow_path, default="")
    checks = [
        _check("workflow_exists", workflow_path.exists(), "Workflow file exists."),
        _check("runs_pytest", "pytest" in content, "Workflow runs pytest."),
        _check("shows_version", "openrepro --version" in content, "Workflow checks the OpenRepro CLI version."),
        _check("installs_package", "pip install -e" in content, "Workflow installs the package in editable mode."),
        _check("no_claims_remote_success", "CI scaffolding" in content, "Workflow comments avoid claiming remote success."),
    ]
    valid = all(item["passed"] for item in checks)
    result = {
        "schema_version": CI_INTEGRATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "valid": valid,
        "status": "passed" if valid else "failed",
        "workflow_path": str(workflow_path),
        "check_count": len(checks),
        "failed_check_count": sum(1 for item in checks if not item["passed"]),
        "checks": checks,
        "policy": "CI validation checks local workflow configuration only; it does not inspect remote GitHub Actions runs.",
    }
    write_json(project_dir / "workspace" / "ci_validation.json", result)
    safe_write_text(project_dir / "workspace" / "CI_VALIDATION.md", _render_validation_markdown(result))
    return result


def ci_summary(project_dir: Path) -> dict[str, Any]:
    """Return local CI summary without mutating files."""
    from .utils import read_json

    project_dir = Path(project_dir)
    summary_path = project_dir / "workspace" / "ci_summary.json"
    workflow_path = project_dir / ".github" / "workflows" / "openrepro-ci.yml"
    data = read_json(summary_path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": workflow_path.exists(),
        "path": str(summary_path) if summary_path.exists() else None,
        "workflow_path": str(workflow_path) if workflow_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if workflow_path.exists() else "missing"),
        "test_command": data.get("test_command"),
        "sha256": sha256_file(workflow_path) if workflow_path.exists() else None,
    }


def _workflow_yaml(test_command: str) -> str:
    return f"""# OpenRepro CI scaffolding. This file defines checks; it does not claim remote CI success.
name: OpenRepro CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11"]
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}
      - name: Install package
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: CLI smoke check
        run: openrepro --version
      - name: Tests
        run: {test_command}
"""


def _write_summary(project_dir: Path, result: dict[str, Any]) -> None:
    write_json(project_dir / "workspace" / "ci_summary.json", result)
    safe_write_text(project_dir / "workspace" / "CI_SUMMARY.md", _render_summary_markdown(result))


def _check(name: str, passed: bool, message: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "message": message}


def _render_summary_markdown(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CI Summary",
            "",
            f"- schema_version: {result['schema_version']}",
            f"- status: {result['status']}",
            f"- workflow_path: `{result['workflow_relative_path']}`",
            f"- test_command: `{result['test_command']}`",
            f"- sha256: `{result['sha256']}`",
            "",
            "## Policy",
            "",
            result["policy"],
            "",
        ]
    )


def _render_validation_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# CI Validation",
        "",
        f"- status: {result['status']}",
        f"- valid: {result['valid']}",
        f"- failed_check_count: {result['failed_check_count']}",
        "",
        "| Check | Passed | Message |",
        "| --- | --- | --- |",
    ]
    for check in result["checks"]:
        lines.append(f"| {check['name']} | {check['passed']} | {check['message']} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
