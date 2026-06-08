"""Static project dashboard generation."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .acceptance_criteria import acceptance_criteria_summary
from .artifact_manager import sha256_file
from .collaboration_pack import collaboration_pack_summary
from .evidence_fingerprint import evidence_package_status
from .freshness import artifact_freshness_summary
from .gaps import gaps_summary
from .project_profile import project_profile_summary
from .refresh import refresh_run_summary
from .review_decisions import review_decision_summary
from .review_site import review_site_summary
from .reviewer_packet import reviewer_packet_summary
from .scorecard import scorecard_summary
from .timeline import project_timeline_summary
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

DASHBOARD_SCHEMA_VERSION = "1.20.1"


def generate_dashboard(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write reports/dashboard/index.html and a manifest, optionally zipped."""
    project_dir = Path(project_dir)
    evidence = evidence_package_status(project_dir)
    freshness = artifact_freshness_summary(project_dir)
    refresh = refresh_run_summary(project_dir)
    collaboration = collaboration_pack_summary(project_dir)
    timeline = project_timeline_summary(project_dir)
    reviewer_packet = reviewer_packet_summary(project_dir)
    review_site = review_site_summary(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    decisions = review_decision_summary(project_dir)
    project_profile = project_profile_summary(project_dir)
    acceptance = acceptance_criteria_summary(project_dir)
    status, top_command = _dashboard_status(project_dir, evidence, freshness, refresh, collaboration)
    dashboard = {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": top_command,
        "readiness": {
            "score": scorecard.get("overall_score"),
            "scorecard_status": scorecard.get("overall_status"),
            "gaps_status": gaps.get("status"),
            "gaps_open_count": gaps.get("open_count"),
            "review_decision_status": decisions.get("status"),
            "unresolved_review_decisions": decisions.get("unresolved_item_count"),
        },
        "freshness": freshness,
        "refresh_run": refresh,
        "collaboration_pack": collaboration,
        "timeline": timeline,
        "reviewer_packet": reviewer_packet,
        "review_site": review_site,
        "project_profile": project_profile,
        "acceptance_criteria": acceptance,
        "evidence_package": evidence,
        "artifact_links": _artifact_links(project_dir),
        "policy": "Dashboards organize workflow state for project handoff; they do not prove scientific reproduction.",
    }
    dashboard_dir = project_dir / "reports" / "dashboard"
    index_path = dashboard_dir / "index.html"
    manifest_path = project_dir / "reports" / "dashboard_manifest.json"
    dashboard["index_path"] = str(index_path)
    dashboard["manifest_path"] = str(manifest_path)
    dashboard["zip_path"] = str(project_dir / "reports" / "dashboard.zip") if export_zip else None
    safe_write_text(index_path, _render_html(dashboard))
    write_json(manifest_path, dashboard)
    if export_zip:
        dashboard["zip_path"] = str(_export_zip(project_dir, dashboard))
        write_json(manifest_path, dashboard)
    return dashboard


def dashboard_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing dashboard summary without mutating files."""
    project_dir = Path(project_dir)
    index_path = project_dir / "reports" / "dashboard" / "index.html"
    manifest_path = project_dir / "reports" / "dashboard_manifest.json"
    zip_path = project_dir / "reports" / "dashboard.zip"
    data = read_json(manifest_path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": index_path.exists(),
        "path": str(index_path) if index_path.exists() else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if index_path.exists() else "missing"),
        "top_command": data.get("top_command"),
        "readiness_score": (data.get("readiness", {}) or {}).get("score") if isinstance(data.get("readiness"), dict) else None,
        "stale_node_count": (data.get("freshness", {}) or {}).get("stale_node_count") if isinstance(data.get("freshness"), dict) else 0,
        "sha256": sha256_file(index_path) if index_path.exists() else None,
    }


def _dashboard_status(
    project_dir: Path,
    evidence: dict[str, Any],
    freshness: dict[str, Any],
    refresh: dict[str, Any],
    collaboration: dict[str, Any],
) -> tuple[str, str | None]:
    if evidence.get("status") != "current":
        return "needs_evidence_package", f"openrepro evidence-package {project_dir} --zip"
    if refresh.get("status") != "complete":
        return "needs_refresh", f"openrepro refresh {project_dir} --zip"
    if freshness.get("status") != "current":
        return "needs_freshness", str(freshness.get("top_command") or f"openrepro freshness {project_dir}")
    if collaboration.get("status") != "ready" or int(collaboration.get("next_safe_command_count", 0) or 0) > 0:
        return "needs_collaboration_pack", str(collaboration.get("top_command") or f"openrepro collaboration-pack {project_dir} --zip")
    return "ready", None


def _artifact_links(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "workspace" / "ARTIFACT_FRESHNESS.md",
        project_dir / "workspace" / "REFRESH_RUN.md",
        project_dir / "workspace" / "REPRO_LOCK.md",
        project_dir / "workspace" / "REPRO_LOCK_VALIDATION.md",
        project_dir / "workspace" / "DATA_PROFILE.md",
        project_dir / "workspace" / "DATA_EXPECTATION_RESULTS.md",
        project_dir / "workspace" / "RUN_INDEX.md",
        project_dir / "reports" / "run_explorer" / "index.html",
        project_dir / "workspace" / "EXPERIMENT_TRACKING.md",
        project_dir / "reports" / "experiments" / "index.html",
        project_dir / "workspace" / "EVALUATION_REGISTRY.md",
        project_dir / "workspace" / "EVALUATION_RESULTS.md",
        project_dir / "workspace" / "EXPERIMENT_LEADERBOARD.md",
        project_dir / "reports" / "evidence_explorer" / "index.html",
        project_dir / "reports" / "local_ui" / "index.html",
        project_dir / "workspace" / "LOCAL_UI_SUMMARY.md",
        project_dir / "workspace" / "EVIDENCE_QUERY.md",
        project_dir / "workspace" / "WORKFLOW_PRESET.md",
        project_dir / "workspace" / "WORKFLOW_EXECUTION.md",
        project_dir / "workspace" / "PIPELINE_PLAN.md",
        project_dir / "workspace" / "PIPELINE_VALIDATION.md",
        project_dir / "workspace" / "ASSET_CATALOG.md",
        project_dir / "workspace" / "ASSET_BUILD_PLAN.md",
        project_dir / "workspace" / "ASSET_MATERIALIZATION.md",
        project_dir / "workspace" / "ARTIFACT_CACHE.md",
        project_dir / "workspace" / "ARTIFACT_CACHE_VALIDATION.md",
        project_dir / "workspace" / "ARTIFACT_CACHE_REMOTES.md",
        project_dir / "workspace" / "ARTIFACT_CACHE_PUSH.md",
        project_dir / "workspace" / "ARTIFACT_CACHE_PULL.md",
        project_dir / "workspace" / "CACHE_RESTORE_PLAN.md",
        project_dir / "workspace" / "AGENT_ADAPTER.md",
        project_dir / "workspace" / "AGENT_ADAPTER_VALIDATION.md",
        project_dir / "workspace" / "AGENT_SANDBOX_RUN.md",
        project_dir / "workspace" / "agent_trajectory.jsonl",
        project_dir / "workspace" / "CI_SUMMARY.md",
        project_dir / "workspace" / "CI_VALIDATION.md",
        project_dir / "workspace" / "PLUGIN_REGISTRY.md",
        project_dir / "workspace" / "PLUGIN_VALIDATION.md",
        project_dir / "workspace" / "PROMOTION_PLAN.md",
        project_dir / "workspace" / "PROMOTION_RECORD.md",
        project_dir / "workspace" / "PROMOTION_REGISTRY.md",
        project_dir / "workspace" / "GITHUB_PR_SUMMARY.md",
        project_dir / "reports" / "pr_comment.md",
        project_dir / "handoff" / "COLLABORATION_PACK.md",
        project_dir / "workspace" / "PROJECT_TIMELINE.md",
        project_dir / "workspace" / "PROJECT_PROFILE.md",
        project_dir / "workspace" / "ACCEPTANCE_CRITERIA.md",
        project_dir / "reports" / "reviewer_packet.md",
        project_dir / "reports" / "review_site" / "index.html",
        project_dir / "reports" / "evidence_package.md",
        project_dir / "reports" / "report.md",
        project_dir / "handoff" / "AGENT_HANDOFF.md",
    ]
    return [
        {
            "label": path.name,
            "path": relpath(path, project_dir),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for path in paths
    ]


def _export_zip(project_dir: Path, dashboard: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "dashboard.zip"
    files = [
        project_dir / "reports" / "dashboard" / "index.html",
        project_dir / "reports" / "dashboard_manifest.json",
    ]
    files.extend(project_dir / str(item["path"]) for item in dashboard.get("artifact_links", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value))
    return escape(str(value))


def _badge(value: Any) -> str:
    text = _cell(value)
    normalized = str(value).lower()
    if normalized in {"ready", "current", "complete", "clear", "passed"}:
        kind = "good"
    elif normalized in {"missing", "stale", "failed", "needs_refresh", "needs_freshness", "needs_evidence_package"}:
        kind = "bad"
    else:
        kind = "warn"
    return f'<span class="badge {kind}">{text}</span>'


def _artifact_link(item: dict[str, Any]) -> str:
    if not item.get("present"):
        return _cell(item.get("path"))
    href = escape(str(item.get("path")).replace("\\", "/"))
    return f'<a href="../../{href}">{_cell(item.get("path"))}</a>'


def _render_html(dashboard: dict[str, Any]) -> str:
    readiness = dashboard["readiness"]
    freshness = dashboard["freshness"]
    refresh = dashboard["refresh_run"]
    collaboration = dashboard["collaboration_pack"]
    project_profile = dashboard["project_profile"]
    acceptance = dashboard["acceptance_criteria"]
    timeline = dashboard["timeline"]
    reviewer_packet = dashboard["reviewer_packet"]
    artifact_rows = "\n".join(
        f"""
        <tr>
          <td>{_cell(item.get("label"))}</td>
          <td>{_badge("present" if item.get("present") else "missing")}</td>
          <td>{_artifact_link(item)}</td>
          <td><code>{_cell(item.get("sha256"))}</code></td>
        </tr>
        """
        for item in dashboard["artifact_links"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Dashboard - {escape(dashboard['project_name'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #17212b; --muted: #5d6b7a; --line: #d8dee8; --soft: #f7f9fc; --good: #0f7b4f; --warn: #9a5b00; --bad: #b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #fff; }}
    header {{ padding: 26px 32px 18px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px 28px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 32px 0 12px; font-size: 19px; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; min-height: 82px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 22px; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; }}
    .good {{ color: var(--good); background: #e9f7ef; }}
    .warn {{ color: var(--warn); background: #fff4df; }}
    .bad {{ color: var(--bad); background: #fdecec; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid var(--line); background: #fff; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    code {{ font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <header>
    <h1>OpenRepro Dashboard: {escape(dashboard['project_name'])}</h1>
    <div>Status: {_badge(dashboard['status'])}</div>
    <p>Generated at {escape(dashboard['created_at'])}. {escape(dashboard['policy'])}</p>
  </header>
  <main>
    <section>
      <h2>Readiness</h2>
      <div class="grid">
        <div class="metric"><span>Readiness score</span><strong>{_cell(readiness.get('score'))}</strong></div>
        <div class="metric"><span>Scorecard</span><strong>{_badge(readiness.get('scorecard_status'))}</strong></div>
        <div class="metric"><span>Gaps</span><strong>{_badge(readiness.get('gaps_status'))}</strong></div>
        <div class="metric"><span>Open gaps</span><strong>{_cell(readiness.get('gaps_open_count'))}</strong></div>
        <div class="metric"><span>Review decisions</span><strong>{_badge(readiness.get('review_decision_status'))}</strong></div>
        <div class="metric"><span>Unresolved decisions</span><strong>{_cell(readiness.get('unresolved_review_decisions'))}</strong></div>
        <div class="metric"><span>Project profile</span><strong>{_badge(project_profile.get('status'))}</strong></div>
        <div class="metric"><span>Target claims</span><strong>{_cell(project_profile.get('target_claim_count'))}</strong></div>
        <div class="metric"><span>Acceptance</span><strong>{_badge(acceptance.get('status'))}</strong></div>
        <div class="metric"><span>Criteria needs work</span><strong>{_cell(acceptance.get('needs_work_count'))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Freshness</h2>
      <div class="grid">
        <div class="metric"><span>Artifact freshness</span><strong>{_badge(freshness.get('status'))}</strong></div>
        <div class="metric"><span>Stale nodes</span><strong>{_cell(freshness.get('stale_node_count'))}</strong></div>
        <div class="metric"><span>Top stale node</span><strong>{_cell(freshness.get('top_stale_node'))}</strong></div>
        <div class="metric"><span>Refresh run</span><strong>{_badge(refresh.get('status'))}</strong></div>
        <div class="metric"><span>Refresh failures</span><strong>{_cell(refresh.get('failed_step_count'))}</strong></div>
      </div>
      <p>Top command: <code>{_cell(freshness.get('top_command') or dashboard.get('top_command'))}</code></p>
    </section>
    <section>
      <h2>Handoff</h2>
      <div class="grid">
        <div class="metric"><span>Collaboration pack</span><strong>{_badge(collaboration.get('status'))}</strong></div>
        <div class="metric"><span>Collab commands</span><strong>{_cell(collaboration.get('next_safe_command_count'))}</strong></div>
        <div class="metric"><span>Timeline</span><strong>{_badge(timeline.get('status'))}</strong></div>
        <div class="metric"><span>Timeline events</span><strong>{_cell(timeline.get('event_count'))}</strong></div>
        <div class="metric"><span>Reviewer packet</span><strong>{_badge(reviewer_packet.get('status'))}</strong></div>
        <div class="metric"><span>Reviewer actions</span><strong>{_cell(reviewer_packet.get('open_action_count'))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Artifacts</h2>
      <table>
        <thead><tr><th>Artifact</th><th>Present</th><th>Path</th><th>SHA-256</th></tr></thead>
        <tbody>{artifact_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
