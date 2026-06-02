"""Controlled execution for verified experiment scaffolds."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .artifact_manager import RunDirectory, write_run_manifest
from .config import load_project_config
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

EXPERIMENT_RUN_SCHEMA_VERSION = "0.7.0"


def _experiment_dir(project_dir: Path, experiment_id: str) -> Path:
    return project_dir / "experiments" / experiment_id


def _select_runner(exp_dir: Path) -> Path:
    runner = exp_dir / "runner.py"
    if runner.exists():
        return runner
    return exp_dir / "runner_stub.py"


def run_experiment(
    project_dir: Path,
    experiment_id: str,
    confirm: bool = False,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run a verified experiment scaffold and write execution evidence."""
    project_dir = Path(project_dir)
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

    project_config = load_project_config(project_dir)
    project_name = str(project_config.get("project_name", project_dir.name))
    run_dirs = RunDirectory.create(project_dir, f"{project_name}_{experiment_id}")
    started_at = iso_now()
    completed = subprocess.run(
        [sys.executable, str(runner.name)],
        cwd=exp_dir,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    completed_at = iso_now()
    status = "completed" if completed.returncode == 0 else "failed"

    log_text = f"""Controlled Experiment Run

started_at: {started_at}
completed_at: {completed_at}
experiment_id: {experiment_id}
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
        "runner": str(runner),
        "exit_code": completed.returncode,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "policy": "Controlled experiment execution records evidence only; it does not claim paper reproduction success.",
    }
    write_json(run_dirs.data / "execution_result.json", execution_result)
    write_json(run_dirs.configs / "experiment_config_snapshot.json", config)
    shutil.copy2(runner, run_dirs.code / "runner.py")
    report = f"""# Experiment Run Report

- experiment_id: {experiment_id}
- status: {status}
- exit_code: {completed.returncode}
- runner: `{runner}`
- verified_candidates_path: `{config.get('verified_candidates_path')}`

## Policy

This report records controlled execution evidence only. It does not claim paper reproduction success.
"""
    safe_write_text(run_dirs.reports / "experiment_report.md", report)
    metadata = {
        "schema_version": EXPERIMENT_RUN_SCHEMA_VERSION,
        "project_dir": str(project_dir),
        "experiment_id": experiment_id,
        "experiment_dir": str(exp_dir),
        "run_dir": str(run_dirs.root),
        "status": status,
        "exit_code": completed.returncode,
        "created_at": completed_at,
        "artifacts": {
            "log": relpath(run_dirs.logs / "run.log", run_dirs.root),
            "execution_result": relpath(run_dirs.data / "execution_result.json", run_dirs.root),
            "report": relpath(run_dirs.reports / "experiment_report.md", run_dirs.root),
        },
        "policy": "Run artifacts are execution evidence, not scientific reproduction claims.",
    }
    metadata["manifest"] = relpath(run_dirs.root / "manifest.json", run_dirs.root)
    write_json(run_dirs.root / "metadata.json", metadata)
    write_run_manifest(
        run_dirs.root,
        "run-experiment",
        extra_metadata={"experiment_id": experiment_id, "status": status, "exit_code": completed.returncode},
    )
    return metadata
