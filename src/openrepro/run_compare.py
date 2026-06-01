"""Run comparison utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, validate_run_manifest
from .utils import iso_now, read_json, safe_write_text, write_json


def _resolve_run(project_dir: Path, run: Path | None, index: int) -> Path:
    if run is not None:
        candidate = run if run.is_absolute() else project_dir / run
        if candidate.exists():
            return candidate
        return run
    runs = list_run_dirs(project_dir)
    if len(runs) <= index:
        raise ValueError("At least two run directories are required for comparison.")
    return runs[index]


def _run_payload(run_dir: Path) -> dict[str, Any]:
    demo_metrics = read_json(run_dir / "data" / "demo_metrics.json", default=None)
    sweep_results = read_json(run_dir / "data" / "sweep_results.json", default=None)
    metadata = read_json(run_dir / "metadata.json", default={}) or {}
    validation = validate_run_manifest(run_dir)
    metrics = demo_metrics if isinstance(demo_metrics, dict) else {}
    if not metrics and isinstance(sweep_results, dict):
        metrics = {
            "result_count": len(sweep_results.get("results", [])),
            "noise_std_values": sweep_results.get("noise_std_values", []),
            "seeds": sweep_results.get("seeds", []),
        }
    return {
        "run_dir": str(run_dir),
        "command": validation.get("command"),
        "manifest_valid": validation.get("valid"),
        "metrics": metrics,
        "metadata": metadata,
    }


def compare_runs(project_dir: Path, left_run: Path | None = None, right_run: Path | None = None) -> dict[str, Any]:
    """Compare two run directories and write workspace comparison artifacts."""
    project_dir = Path(project_dir)
    left = _resolve_run(project_dir, left_run, 1)
    right = _resolve_run(project_dir, right_run, 0)
    if left == right:
        raise ValueError("Run comparison requires two distinct run directories.")

    left_payload = _run_payload(left)
    right_payload = _run_payload(right)
    metric_keys = sorted(set(left_payload["metrics"]).union(right_payload["metrics"]))
    metric_deltas = []
    for key in metric_keys:
        left_value = left_payload["metrics"].get(key)
        right_value = right_payload["metrics"].get(key)
        delta = None
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            delta = right_value - left_value
        metric_deltas.append({"metric": key, "left": left_value, "right": right_value, "delta": delta})

    comparison = {
        "schema_version": "0.4.0",
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "left": left_payload,
        "right": right_payload,
        "metric_deltas": metric_deltas,
        "policy": "Run comparison reports observed artifact and metric differences only.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "run_comparison.json", comparison)
    lines = [
        "# Run Comparison",
        "",
        f"- left: `{left}`",
        f"- right: `{right}`",
        f"- left_manifest_valid: {left_payload['manifest_valid']}",
        f"- right_manifest_valid: {right_payload['manifest_valid']}",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Left | Right | Delta |",
        "| --- | --- | --- | --- |",
    ]
    for item in metric_deltas:
        lines.append(f"| {item['metric']} | {item['left']} | {item['right']} | {item['delta']} |")
    safe_write_text(workspace / "RUN_COMPARISON.md", "\n".join(lines) + "\n")
    return comparison
