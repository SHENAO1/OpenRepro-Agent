"""Run index and static run explorer generation."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import list_run_dirs, sha256_file, validate_run_manifest
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

RUN_INDEX_SCHEMA_VERSION = "1.28.0"


def generate_run_index(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write run index artifacts and a static run explorer."""
    project_dir = Path(project_dir)
    runs = [_run_record(project_dir, run_dir) for run_dir in list_run_dirs(project_dir)]
    index = {
        "schema_version": RUN_INDEX_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if runs else "empty",
        "run_count": len(runs),
        "valid_manifest_count": sum(1 for run in runs if run.get("manifest_valid")),
        "quality_gate_passed_count": sum(1 for run in runs if run.get("quality_gate_status") == "passed"),
        "commands": _count_by_key(runs, "command"),
        "experiments": _count_by_key(runs, "experiment_id"),
        "runs": runs,
        "policy": "Run indexes summarize observed engineering artifacts only; they do not claim scientific reproduction success.",
    }
    workspace = project_dir / "workspace"
    reports = project_dir / "reports"
    explorer_dir = reports / "run_explorer"
    index_path = workspace / "run_index.json"
    markdown_path = workspace / "RUN_INDEX.md"
    explorer_path = explorer_dir / "index.html"
    manifest_path = reports / "run_explorer_manifest.json"
    index["index_path"] = str(index_path)
    index["markdown_path"] = str(markdown_path)
    index["explorer_path"] = str(explorer_path)
    index["manifest_path"] = str(manifest_path)
    index["zip_path"] = str(reports / "run_explorer.zip") if export_zip else None
    write_json(index_path, index)
    safe_write_text(markdown_path, _render_markdown(index))
    safe_write_text(explorer_path, _render_html(index))
    write_json(manifest_path, index)
    if export_zip:
        index["zip_path"] = str(_export_zip(project_dir, index))
        write_json(index_path, index)
        write_json(manifest_path, index)
    return index


