"""Static local project console for OpenRepro artifacts."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZipFile

from .agent_adapter import agent_adapter_summary
from .agent_board import agent_board_summary
from .agent_sandbox import agent_sandbox_summary
from .artifact_cache import artifact_cache_summary
from .artifact_manager import sha256_file
from .asset_build import asset_build_summary
from .asset_catalog import asset_catalog_summary
from .ci_integration import ci_summary
from .dashboard import dashboard_summary
from .evidence_explorer import evidence_explorer_summary
from .experiment_evaluation import evaluation_registry_summary, evaluation_results_summary
from .experiment_tracking import experiment_tracking_summary
from .pipeline_spec import pipeline_spec_summary
from .plugin_registry import plugin_registry_summary
from .promotion import promotion_summary
from .run_index import run_index_summary
from .security_policy import security_summary
from .utils import iso_now, read_json, relpath, safe_write_text, write_json
from .workflow_executor import workflow_execution_summary
from .workflow_preset import workflow_preset_summary
from .workflow_registry import workflow_state_summary

LOCAL_UI_SCHEMA_VERSION = "1.45.0"


def generate_local_ui(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write a static local UI under reports/local_ui."""
    project_dir = Path(project_dir)
    panels = _build_panels(project_dir)
    artifact_links = _artifact_links(project_dir)
    status = _overall_status(panels)
    ui = {
        "schema_version": LOCAL_UI_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "panel_count": len(panels),
        "present_panel_count": sum(1 for panel in panels if panel["present"]),
        "missing_panel_count": sum(1 for panel in panels if not panel["present"]),
        "artifact_link_count": len(artifact_links),
        "present_artifact_link_count": sum(1 for item in artifact_links if item["present"]),
        "missing_artifact_link_count": sum(1 for item in artifact_links if not item["present"]),
        "panels": panels,
        "artifact_links": artifact_links,
        "guardrails": [
            "The local UI reads existing project summaries and does not run experiments.",
            "Missing panels are shown as missing instead of being fabricated.",
            "Statuses are workflow evidence states, not scientific reproduction claims.",
        ],
        "policy": "Local UIs organize project evidence for navigation and operator review; they do not prove scientific reproduction.",
    }
    reports = project_dir / "reports"
    ui_dir = reports / "local_ui"
    index_path = ui_dir / "index.html"
    manifest_path = reports / "local_ui_manifest.json"
    summary_path = project_dir / "workspace" / "local_ui_summary.json"
    markdown_path = project_dir / "workspace" / "LOCAL_UI_SUMMARY.md"
    ui["index_path"] = str(index_path)
    ui["manifest_path"] = str(manifest_path)
    ui["summary_path"] = str(summary_path)
    ui["markdown_path"] = str(markdown_path)
    ui["zip_path"] = str(reports / "local_ui.zip") if export_zip else None

    safe_write_text(index_path, _render_html(ui))
    write_json(manifest_path, ui)
    write_json(summary_path, _summary_doc(ui))
    safe_write_text(markdown_path, _render_markdown(ui))
    if export_zip:
        ui["zip_path"] = str(_export_zip(project_dir, ui))
        write_json(manifest_path, ui)
        write_json(summary_path, _summary_doc(ui))
    return ui


