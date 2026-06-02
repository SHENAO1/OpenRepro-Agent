"""Repeat experiment execution and experiment-run comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .experiment_runner import run_experiment
from .utils import iso_now, read_json, safe_write_text, write_json

EXPERIMENT_COMPARISON_SCHEMA_VERSION = "0.9.3"


def rerun_experiment(
    project_dir: Path,
    experiment_id: str,
    confirm: bool = False,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run an existing experiment scaffold again."""
    return run_experiment(project_dir, experiment_id=experiment_id, confirm=confirm, timeout_seconds=timeout_seconds)


def _manifest(run_dir: Path) -> dict[str, Any]:
    data = read_json(run_dir / "manifest.json", default={}) or {}
    return data if isinstance(data, dict) else {}


def _experiment_id_for_run(run_dir: Path) -> str | None:
    metadata = _manifest(run_dir).get("metadata", {})
    return str(metadata.get("experiment_id")) if isinstance(metadata, dict) and metadata.get("experiment_id") else None


def _experiment_run_dirs(project_dir: Path, experiment_id: str) -> list[Path]:
    matches: list[Path] = []
    for run_dir in list_run_dirs(project_dir):
        manifest = _manifest(run_dir)
        if manifest.get("command") != "run-experiment":
            continue
        metadata = manifest.get("metadata", {})
        if isinstance(metadata, dict) and metadata.get("experiment_id") == experiment_id:
            matches.append(run_dir)
    return matches


def _hash(path: Path) -> str | None:
    return sha256_file(path) if path.exists() and path.is_file() else None


def _normalized_json_hash(path: Path, ignored_keys: set[str]) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    data = read_json(path, default=None)
    if not isinstance(data, dict):
        return None
    normalized = {key: value for key, value in data.items() if key not in ignored_keys}
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _run_summary(run_dir: Path) -> dict[str, Any]:
    manifest = _manifest(run_dir)
    metadata = manifest.get("metadata", {}) if isinstance(manifest.get("metadata"), dict) else {}
    metrics = read_json(run_dir / "data" / "metrics.json", default={}) or {}
    metrics = metrics if isinstance(metrics, dict) else {}
    environment = read_json(run_dir / "configs" / "environment_snapshot.json", default={}) or {}
    environment = environment if isinstance(environment, dict) else {}
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "experiment_id": metadata.get("experiment_id") or _experiment_id_for_run(run_dir),
        "template": metadata.get("template"),
        "created_at": manifest.get("created_at"),
        "metrics": metrics,
        "hashes": {
            "manifest_sha256": _hash(run_dir / "manifest.json"),
            "runner_sha256": _hash(run_dir / "code" / "runner.py"),
            "inputs_sha256": _hash(run_dir / "configs" / "experiment_inputs_snapshot.json"),
            "spec_sha256": _hash(run_dir / "configs" / "experiment_spec_snapshot.json"),
            "data_index_sha256": _hash(run_dir / "configs" / "data_index_snapshot.json"),
            "normalized_inputs_sha256": _normalized_json_hash(
                run_dir / "configs" / "experiment_inputs_snapshot.json",
                ignored_keys={"created_at", "updated_at"},
            ),
            "environment_sha256": _hash(run_dir / "configs" / "environment_snapshot.json"),
        },
        "repeatability_check": environment.get("repeatability_check"),
    }


def _metric_deltas(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    left_metrics = left.get("metrics", {})
    right_metrics = right.get("metrics", {})
    deltas: list[dict[str, Any]] = []
    for key in sorted(set(left_metrics) | set(right_metrics)):
        left_value = left_metrics.get(key)
        right_value = right_metrics.get(key)
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            delta = right_value - left_value
        else:
            delta = None
        deltas.append(
            {
                "metric": key,
                "left": left_value,
                "right": right_value,
                "delta": delta,
                "equal": left_value == right_value,
            }
        )
    return deltas


def compare_experiments(
    project_dir: Path,
    experiment_id: str,
    left_run: Path | None = None,
    right_run: Path | None = None,
) -> dict[str, Any]:
    """Compare two runs of the same experiment scaffold."""
    project_dir = Path(project_dir)
    runs = _experiment_run_dirs(project_dir, experiment_id)
    if left_run is None or right_run is None:
        if len(runs) < 2:
            raise ValueError(f"At least two run-experiment outputs are required for experiment {experiment_id}.")
        right = runs[0] if right_run is None else Path(right_run)
        left = runs[1] if left_run is None else Path(left_run)
    else:
        left = Path(left_run)
        right = Path(right_run)
    if not left.is_absolute() and not left.exists():
        left = project_dir / left
    if not right.is_absolute() and not right.exists():
        right = project_dir / right

    left_summary = _run_summary(left)
    right_summary = _run_summary(right)
    if left_summary.get("experiment_id") != experiment_id or right_summary.get("experiment_id") != experiment_id:
        raise ValueError("Both runs must belong to the requested experiment id.")

    hash_comparison = {
        key: {
            "left": left_summary["hashes"].get(key),
            "right": right_summary["hashes"].get(key),
            "equal": left_summary["hashes"].get(key) == right_summary["hashes"].get(key),
        }
        for key in sorted(set(left_summary["hashes"]) | set(right_summary["hashes"]))
    }
    metric_deltas = _metric_deltas(left_summary, right_summary)
    warnings: list[str] = []
    spec_comparison = hash_comparison.get("spec_sha256")
    if spec_comparison and not spec_comparison.get("equal"):
        warnings.append("Experiment spec hash differs between compared runs.")
    data_comparison = hash_comparison.get("data_index_sha256")
    if data_comparison and not data_comparison.get("equal"):
        warnings.append("Data index hash differs between compared runs.")
    result = {
        "schema_version": EXPERIMENT_COMPARISON_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "experiment_id": experiment_id,
        "left": left_summary,
        "right": right_summary,
        "metric_deltas": metric_deltas,
        "all_metrics_equal": all(item["equal"] for item in metric_deltas),
        "hash_comparison": hash_comparison,
        "warnings": warnings,
        "policy": "Experiment comparisons report engineering evidence only; they do not claim scientific reproduction success.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "experiment_comparison.json", result)
    safe_write_text(workspace / "EXPERIMENT_COMPARISON.md", _render_comparison_markdown(result))
    return result


def _render_comparison_markdown(result: dict[str, Any]) -> str:
    metric_lines = [
        "| Metric | Left | Right | Delta | Equal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in result["metric_deltas"]:
        metric_lines.append(
            f"| {item['metric']} | {item['left']} | {item['right']} | {item['delta']} | {item['equal']} |"
        )
    hash_lines = [
        "| Hash | Equal |",
        "| --- | --- |",
    ]
    for key, item in result["hash_comparison"].items():
        hash_lines.append(f"| {key} | {item['equal']} |")
    return f"""# Experiment Comparison

- experiment_id: {result['experiment_id']}
- left_run: `{result['left']['run_dir']}`
- right_run: `{result['right']['run_dir']}`
- all_metrics_equal: {result['all_metrics_equal']}
- warnings: {result['warnings']}

## Metric Deltas

{chr(10).join(metric_lines)}

## Hash Comparison

{chr(10).join(hash_lines)}

## Policy

{result['policy']}
"""