def run_index_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing run index summary without mutating files."""
    project_dir = Path(project_dir)
    index_path = project_dir / "workspace" / "run_index.json"
    markdown_path = project_dir / "workspace" / "RUN_INDEX.md"
    explorer_path = project_dir / "reports" / "run_explorer" / "index.html"
    manifest_path = project_dir / "reports" / "run_explorer_manifest.json"
    zip_path = project_dir / "reports" / "run_explorer.zip"
    data = read_json(index_path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": index_path.exists(),
        "path": str(index_path) if index_path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "explorer_path": str(explorer_path) if explorer_path.exists() else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if index_path.exists() else "missing"),
        "run_count": int(data.get("run_count", 0) or 0),
        "valid_manifest_count": int(data.get("valid_manifest_count", 0) or 0),
        "quality_gate_passed_count": int(data.get("quality_gate_passed_count", 0) or 0),
        "sha256": sha256_file(index_path) if index_path.exists() else None,
    }


def indexed_run(project_dir: Path, run_id: str) -> dict[str, Any]:
    """Return one indexed run record, generating a fresh index if needed."""
    index = generate_run_index(project_dir)
    for run in index["runs"]:
        if run["run_id"] == run_id or Path(run["run_dir"]).name == run_id:
            return run
    raise ValueError(f"Run not found in index: {run_id}")


def compare_indexed_runs(project_dir: Path, left_run_id: str, right_run_id: str) -> dict[str, Any]:
    """Compare two indexed run records and write comparison artifacts."""
    project_dir = Path(project_dir)
    index = generate_run_index(project_dir)
    left = _find_run(index, left_run_id)
    right = _find_run(index, right_run_id)
    if left["run_id"] == right["run_id"]:
        raise ValueError("Run index comparison requires two distinct run ids.")
    metric_keys = sorted(set(left.get("metrics", {})) | set(right.get("metrics", {})))
    metric_deltas = []
    for key in metric_keys:
        left_value = left.get("metrics", {}).get(key)
        right_value = right.get("metrics", {}).get(key)
        delta = right_value - left_value if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)) else None
        metric_deltas.append(
            {
                "metric": key,
                "left": left_value,
                "right": right_value,
                "delta": delta,
                "equal": left_value == right_value,
            }
        )
    result = {
        "schema_version": RUN_INDEX_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "left": left,
        "right": right,
        "metric_deltas": metric_deltas,
        "all_metrics_equal": all(item["equal"] for item in metric_deltas),
        "manifest_valid_match": left.get("manifest_valid") == right.get("manifest_valid"),
        "quality_gate_status_match": left.get("quality_gate_status") == right.get("quality_gate_status"),
        "policy": "Run index comparison reports observed artifact and metric differences only.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "run_index_comparison.json", result)
    safe_write_text(workspace / "RUN_INDEX_COMPARISON.md", _render_comparison_markdown(result))
    return result


def _find_run(index: dict[str, Any], run_id: str) -> dict[str, Any]:
    for run in index.get("runs", []):
        if run.get("run_id") == run_id:
            return run
    raise ValueError(f"Run not found in index: {run_id}")


def _run_record(project_dir: Path, run_dir: Path) -> dict[str, Any]:
    validation = validate_run_manifest(run_dir)
    manifest = read_json(run_dir / "manifest.json", default={}) or {}
    manifest = manifest if isinstance(manifest, dict) else {}
    metadata = manifest.get("metadata", {}) if isinstance(manifest.get("metadata"), dict) else {}
    quality_gate = read_json(run_dir / "reports" / "quality_gate.json", default={}) or {}
    quality_gate = quality_gate if isinstance(quality_gate, dict) else {}
    execution = read_json(run_dir / "data" / "execution_result.json", default={}) or {}
    execution = execution if isinstance(execution, dict) else {}
    metrics = _metrics(run_dir)
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "relative_path": relpath(run_dir, project_dir).replace("\\", "/"),
        "command": validation.get("command") or manifest.get("command"),
        "created_at": manifest.get("created_at"),
        "manifest_valid": bool(validation.get("valid")),
        "manifest_error_count": len(validation.get("errors", [])),
        "manifest_warning_count": len(validation.get("warnings", [])),
        "checked_artifact_count": validation.get("checked_artifacts", 0),
        "experiment_id": metadata.get("experiment_id") or execution.get("experiment_id"),
        "template": metadata.get("template") or execution.get("template"),
        "execution_status": execution.get("status"),
        "exit_code": execution.get("exit_code"),
        "quality_gate_status": quality_gate.get("status"),
        "quality_gate_valid": quality_gate.get("valid"),
        "quality_gate_failed_check_count": int(quality_gate.get("failed_check_count", 0) or 0),
        "metrics": metrics,
        "metric_count": len(metrics),
        "artifact_links": _artifact_links(run_dir),
        "manifest_sha256": sha256_file(run_dir / "manifest.json") if (run_dir / "manifest.json").exists() else None,
    }


def _metrics(run_dir: Path) -> dict[str, Any]:
    metrics = read_json(run_dir / "data" / "metrics.json", default={}) or {}
    if isinstance(metrics, dict) and metrics:
        return _scalar_metrics(metrics)
    demo = read_json(run_dir / "data" / "demo_metrics.json", default={}) or {}
    if isinstance(demo, dict) and demo:
        return _scalar_metrics(demo)
    sweep = read_json(run_dir / "data" / "sweep_results.json", default={}) or {}
    if isinstance(sweep, dict):
        rows = sweep.get("results", [])
        rows = rows if isinstance(rows, list) else []
        return {
            "result_count": len(rows),
            "noise_std_count": len(sweep.get("noise_std_values", []) or []),
            "seed_count": len(sweep.get("seeds", []) or []),
        }
    execution = read_json(run_dir / "data" / "execution_result.json", default={}) or {}
    if isinstance(execution, dict) and execution:
        return _scalar_metrics({"exit_code": execution.get("exit_code")})
    return {}


def _scalar_metrics(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[str(key)] = value
    return result


def _artifact_links(run_dir: Path) -> list[dict[str, Any]]:
    paths = [
        run_dir / "manifest.json",
        run_dir / "metadata.json",
        run_dir / "reports" / "quality_gate.json",
        run_dir / "reports" / "quality_gate.md",
        run_dir / "reports" / "experiment_report.md",
        run_dir / "reports" / "demo_report.md",
        run_dir / "data" / "metrics.json",
        run_dir / "data" / "demo_metrics.json",
        run_dir / "data" / "execution_result.json",
        run_dir / "configs" / "environment_snapshot.json",
    ]
    return [
        {
            "label": path.name,
            "path": relpath(path, run_dir).replace("\\", "/"),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        }
        for path in paths
    ]


def _count_by_key(runs: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        value = str(run.get(key) or "none")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _render_markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Run Index",
        "",
        f"- Project: `{index['project_name']}`",
        f"- Status: `{index['status']}`",
        f"- Runs: {index['run_count']}",
        f"- Valid manifests: {index['valid_manifest_count']}",
        f"- Quality gates passed: {index['quality_gate_passed_count']}",
        "",
        "## Runs",
        "",
        "| Run | Command | Experiment | Manifest | Gate | Metrics |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for run in index["runs"]:
        metrics = ", ".join(f"{key}={value}" for key, value in list(run.get("metrics", {}).items())[:6])
        lines.append(
            f"| `{run['run_id']}` | {run.get('command')} | {run.get('experiment_id')} | "
            f"{run.get('manifest_valid')} | {run.get('quality_gate_status')} | {metrics} |"
        )
    lines.extend(["", "## Policy", "", index["policy"], ""])
    return "\n".join(lines)


def _render_comparison_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Run Index Comparison",
        "",
        f"- left: `{result['left']['run_id']}`",
        f"- right: `{result['right']['run_id']}`",
        f"- all_metrics_equal: {result['all_metrics_equal']}",
        f"- manifest_valid_match: {result['manifest_valid_match']}",
        f"- quality_gate_status_match: {result['quality_gate_status_match']}",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Left | Right | Delta | Equal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in result["metric_deltas"]:
        lines.append(f"| {item['metric']} | {item['left']} | {item['right']} | {item['delta']} | {item['equal']} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _export_zip(project_dir: Path, index: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "run_explorer.zip"
    files = [
        project_dir / "workspace" / "run_index.json",
        project_dir / "workspace" / "RUN_INDEX.md",
        project_dir / "reports" / "run_explorer_manifest.json",
        project_dir / "reports" / "run_explorer" / "index.html",
    ]
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in files:
            if path.exists() and path.is_file():
                archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return escape(", ".join(f"{key}={val}" for key, val in value.items()))
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value))
    return escape(str(value))


def _badge(value: Any) -> str:
    text = _cell(value)
    normalized = str(value).lower()
    if normalized in {"true", "ready", "passed", "complete", "completed"}:
        kind = "good"
    elif normalized in {"false", "failed", "missing", "invalid"}:
        kind = "bad"
    else:
        kind = "warn"
    return f'<span class="badge {kind}">{text}</span>'


def _render_html(index: dict[str, Any]) -> str:
    rows = "\n".join(_run_row(run) for run in index["runs"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Run Explorer - {escape(index['project_name'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #1f2933; --muted: #667085; --line: #d9e2ec; --soft: #f6f8fb; --good: #147d64; --warn: #a15c00; --bad: #b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #fff; }}
    header {{ padding: 24px 30px 18px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 24px 28px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 30px 0 12px; font-size: 19px; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; min-height: 80px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 22px; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; }}
    .good {{ color: var(--good); background: #e8f5ef; }}
    .warn {{ color: var(--warn); background: #fff4df; }}
    .bad {{ color: var(--bad); background: #fdecec; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid var(--line); background: #fff; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    code {{ font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <header>
    <h1>OpenRepro Run Explorer: {escape(index['project_name'])}</h1>
    <div>Status: {_badge(index['status'])}</div>
    <p>Generated at {escape(index['created_at'])}. {escape(index['policy'])}</p>
  </header>
  <main>
    <section class="grid">
      <div class="metric"><span>Runs</span><strong>{index['run_count']}</strong></div>
      <div class="metric"><span>Valid manifests</span><strong>{index['valid_manifest_count']}</strong></div>
      <div class="metric"><span>Quality gates passed</span><strong>{index['quality_gate_passed_count']}</strong></div>
      <div class="metric"><span>Commands</span><strong>{len(index['commands'])}</strong></div>
    </section>
    <section>
      <h2>Runs</h2>
      <table>
        <thead>
          <tr>
            <th>Run</th><th>Command</th><th>Experiment</th><th>Manifest</th><th>Quality Gate</th><th>Metrics</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def _run_row(run: dict[str, Any]) -> str:
    metrics = ", ".join(f"{key}={value}" for key, value in list(run.get("metrics", {}).items())[:8])
    return f"""
    <tr>
      <td><code>{_cell(run.get('run_id'))}</code><br>{_cell(run.get('relative_path'))}</td>
      <td>{_cell(run.get('command'))}</td>
      <td>{_cell(run.get('experiment_id'))}</td>
      <td>{_badge(run.get('manifest_valid'))}</td>
      <td>{_badge(run.get('quality_gate_status'))}</td>
      <td>{_cell(metrics)}</td>
    </tr>
    """