def local_ui_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing local UI summary without mutating files."""
    project_dir = Path(project_dir)
    index_path = project_dir / "reports" / "local_ui" / "index.html"
    manifest_path = project_dir / "reports" / "local_ui_manifest.json"
    summary_path = project_dir / "workspace" / "local_ui_summary.json"
    markdown_path = project_dir / "workspace" / "LOCAL_UI_SUMMARY.md"
    zip_path = project_dir / "reports" / "local_ui.zip"
    data = read_json(manifest_path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": index_path.exists(),
        "path": str(index_path) if index_path.exists() else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "summary_path": str(summary_path) if summary_path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if index_path.exists() else "missing"),
        "panel_count": int(data.get("panel_count", 0) or 0),
        "present_panel_count": int(data.get("present_panel_count", 0) or 0),
        "missing_panel_count": int(data.get("missing_panel_count", 0) or 0),
        "artifact_link_count": int(data.get("artifact_link_count", 0) or 0),
        "missing_artifact_link_count": int(data.get("missing_artifact_link_count", 0) or 0),
        "sha256": sha256_file(index_path) if index_path.exists() else None,
    }


def _build_panels(project_dir: Path) -> list[dict[str, Any]]:
    return [
        _panel(
            "workflow",
            "Workflow",
            [
                ("DAG state", workflow_state_summary, [("Steps", "step_count"), ("Runnable", "runnable_step_count"), ("Blocked", "blocked_step_count")]),
                ("Preset", workflow_preset_summary, [("Preset", "preset"), ("Selected", "selected_step_count"), ("Runnable", "runnable_step_count")]),
                ("Execution", workflow_execution_summary, [("Selected", "selected_step_count"), ("Passed", "passed_step_count"), ("Blocked", "blocked_step_count")]),
                ("Pipeline", pipeline_spec_summary, [("Steps", "step_count"), ("Runnable", "runnable_step_count"), ("Valid", "valid")]),
            ],
            project_dir,
        ),
        _panel(
            "assets",
            "Assets",
            [
                ("Catalog", asset_catalog_summary, [("Assets", "asset_count"), ("Kinds", "kind_counts")]),
                ("Cache", artifact_cache_summary, [("Cached files", "cached_file_count"), ("Blobs", "blob_count"), ("Bytes", "total_size_bytes")]),
                ("Cache remotes", _cache_remote_summary, [("Remotes", "remote_count"), ("Default", "default_remote")]),
                ("Restore plan", _cache_restore_summary, [("Actions", "action_count"), ("Restore actions", "restore_action_count"), ("Status", "status")]),
                ("Build plan", asset_build_summary, [("Materialize", "materialize_step_count"), ("Blocked", "blocked_step_count"), ("Top step", "top_step_id")]),
            ],
            project_dir,
        ),
        _panel(
            "experiments",
            "Experiments",
            [
                ("Runs", run_index_summary, [("Runs", "run_count"), ("Valid manifests", "valid_manifest_count"), ("Passed gates", "quality_gate_passed_count")]),
                ("Tracking", experiment_tracking_summary, [("Experiments", "experiment_count"), ("Runs", "run_count")]),
                ("Evaluation registry", evaluation_registry_summary, [("Suites", "suite_count")]),
                ("Evaluation results", evaluation_results_summary, [("Experiments", "experiment_count"), ("Passed", "passed_experiment_count"), ("Failed", "failed_experiment_count")]),
                ("Leaderboard", _leaderboard_summary, [("Experiments", "experiment_count"), ("Rankable", "rankable_experiment_count"), ("Metric", "metric")]),
            ],
            project_dir,
        ),
        _panel(
            "review",
            "Review",
            [
                ("Dashboard", dashboard_summary, [("Readiness", "readiness_score"), ("Stale nodes", "stale_node_count")]),
                ("Evidence explorer", evidence_explorer_summary, [("Claims", "claim_count"), ("Runs", "run_count")]),
                ("Agent board", agent_board_summary, [("Agents", "agent_count"), ("Tasks", "task_count"), ("Open", "open_task_count")]),
                ("Promotion", promotion_summary, [("Promotions", "promotion_count"), ("Latest state", "latest_state"), ("Plan", "latest_plan_status")]),
            ],
            project_dir,
        ),
        _panel(
            "automation",
            "Automation",
            [
                ("Agent adapter", agent_adapter_summary, [("Steps", "adapter_step_count"), ("Blocked", "blocked_task_count"), ("Valid", "validation_valid")]),
                ("Agent sandbox", agent_sandbox_summary, [("Selected", "selected_step_count"), ("Passed", "passed_step_count"), ("Failed", "failed_step_count")]),
                ("CI", ci_summary, [("Present", "present"), ("Status", "status"), ("Test command", "test_command")]),
                ("Plugins", plugin_registry_summary, [("Plugins", "plugin_count"), ("Enabled", "enabled_plugin_count"), ("Validation", "validation_status")]),
                ("GitHub PR", _github_pr_summary, [("Checks", "check_count"), ("Failed", "failed_check_count"), ("Warnings", "warning_count")]),
                ("Security", security_summary, [("Findings", "finding_count"), ("High", "high_count"), ("Valid", "valid")]),
            ],
            project_dir,
        ),
    ]


def _panel(
    panel_id: str,
    title: str,
    summary_defs: list[tuple[str, Callable[[Path], dict[str, Any]], list[tuple[str, str]]]],
    project_dir: Path,
) -> dict[str, Any]:
    summaries = []
    for label, summary_fn, metric_defs in summary_defs:
        summary = summary_fn(project_dir)
        summaries.append(_summary_item(project_dir, label, summary, metric_defs))
    present = any(item["present"] for item in summaries)
    status = _aggregate_summary_status(summaries)
    top_command = next((item.get("top_command") for item in summaries if item.get("top_command")), None)
    return {
        "id": panel_id,
        "title": title,
        "status": status,
        "present": present,
        "summary_count": len(summaries),
        "present_summary_count": sum(1 for item in summaries if item["present"]),
        "missing_summary_count": sum(1 for item in summaries if not item["present"]),
        "top_command": top_command,
        "summaries": summaries,
    }


def _summary_item(
    project_dir: Path,
    label: str,
    summary: dict[str, Any],
    metric_defs: list[tuple[str, str]],
) -> dict[str, Any]:
    status = str(summary.get("status") or ("present" if summary.get("present") else "missing"))
    paths = _summary_paths(project_dir, summary)
    return {
        "label": label,
        "status": status,
        "present": bool(summary.get("present")),
        "schema_version": summary.get("schema_version"),
        "top_command": summary.get("top_command"),
        "metrics": [{"label": metric_label, "value": summary.get(key)} for metric_label, key in metric_defs],
        "paths": paths,
        "sha256": summary.get("sha256"),
    }


def _summary_paths(project_dir: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    keys = [
        "path",
        "comment_path",
        "markdown_path",
        "policy_path",
        "policy_markdown_path",
        "index_path",
        "explorer_path",
        "manifest_path",
        "summary_path",
        "validation_path",
        "validation_markdown_path",
        "config_path",
        "plan_path",
        "record_path",
        "materialization_path",
        "materialization_markdown_path",
        "zip_path",
        "workflow_path",
        "trajectory_path",
        "events_path",
    ]
    rows = []
    for key in keys:
        value = summary.get(key)
        if not value:
            continue
        path = Path(str(value))
        resolved = path if path.is_absolute() else project_dir / path
        rows.append(
            {
                "kind": key,
                "path": _relative_or_raw(resolved, project_dir),
                "present": resolved.exists(),
                "sha256": sha256_file(resolved) if resolved.exists() and resolved.is_file() else None,
            }
        )
    return rows


def _artifact_links(project_dir: Path) -> list[dict[str, Any]]:
    candidates = [
        ("Project dashboard", "reports/dashboard/index.html"),
        ("Evidence explorer", "reports/evidence_explorer/index.html"),
        ("Run explorer", "reports/run_explorer/index.html"),
        ("Experiment browser", "reports/experiments/index.html"),
        ("Agent board", "reports/agent_board/index.html"),
        ("Review site", "reports/review_site/index.html"),
        ("Evidence package", "reports/evidence_package.md"),
        ("Delivery bundle", "reports/DELIVERY_BUNDLE.md"),
        ("Readiness review", "reports/READINESS_REVIEW.md"),
        ("Workflow state", "workspace/WORKFLOW_STATE.md"),
        ("Workflow preset", "workspace/WORKFLOW_PRESET.md"),
        ("Workflow execution", "workspace/WORKFLOW_EXECUTION.md"),
        ("Pipeline plan", "workspace/PIPELINE_PLAN.md"),
        ("Asset catalog", "workspace/ASSET_CATALOG.md"),
        ("Asset graph", "workspace/ASSET_CATALOG_GRAPH.md"),
        ("Asset build plan", "workspace/ASSET_BUILD_PLAN.md"),
        ("Asset materialization", "workspace/ASSET_MATERIALIZATION.md"),
        ("Artifact cache", "workspace/ARTIFACT_CACHE.md"),
        ("Cache remotes", "workspace/ARTIFACT_CACHE_REMOTES.md"),
        ("Cache restore", "workspace/CACHE_RESTORE_PLAN.md"),
        ("Experiment tracking", "workspace/EXPERIMENT_TRACKING.md"),
        ("Evaluation results", "workspace/EVALUATION_RESULTS.md"),
        ("Leaderboard", "workspace/EXPERIMENT_LEADERBOARD.md"),
        ("Agent adapter", "workspace/AGENT_ADAPTER.md"),
        ("Agent sandbox", "workspace/AGENT_SANDBOX_RUN.md"),
        ("CI summary", "workspace/CI_SUMMARY.md"),
        ("CI validation", "workspace/CI_VALIDATION.md"),
        ("Plugin registry", "workspace/PLUGIN_REGISTRY.md"),
        ("Plugin validation", "workspace/PLUGIN_VALIDATION.md"),
        ("Promotion plan", "workspace/PROMOTION_PLAN.md"),
        ("Promotion record", "workspace/PROMOTION_RECORD.md"),
        ("Promotion registry", "workspace/PROMOTION_REGISTRY.md"),
        ("GitHub PR summary", "workspace/GITHUB_PR_SUMMARY.md"),
        ("GitHub PR comment", "reports/pr_comment.md"),
        ("Security policy", "workspace/SECURITY_POLICY.md"),
        ("Security audit", "workspace/SECURITY_AUDIT.md"),
        ("GitHub Actions workflow", ".github/workflows/openrepro-ci.yml"),
    ]
    links = []
    for label, relative in candidates:
        path = project_dir / relative
        links.append(
            {
                "label": label,
                "path": relative,
                "present": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
                "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
            }
        )
    return links


def _cache_remote_summary(project_dir: Path) -> dict[str, Any]:
    path = Path(project_dir) / "workspace" / "artifact_cache_remotes.json"
    markdown_path = Path(project_dir) / "workspace" / "ARTIFACT_CACHE_REMOTES.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "remote_count": int(data.get("remote_count", 0) or 0),
        "default_remote": data.get("default_remote"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _cache_restore_summary(project_dir: Path) -> dict[str, Any]:
    path = Path(project_dir) / "workspace" / "cache_restore_plan.json"
    markdown_path = Path(project_dir) / "workspace" / "CACHE_RESTORE_PLAN.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "action_count": int(data.get("action_count", 0) or 0),
        "restore_action_count": int(data.get("restore_action_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _leaderboard_summary(project_dir: Path) -> dict[str, Any]:
    path = Path(project_dir) / "workspace" / "experiment_leaderboard.json"
    markdown_path = Path(project_dir) / "workspace" / "EXPERIMENT_LEADERBOARD.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "experiment_count": int(data.get("experiment_count", 0) or 0),
        "rankable_experiment_count": int(data.get("rankable_experiment_count", 0) or 0),
        "metric": data.get("metric"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _github_pr_summary(project_dir: Path) -> dict[str, Any]:
    path = Path(project_dir) / "workspace" / "github_pr_summary.json"
    markdown_path = Path(project_dir) / "workspace" / "GITHUB_PR_SUMMARY.md"
    comment_path = Path(project_dir) / "reports" / "pr_comment.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "comment_path": str(comment_path) if comment_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "check_count": int(data.get("check_count", 0) or 0),
        "failed_check_count": int(data.get("failed_check_count", 0) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _overall_status(panels: list[dict[str, Any]]) -> str:
    if not any(panel["present"] for panel in panels):
        return "empty"
    if any(panel["status"] in {"failed", "blocked", "needs_attention"} for panel in panels):
        return "needs_attention"
    if any(panel["missing_summary_count"] for panel in panels):
        return "partial"
    return "ready"


def _aggregate_summary_status(summaries: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "missing") for item in summaries}
    if not any(item["present"] for item in summaries):
        return "missing"
    if statuses & {"failed", "blocked"}:
        return "needs_attention"
    if statuses <= {"ready", "complete", "passed", "current", "present", "written", "preserved"}:
        return "ready"
    if "missing" in statuses:
        return "partial"
    return "ready"


def _relative_or_raw(path: Path, project_dir: Path) -> str:
    try:
        return relpath(path, project_dir).replace("\\", "/")
    except ValueError:
        return str(path)


def _summary_doc(ui: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": ui["schema_version"],
        "created_at": ui["created_at"],
        "project_name": ui["project_name"],
        "status": ui["status"],
        "panel_count": ui["panel_count"],
        "present_panel_count": ui["present_panel_count"],
        "missing_panel_count": ui["missing_panel_count"],
        "artifact_link_count": ui["artifact_link_count"],
        "present_artifact_link_count": ui["present_artifact_link_count"],
        "missing_artifact_link_count": ui["missing_artifact_link_count"],
        "index_path": ui["index_path"],
        "manifest_path": ui["manifest_path"],
        "zip_path": ui["zip_path"],
        "policy": ui["policy"],
    }


def _export_zip(project_dir: Path, ui: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "local_ui.zip"
    files = [
        project_dir / "reports" / "local_ui" / "index.html",
        project_dir / "reports" / "local_ui_manifest.json",
        project_dir / "workspace" / "local_ui_summary.json",
        project_dir / "workspace" / "LOCAL_UI_SUMMARY.md",
    ]
    for item in ui.get("artifact_links", []):
        if item.get("present"):
            files.append(project_dir / str(item["path"]))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _render_markdown(ui: dict[str, Any]) -> str:
    index_relative = relpath(Path(ui["index_path"]), Path(ui["project_dir"])).replace("\\", "/")
    lines = [
        "# Local UI Summary",
        "",
        f"- schema_version: {ui['schema_version']}",
        f"- status: {ui['status']}",
        f"- panel_count: {ui['panel_count']}",
        f"- present_panel_count: {ui['present_panel_count']}",
        f"- missing_panel_count: {ui['missing_panel_count']}",
        f"- artifact_link_count: {ui['artifact_link_count']}",
        f"- missing_artifact_link_count: {ui['missing_artifact_link_count']}",
        f"- index_path: `{index_relative}`",
        "",
        "| Panel | Status | Present | Missing summaries | Top command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for panel in ui["panels"]:
        lines.append(
            "| {title} | {status} | {present} | {missing} | `{command}` |".format(
                title=_md(panel["title"]),
                status=_md(panel["status"]),
                present=_md(panel["present_summary_count"]),
                missing=_md(panel["missing_summary_count"]),
                command=_md(panel.get("top_command") or ""),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in ui["guardrails"])
    lines.extend(["", "## Policy", "", ui["policy"], ""])
    return "\n".join(lines)


def _render_html(ui: dict[str, Any]) -> str:
    nav = "\n".join(
        f'<button type="button" class="tab-button" data-target="{escape(panel["id"])}">{escape(panel["title"])}</button>'
        for panel in ui["panels"]
    )
    panel_sections = "\n".join(_panel_html(panel) for panel in ui["panels"])
    artifact_rows = "\n".join(_artifact_row(item) for item in ui["artifact_links"])
    guardrails = "\n".join(f"<li>{escape(item)}</li>" for item in ui["guardrails"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Local UI - {escape(ui['project_name'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #182230; --muted: #5d6b7a; --line: #d8dee8; --soft: #f6f8fb; --surface: #ffffff; --good: #0f766e; --warn: #9a5b00; --bad: #b42318; --blue: #2454a6; --violet: #6d3fa4; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #fff; }}
    header {{ border-bottom: 1px solid var(--line); background: linear-gradient(180deg, #f6f8fb 0%, #eef4f7 100%); }}
    .header-inner {{ max-width: 1240px; margin: 0 auto; padding: 24px 28px 18px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 30px 0 12px; font-size: 20px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; letter-spacing: 0; }}
    p, li {{ color: var(--muted); line-height: 1.5; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 20px 28px 48px; }}
    .status-line {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-top: 16px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: var(--surface); min-height: 76px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 21px; overflow-wrap: anywhere; }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; }}
    .tab-button {{ border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); padding: 8px 12px; font-size: 14px; cursor: pointer; }}
    .tab-button.active {{ border-color: var(--blue); color: var(--blue); background: #eef5ff; }}
    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }}
    .summary {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; min-height: 180px; }}
    .summary-head {{ display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }}
    .summary-metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(115px, 1fr)); gap: 8px; margin-top: 12px; }}
    .mini {{ border-left: 3px solid var(--violet); padding: 6px 8px; background: var(--soft); min-height: 50px; }}
    .mini span {{ display: block; color: var(--muted); font-size: 12px; }}
    .mini strong {{ display: block; margin-top: 4px; overflow-wrap: anywhere; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; white-space: nowrap; }}
    .good {{ color: var(--good); background: #e8f5ef; }}
    .warn {{ color: var(--warn); background: #fff4df; }}
    .bad {{ color: var(--bad); background: #fdecec; }}
    .search-row {{ display: flex; gap: 10px; align-items: center; margin: 18px 0 10px; }}
    input[type="search"] {{ width: min(480px, 100%); border: 1px solid var(--line); border-radius: 8px; padding: 9px 11px; font-size: 14px; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid var(--line); background: #fff; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    code {{ font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    @media (max-width: 640px) {{ .header-inner, main {{ padding-left: 16px; padding-right: 16px; }} .summary-head {{ display: block; }} }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <h1>OpenRepro Local UI: {escape(ui['project_name'])}</h1>
      <div class="status-line">
        <span>Status: {_badge(ui['status'])}</span>
        <span>Generated: <code>{escape(ui['created_at'])}</code></span>
      </div>
      <div class="metrics">
        <div class="metric"><span>Panels</span><strong>{ui['panel_count']}</strong></div>
        <div class="metric"><span>Present panels</span><strong>{ui['present_panel_count']}</strong></div>
        <div class="metric"><span>Artifact links</span><strong>{ui['artifact_link_count']}</strong></div>
        <div class="metric"><span>Missing links</span><strong>{ui['missing_artifact_link_count']}</strong></div>
      </div>
    </div>
  </header>
  <main>
    <nav class="tabs" aria-label="Local UI panels">{nav}</nav>
    {panel_sections}
    <section>
      <h2>Artifacts</h2>
      <div class="search-row">
        <input id="artifact-search" type="search" placeholder="Search artifacts">
      </div>
      <table>
        <thead><tr><th>Artifact</th><th>Status</th><th>Path</th><th>SHA-256</th></tr></thead>
        <tbody id="artifact-rows">{artifact_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Guardrails</h2>
      <ul>{guardrails}</ul>
      <p>{escape(ui['policy'])}</p>
    </section>
  </main>
  <script>
    const buttons = Array.from(document.querySelectorAll('.tab-button'));
    const panels = Array.from(document.querySelectorAll('.panel'));
    function activate(target) {{
      buttons.forEach(button => button.classList.toggle('active', button.dataset.target === target));
      panels.forEach(panel => panel.classList.toggle('active', panel.id === target));
    }}
    if (buttons.length) activate(buttons[0].dataset.target);
    buttons.forEach(button => button.addEventListener('click', () => activate(button.dataset.target)));
    const search = document.getElementById('artifact-search');
    const rows = Array.from(document.querySelectorAll('#artifact-rows tr'));
    search.addEventListener('input', () => {{
      const query = search.value.trim().toLowerCase();
      rows.forEach(row => {{
        row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
      }});
    }});
  </script>
</body>
</html>
"""


