"""Experiment-level tracking built from indexed run evidence."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .run_index import generate_run_index
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

EXPERIMENT_TRACKING_SCHEMA_VERSION = "1.38.0"


def generate_experiment_tracking(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write experiment-level tracking artifacts and a static browser."""
    project_dir = Path(project_dir)
    run_index = generate_run_index(project_dir, export_zip=False)
    experiments = [_experiment_record(project_dir, experiment_id, runs) for experiment_id, runs in _group_runs(run_index.get("runs", [])).items()]
    tracking = {
        "schema_version": EXPERIMENT_TRACKING_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if experiments else "empty",
        "experiment_count": len(experiments),
        "run_count": sum(int(experiment.get("run_count", 0) or 0) for experiment in experiments),
        "experiments": experiments,
        "policy": "Experiment tracking summarizes observed workflow runs and artifacts only; it does not claim scientific reproduction success.",
    }
    workspace = project_dir / "workspace"
    reports = project_dir / "reports"
    browser_dir = reports / "experiments"
    tracking["json_path"] = str(workspace / "experiment_tracking.json")
    tracking["markdown_path"] = str(workspace / "EXPERIMENT_TRACKING.md")
    tracking["index_path"] = str(browser_dir / "index.html")
    tracking["manifest_path"] = str(reports / "experiment_tracking_manifest.json")
    tracking["zip_path"] = str(reports / "experiment_tracking.zip") if export_zip else None
    write_json(workspace / "experiment_tracking.json", tracking)
    safe_write_text(workspace / "EXPERIMENT_TRACKING.md", _render_markdown(tracking))
    safe_write_text(browser_dir / "index.html", _render_html(tracking))
    write_json(reports / "experiment_tracking_manifest.json", tracking)
    if export_zip:
        tracking["zip_path"] = str(_export_zip(project_dir, tracking))
        write_json(workspace / "experiment_tracking.json", tracking)
        write_json(reports / "experiment_tracking_manifest.json", tracking)
    return tracking


def experiment_tracking_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing experiment tracking summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "experiment_tracking.json"
    markdown_path = project_dir / "workspace" / "EXPERIMENT_TRACKING.md"
    index_path = project_dir / "reports" / "experiments" / "index.html"
    manifest_path = project_dir / "reports" / "experiment_tracking_manifest.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "index_path": str(index_path) if index_path.exists() else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "experiment_count": int(data.get("experiment_count", 0) or 0),
        "run_count": int(data.get("run_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def list_tracked_experiments(project_dir: Path) -> dict[str, Any]:
    """Return tracked experiments, generating tracking when missing."""
    tracking = _tracking(project_dir)
    return {
        "schema_version": EXPERIMENT_TRACKING_SCHEMA_VERSION,
        "project_dir": str(Path(project_dir)),
        "experiment_count": len(tracking.get("experiments", [])),
        "experiments": tracking.get("experiments", []),
    }


def tracked_experiment(project_dir: Path, experiment_id: str) -> dict[str, Any]:
    """Return one tracked experiment."""
    tracking = _tracking(project_dir)
    for experiment in tracking.get("experiments", []):
        if experiment.get("experiment_id") == experiment_id:
            return experiment
    raise ValueError(f"Experiment not found in tracking: {experiment_id}")


def compare_tracked_experiments(project_dir: Path, left_id: str, right_id: str) -> dict[str, Any]:
    """Compare latest metrics for two tracked experiments."""
    project_dir = Path(project_dir)
    left = tracked_experiment(project_dir, left_id)
    right = tracked_experiment(project_dir, right_id)
    keys = sorted(set(left.get("latest_metrics", {})) | set(right.get("latest_metrics", {})))
    metric_deltas = []
    for key in keys:
        left_value = left.get("latest_metrics", {}).get(key)
        right_value = right.get("latest_metrics", {}).get(key)
        delta = right_value - left_value if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)) else None
        metric_deltas.append({"metric": key, "left": left_value, "right": right_value, "delta": delta, "equal": left_value == right_value})
    result = {
        "schema_version": EXPERIMENT_TRACKING_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "left_experiment_id": left_id,
        "right_experiment_id": right_id,
        "metric_deltas": metric_deltas,
        "all_metrics_equal": all(item["equal"] for item in metric_deltas),
        "policy": "Experiment tracking comparisons report observed latest metric differences only.",
    }
    write_json(project_dir / "workspace" / "experiment_tracking_comparison.json", result)
    safe_write_text(project_dir / "workspace" / "EXPERIMENT_TRACKING_COMPARISON.md", _render_comparison_markdown(result))
    return result


