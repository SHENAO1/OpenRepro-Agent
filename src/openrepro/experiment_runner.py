"""Controlled execution for verified experiment scaffolds."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .artifact_manager import REQUIRED_RUN_ARTIFACTS, RunDirectory, validate_run_manifest, write_run_manifest
from .config import load_project_config
from .environment_snapshot import build_environment_snapshot
from .experiment_inputs import validate_experiment_inputs
from .experiment_spec import validate_experiment_spec
from .experiment_templates import normalize_artifact_paths
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

EXPERIMENT_RUN_SCHEMA_VERSION = "0.9.2"


def _experiment_dir(project_dir: Path, experiment_id: str) -> Path:
    return project_dir / "experiments" / experiment_id


def _select_runner(exp_dir: Path) -> Path:
    runner = exp_dir / "runner.py"
    if runner.exists():
        return runner
    return exp_dir / "runner_stub.py"


def _load_expected_artifacts(exp_dir: Path) -> dict[str, Any]:
    expected = read_json(exp_dir / "expected_artifacts.json", default={}) or {}
    return expected if isinstance(expected, dict) else {}


def _required_artifacts_for_run(expected_artifacts: dict[str, Any]) -> list[str]:
    base = REQUIRED_RUN_ARTIFACTS.get("run-experiment", [])
    is_template_schema = expected_artifacts.get("schema_version") == EXPERIMENT_RUN_SCHEMA_VERSION
    is_template_scaffold = bool(expected_artifacts.get("template"))
    declared = (
        normalize_artifact_paths(expected_artifacts.get("required"))
        if is_template_schema or is_template_scaffold
        else []
    )
    return normalize_artifact_paths(list(base) + declared)


def run_experiment(
    project_dir: Path,
    experiment_id: str,
    confirm: bool = False,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run a verified experiment scaffold and write execution evidence."""
    project_dir = Path(project_dir).resolve()
    if not confirm:
        raise ValueError("run-experiment requires --confirm.")
    exp_dir = _experiment_dir(project_dir, experiment_id)
    if not exp_dir.exists():
        raise FileNotFoundError(f"Experiment directory not found: {exp_dir}")
    config_path = exp_dir / "experiment_config.json"
    config = read_json(config_path, default=None)
    if not isinstance(config, dict):
        raise ValueError(f"Experiment config not found or invalid: {config_path}")
    if config.get("status") != "verified_inputs_ready" or not config.get("runnable"):
        raise ValueError("Experiment must be verified_inputs_ready and runnable before execution.")

    runner = _select_runner(exp_dir)
    if not runner.exists():
        raise FileNotFoundError(f"Experiment runner not found: {runner}")

    expected_artifacts = _load_expected_artifacts(exp_dir)
    required_artifacts = _required_artifacts_for_run(expected_artifacts)
    template = str(config.get("template") or expected_artifacts.get("template") or "basic")
    experiment_inputs_path = exp_dir / "experiment_inputs.json"
    input_validation = validate_experiment_inputs(project_dir, experiment_id)
    spec_validation = validate_experiment_spec(project_dir, experiment_id)
    if not spec_validation["valid"]:
        raise ValueError(f"Experiment spec validation failed: {spec_validation['errors']}")
    experiment_inputs = read_json(experiment_inputs_path, default={}) or {}
    experiment_inputs = experiment_inputs if isinstance(experiment_inputs, dict) else {}
    input_completeness = experiment_inputs.get("input_completeness", {}) if experiment_inputs else {}

    project_config = load_project_config(project_dir)
    project_name = str(project_config.get("project_name", project_dir.name))
    run_dirs = RunDirectory.create(project_dir, f"{project_name}_{experiment_id}")
    started_at = iso_now()
    env = os.environ.copy()
    env["OPENREPRO_RUN_DIR"] = str(run_dirs.root)
    env["OPENREPRO_EXPERIMENT_ID"] = experiment_id
    env["OPENREPRO_EXPERIMENT_TEMPLATE"] = template
    env["OPENREPRO_EXPERIMENT_INPUTS"] = str(experiment_inputs_path)
    completed = subprocess.run(
        [sys.executable, str(runner.name)],
        cwd=exp_dir,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
        env=env,
    )
    completed_at = iso_now()
    status = "completed" if completed.returncode == 0 else "failed"

    log_text = f"""Controlled Experiment Run

started_at: {started_at}
completed_at: {completed_at}
experiment_id: {experiment_id}
template: {template}
input_completeness: {input_completeness.get("status", "missing")}
runner: {runner}
exit_code: {completed.returncode}
status: {status}

## stdout

{completed.stdout or ""}

## stderr

{completed.stderr or ""}
"""
    safe_write_text(run_dirs.logs / "run.log", log_text)
    execution_result = {
        "schema_version": EXPERIMENT_RUN_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "template": template,
        "runner": str(runner),
        "exit_code": completed.returncode,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "expected_artifacts": {
            "path": str(exp_dir / "expected_artifacts.json") if expected_artifacts else None,
            "required": required_artifacts,
            "optional": normalize_artifact_paths(expected_artifacts.get("optional")),
        },
        "experiment_inputs": {
            "path": str(experiment_inputs_path) if experiment_inputs else None,
            "input_completeness": input_completeness or {"status": "missing"},
        },
        "input_validation": input_validation,
        "policy": "Controlled experiment execution records evidence only; it does not claim paper reproduction success.",
    }
    write_json(run_dirs.data / "execution_result.json", execution_result)
    write_json(run_dirs.configs / "experiment_config_snapshot.json", config)
    write_json(
        run_dirs.configs / "experiment_inputs_snapshot.json",
        experiment_inputs
        or {
            "schema_version": EXPERIMENT_RUN_SCHEMA_VERSION,
            "experiment_id": experiment_id,
            "template": template,
            "input_completeness": {"status": "missing"},
        },
    )
    spec = read_json(exp_dir / "experiment_spec.json", default={}) or {}
    write_json(run_dirs.configs / "experiment_spec_snapshot.json", spec if isinstance(spec, dict) else {})
    environment_snapshot = build_environment_snapshot(project_dir, exp_dir, run_dirs.root, runner, experiment_id, template)
    write_json(run_dirs.configs / "environment_snapshot.json", environment_snapshot)
    shutil.copy2(runner, run_dirs.code / "runner.py")
    report = f"""# Experiment Run Report

- experiment_id: {experiment_id}
- status: {status}
- exit_code: {completed.returncode}
- template: {template}
- runner: `{runner}`
- verified_candidates_path: `{config.get('verified_candidates_path')}`
- experiment_inputs_path: `{experiment_inputs_path if experiment_inputs else None}`
- experiment_spec_path: `{exp_dir / 'experiment_spec.json'}`
- experiment_spec_sha256: {spec_validation.get('spec_sha256')}
- input_completeness: {input_completeness.get('status', 'missing')}
- missing_required_inputs: {input_completeness.get('missing', [])}
- input_warning: {input_completeness.get('warning')}
- environment_snapshot: `configs/environment_snapshot.json`
- random_seed: {environment_snapshot.get('random_seed')}
- repeatability_check: {environment_snapshot.get('repeatability_check', {}).get('status')}
- required_artifacts: {len(required_artifacts)}

## Policy

This report records controlled execution evidence only. It does not claim paper reproduction success.
"""
    safe_write_text(run_dirs.reports / "experiment_report.md", report)
    metadata = {
        "schema_version": EXPERIMENT_RUN_SCHEMA_VERSION,
        "project_dir": str(project_dir),
        "experiment_id": experiment_id,
        "experiment_dir": str(exp_dir),
        "template": template,
        "run_dir": str(run_dirs.root),
        "status": status,
        "exit_code": completed.returncode,
        "created_at": completed_at,
        "artifacts": {
            "log": relpath(run_dirs.logs / "run.log", run_dirs.root),
            "execution_result": relpath(run_dirs.data / "execution_result.json", run_dirs.root),
            "report": relpath(run_dirs.reports / "experiment_report.md", run_dirs.root),
        },
        "expected_artifacts": {
            "path": str(exp_dir / "expected_artifacts.json") if expected_artifacts else None,
            "required": required_artifacts,
            "optional": normalize_artifact_paths(expected_artifacts.get("optional")),
        },
        "experiment_inputs": {
            "path": str(experiment_inputs_path) if experiment_inputs else None,
            "snapshot": relpath(run_dirs.configs / "experiment_inputs_snapshot.json", run_dirs.root),
            "input_completeness": input_completeness or {"status": "missing"},
            "validation": input_validation,
        },
        "experiment_spec": {
            "path": str(exp_dir / "experiment_spec.json"),
            "snapshot": relpath(run_dirs.configs / "experiment_spec_snapshot.json", run_dirs.root),
            "validation": spec_validation,
            "sha256": spec_validation.get("spec_sha256"),
        },
        "environment_snapshot": {
            "snapshot": relpath(run_dirs.configs / "environment_snapshot.json", run_dirs.root),
            "random_seed": environment_snapshot.get("random_seed"),
            "runner_sha256": (environment_snapshot.get("runner") or {}).get("sha256"),
            "repeatability_check": environment_snapshot.get("repeatability_check"),
        },
        "policy": "Run artifacts are execution evidence, not scientific reproduction claims.",
    }
    metadata["manifest"] = relpath(run_dirs.root / "manifest.json", run_dirs.root)
    write_json(run_dirs.root / "metadata.json", metadata)
    write_run_manifest(
        run_dirs.root,
        "run-experiment",
        required_artifacts=required_artifacts,
        extra_metadata={
            "experiment_id": experiment_id,
            "template": template,
            "status": status,
            "exit_code": completed.returncode,
            "expected_artifact_count": len(required_artifacts),
            "input_completeness": input_completeness.get("status", "missing"),
            "repeatability_check": environment_snapshot.get("repeatability_check", {}).get("status"),
            "experiment_spec_sha256": spec_validation.get("spec_sha256"),
        },
    )
    artifact_validation = validate_run_manifest(run_dirs.root, required_artifacts=required_artifacts)
    metadata["artifact_validation"] = {
        "valid": artifact_validation["valid"],
        "checked_artifacts": artifact_validation["checked_artifacts"],
        "errors": artifact_validation["errors"],
    }
    if status == "completed" and not artifact_validation["valid"]:
        errors = "; ".join(artifact_validation["errors"])
        raise ValueError(f"Experiment artifact validation failed: {errors}")
    return metadata
