"""Environment and repeatability snapshots for experiment runs."""

from __future__ import annotations

import importlib.metadata
import platform
import sys
from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .utils import iso_now, read_json

ENVIRONMENT_SCHEMA_VERSION = "0.9.1"
DEPENDENCY_PACKAGES = {
    "typer": "typer",
    "pyyaml": "PyYAML",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "rich": "rich",
    "pdfplumber": "pdfplumber",
}


def _dependency_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name, package in DEPENDENCY_PACKAGES.items():
        try:
            versions[name] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _stable_metric_items(metrics: dict[str, Any]) -> dict[str, Any]:
    ignored = {"generated_at", "input_completeness"}
    return {key: value for key, value in metrics.items() if key not in ignored}


def _previous_same_seed_run(project_dir: Path, current_run_dir: Path, experiment_id: str, seed: Any) -> Path | None:
    if seed is None:
        return None
    for run_dir in list_run_dirs(project_dir):
        if run_dir == current_run_dir:
            continue
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        metadata = manifest.get("metadata", {}) if isinstance(manifest, dict) else {}
        if metadata.get("experiment_id") != experiment_id:
            continue
        metrics = read_json(run_dir / "data" / "metrics.json", default={}) or {}
        if isinstance(metrics, dict) and metrics.get("seed") == seed:
            return run_dir
    return None


def _repeatability_check(
    project_dir: Path,
    run_dir: Path,
    experiment_id: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    seed = metrics.get("seed")
    if seed is None:
        return {"status": "no_seed_recorded", "seed": None}
    previous = _previous_same_seed_run(project_dir, run_dir, experiment_id, seed)
    if previous is None:
        return {"status": "no_prior_same_seed_run", "seed": seed}

    previous_metrics = read_json(previous / "data" / "metrics.json", default={}) or {}
    current_stable = _stable_metric_items(metrics)
    previous_stable = _stable_metric_items(previous_metrics if isinstance(previous_metrics, dict) else {})
    changed = {
        key: {"previous": previous_stable.get(key), "current": current_stable.get(key)}
        for key in sorted(set(previous_stable) | set(current_stable))
        if previous_stable.get(key) != current_stable.get(key)
    }
    return {
        "status": "matched" if not changed else "changed",
        "seed": seed,
        "previous_run_dir": str(previous),
        "changed_fields": changed,
    }


def build_environment_snapshot(
    project_dir: Path,
    exp_dir: Path,
    run_dir: Path,
    runner: Path,
    experiment_id: str,
    template: str,
) -> dict[str, Any]:
    """Build an environment snapshot for an experiment run."""
    metrics = read_json(run_dir / "data" / "metrics.json", default={}) or {}
    metrics = metrics if isinstance(metrics, dict) else {}
    inputs = read_json(exp_dir / "experiment_inputs.json", default={}) or {}
    inputs = inputs if isinstance(inputs, dict) else {}
    parameter_values = inputs.get("parameter_values", {}) if inputs else {}
    seed = metrics.get("seed", parameter_values.get("seed") if isinstance(parameter_values, dict) else None)
    return {
        "schema_version": ENVIRONMENT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "experiment_id": experiment_id,
        "template": template,
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
        "random_seed": seed,
        "runner": {
            "path": str(runner),
            "sha256": sha256_file(runner) if runner.exists() else None,
        },
        "experiment_inputs": {
            "path": str(exp_dir / "experiment_inputs.json") if inputs else None,
            "input_completeness": inputs.get("input_completeness", {}) if inputs else {"status": "missing"},
        },
        "repeatability_check": _repeatability_check(project_dir, run_dir, experiment_id, metrics),
        "policy": "Environment snapshots record execution context only; they do not claim scientific reproducibility.",
    }