def _tracking(project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    tracking = read_json(project_dir / "workspace" / "experiment_tracking.json", default={}) or {}
    if not isinstance(tracking, dict) or not tracking:
        tracking = generate_experiment_tracking(project_dir)
    return tracking if isinstance(tracking, dict) else {}


def _group_runs(runs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        experiment_id = str(run.get("experiment_id") or run.get("command") or "unassigned")
        grouped.setdefault(experiment_id, []).append(run)
    return dict(sorted(grouped.items()))


def _experiment_record(project_dir: Path, experiment_id: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_runs = sorted(runs, key=lambda run: str(run.get("created_at") or run.get("run_id") or ""), reverse=True)
    latest = sorted_runs[0] if sorted_runs else {}
    spec_path = project_dir / "experiments" / experiment_id / "experiment_spec.json"
    inputs_path = project_dir / "experiments" / experiment_id / "experiment_inputs.json"
    return {
        "experiment_id": experiment_id,
        "status": _experiment_status(sorted_runs),
        "run_count": len(sorted_runs),
        "latest_run_id": latest.get("run_id"),
        "latest_created_at": latest.get("created_at"),
        "latest_quality_gate_status": latest.get("quality_gate_status"),
        "quality_gate_status_counts": _count_by_key(sorted_runs, "quality_gate_status"),
        "commands": _count_by_key(sorted_runs, "command"),
        "templates": _count_by_key(sorted_runs, "template"),
        "metric_keys": sorted({key for run in sorted_runs for key in (run.get("metrics") or {})}),
        "latest_metrics": latest.get("metrics", {}),
        "spec_present": spec_path.exists(),
        "spec_sha256": sha256_file(spec_path) if spec_path.exists() else None,
        "inputs_present": inputs_path.exists(),
        "inputs": read_json(inputs_path, default={}) if inputs_path.exists() else {},
        "runs": sorted_runs,
    }


def _experiment_status(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "empty"
    if any(run.get("quality_gate_status") == "passed" for run in runs):
        return "has_passed_gate"
    if any(run.get("quality_gate_status") for run in runs):
        return "has_runs"
    return "unvalidated"


def _count_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "none")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _export_zip(project_dir: Path, tracking: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "experiment_tracking.zip"
    files = [
        project_dir / "workspace" / "experiment_tracking.json",
        project_dir / "workspace" / "EXPERIMENT_TRACKING.md",
        project_dir / "reports" / "experiments" / "index.html",
        project_dir / "reports" / "experiment_tracking_manifest.json",
    ]
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _render_markdown(tracking: dict[str, Any]) -> str:
    lines = [
        "# Experiment Tracking",
        "",
        f"- schema_version: {tracking['schema_version']}",
        f"- status: {tracking['status']}",
        f"- experiment_count: {tracking['experiment_count']}",
        f"- run_count: {tracking['run_count']}",
        "",
        "| Experiment | Status | Runs | Latest run | Gate | Metrics |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for experiment in tracking["experiments"]:
        metrics = ", ".join(list((experiment.get("latest_metrics") or {}).keys())[:6])
        lines.append(
            "| {experiment_id} | {status} | {runs} | {latest} | {gate} | {metrics} |".format(
                experiment_id=_cell(experiment.get("experiment_id")),
                status=_cell(experiment.get("status")),
                runs=_cell(experiment.get("run_count")),
                latest=_cell(experiment.get("latest_run_id")),
                gate=_cell(experiment.get("latest_quality_gate_status")),
                metrics=_cell(metrics),
            )
        )
    lines.extend(["", "## Policy", "", tracking["policy"], ""])
    return "\n".join(lines)


def _render_comparison_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Experiment Tracking Comparison",
        "",
        f"- left: {result['left_experiment_id']}",
        f"- right: {result['right_experiment_id']}",
        f"- all_metrics_equal: {result['all_metrics_equal']}",
        "",
        "| Metric | Left | Right | Delta | Equal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in result["metric_deltas"]:
        lines.append(f"| {_cell(item['metric'])} | {_cell(item['left'])} | {_cell(item['right'])} | {_cell(item['delta'])} | {_cell(item['equal'])} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _render_html(tracking: dict[str, Any]) -> str:
    rows = "\n".join(_experiment_row(experiment) for experiment in tracking["experiments"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Experiments - {escape(tracking['project_name'])}</title>
  <style>
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: #1f2933; background: #fff; }}
    header {{ padding: 24px 30px; border-bottom: 1px solid #d8dee8; background: #f7f9fc; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px 28px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ color: #667085; line-height: 1.5; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid #d8dee8; }}
    th, td {{ border-bottom: 1px solid #d8dee8; padding: 9px 10px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #f7f9fc; font-size: 12px; text-transform: uppercase; color: #667085; }}
    code {{ font-family: Consolas, monospace; font-size: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>OpenRepro Experiments: {escape(tracking['project_name'])}</h1>
    <p>{escape(tracking['policy'])}</p>
  </header>
  <main>
    <table><thead><tr><th>Experiment</th><th>Status</th><th>Runs</th><th>Latest run</th><th>Gate</th><th>Latest metrics</th></tr></thead><tbody>{rows}</tbody></table>
  </main>
</body>
</html>
"""


def _experiment_row(experiment: dict[str, Any]) -> str:
    metrics = ", ".join(f"{key}={value}" for key, value in list((experiment.get("latest_metrics") or {}).items())[:6])
    return "<tr><td><code>{experiment}</code></td><td>{status}</td><td>{runs}</td><td><code>{latest}</code></td><td>{gate}</td><td>{metrics}</td></tr>".format(
        experiment=_html(experiment.get("experiment_id")),
        status=_html(experiment.get("status")),
        runs=_html(experiment.get("run_count")),
        latest=_html(experiment.get("latest_run_id")),
        gate=_html(experiment.get("latest_quality_gate_status")),
        metrics=_html(metrics),
    )


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _html(value: Any) -> str:
    return escape("" if value is None else str(value))