def _panel_html(panel: dict[str, Any]) -> str:
    cards = "\n".join(_summary_card(item) for item in panel["summaries"])
    return f"""
    <section id="{escape(panel['id'])}" class="panel">
      <h2>{escape(panel['title'])}</h2>
      <div class="status-line">
        <span>Status: {_badge(panel['status'])}</span>
        <span>Top command: <code>{_cell(panel.get('top_command'))}</code></span>
      </div>
      <div class="summary-grid">{cards}</div>
    </section>
    """


def _summary_card(item: dict[str, Any]) -> str:
    metrics = "\n".join(
        f'<div class="mini"><span>{escape(str(metric["label"]))}</span><strong>{_cell(metric.get("value"))}</strong></div>'
        for metric in item["metrics"]
    )
    links = "\n".join(_path_link(path) for path in item["paths"]) or "<p>No linked files.</p>"
    return f"""
    <article class="summary">
      <div class="summary-head">
        <h3>{escape(item['label'])}</h3>
        {_badge(item['status'])}
      </div>
      <div class="summary-metrics">{metrics}</div>
      <div>{links}</div>
    </article>
    """


def _path_link(path: dict[str, Any]) -> str:
    text = f"{path.get('kind')}: {path.get('path')}"
    if not path.get("present"):
        return f"<p>{escape(text)} {_badge('missing')}</p>"
    href = "../../" + escape(str(path.get("path")).replace("\\", "/"))
    return f'<p><a href="{href}">{escape(text)}</a></p>'


def _artifact_row(item: dict[str, Any]) -> str:
    if item.get("present"):
        href = "../../" + escape(str(item["path"]).replace("\\", "/"))
        path = f'<a href="{href}">{escape(str(item["path"]))}</a>'
    else:
        path = escape(str(item["path"]))
    return f"""
    <tr>
      <td>{escape(str(item['label']))}</td>
      <td>{_badge('present' if item.get('present') else 'missing')}</td>
      <td>{path}</td>
      <td><code>{_cell(item.get('sha256'))}</code></td>
    </tr>
    """


def _badge(value: Any) -> str:
    text = _cell(value)
    normalized = str(value).lower()
    if normalized in {"ready", "complete", "passed", "current", "present", "true", "written", "preserved"}:
        kind = "good"
    elif normalized in {"missing", "failed", "blocked", "needs_attention", "false"}:
        kind = "bad"
    else:
        kind = "warn"
    return f'<span class="badge {kind}">{text}</span>'


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return escape(", ".join(f"{key}={val}" for key, val in value.items()))
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value))
    return escape(str(value))


def _md(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
