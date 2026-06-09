"""Static reproduction cockpit for high-signal project review."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .claim_trace import claim_trace_summary
from .dataset_card import data_quality_gate_summary, dataset_card_summary
from .evidence_fingerprint import evidence_package_status
from .evidence_graph import evidence_graph_summary
from .freshness import artifact_freshness_summary
from .gaps import gaps_summary
from .integrations import integrations_summary
from .readiness_review import readiness_review_summary
from .review_decisions import review_decision_summary
from .run_index import run_index_summary
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

COCKPIT_SCHEMA_VERSION = "1.57.0"


def generate_cockpit(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write a static reproduction cockpit and compact summary artifacts."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    data_quality = data_quality_gate_summary(project_dir)
    dataset_card = dataset_card_summary(project_dir)
    claim_trace = claim_trace_summary(project_dir)
    evidence_graph = evidence_graph_summary(project_dir)
    runs = run_index_summary(project_dir)
    bench_lite = _bench_lite_summary(project_dir)
    integrations = integrations_summary(project_dir)
    evidence = evidence_package_status(project_dir)
    freshness = artifact_freshness_summary(project_dir)
    readiness = readiness_review_summary(project_dir)
    review_decisions = review_decision_summary(project_dir)
    next_actions = _next_actions(
        project_dir,
        scorecard=scorecard,
        gaps=gaps,
        data_quality=data_quality,
        dataset_card=dataset_card,
        claim_trace=claim_trace,
        evidence_graph=evidence_graph,
        runs=runs,
        bench_lite=bench_lite,
        integrations=integrations,
        evidence=evidence,
        freshness=freshness,
        readiness=readiness,
        review_decisions=review_decisions,
    )
    status = "ready_for_review" if not next_actions else "needs_attention"
    cockpit = {
        "schema_version": COCKPIT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": next_actions[0]["command"] if next_actions else None,
        "next_action_count": len(next_actions),
        "next_actions": next_actions,
        "summary": {
            "readiness_score": scorecard.get("overall_score"),
            "readiness_status": scorecard.get("overall_status"),
            "gap_status": gaps.get("status"),
            "open_gap_count": gaps.get("open_count"),
            "data_quality_status": data_quality.get("status"),
            "data_quality_failed_count": data_quality.get("failed_count"),
            "dataset_card_status": dataset_card.get("status"),
            "claim_trace_status": claim_trace.get("validation_status", "missing"),
            "claim_trace_issue_count": claim_trace.get("validation_issue_count"),
            "evidence_graph_status": evidence_graph.get("status"),
            "evidence_graph_node_count": evidence_graph.get("node_count"),
            "run_count": runs.get("run_count"),
            "quality_gate_passed_count": runs.get("quality_gate_passed_count"),
            "bench_lite_status": bench_lite.get("status"),
            "bench_lite_tasks_passed": bench_lite.get("tasks_passed"),
            "integration_status": integrations.get("status"),
            "integration_execution_status": integrations.get("execution_status"),
            "evidence_package_status": evidence.get("status"),
            "freshness_status": freshness.get("status"),
            "readiness_review_status": readiness.get("status"),
            "unresolved_review_decisions": review_decisions.get("unresolved_item_count"),
        },
        "sections": {
            "readiness": scorecard,
            "gaps": gaps,
            "data_quality_gate": data_quality,
            "dataset_card": dataset_card,
            "claim_trace": claim_trace,
            "evidence_graph": evidence_graph,
            "runs": runs,
            "bench_lite": bench_lite,
            "integrations": integrations,
            "evidence_package": evidence,
            "freshness": freshness,
            "readiness_review": readiness,
            "review_decisions": review_decisions,
        },
        "artifact_links": _artifact_links(project_dir),
        "policy": "The reproduction cockpit organizes workflow evidence for human review; it does not prove scientific reproduction or validate scientific correctness.",
    }
    reports = project_dir / "reports"
    cockpit_dir = reports / "cockpit"
    index_path = cockpit_dir / "index.html"
    manifest_path = reports / "cockpit_manifest.json"
    summary_path = project_dir / "workspace" / "cockpit_summary.json"
    markdown_path = project_dir / "workspace" / "COCKPIT_SUMMARY.md"
    cockpit["index_path"] = str(index_path)
    cockpit["manifest_path"] = str(manifest_path)
    cockpit["summary_path"] = str(summary_path)
    cockpit["markdown_path"] = str(markdown_path)
    cockpit["zip_path"] = str(reports / "cockpit.zip") if export_zip else None

    safe_write_text(index_path, _render_html(cockpit))
    write_json(manifest_path, cockpit)
    write_json(summary_path, _summary_doc(cockpit))
    safe_write_text(markdown_path, _render_markdown(cockpit))
    if export_zip:
        cockpit["zip_path"] = str(_export_zip(project_dir, cockpit))
        write_json(manifest_path, cockpit)
        write_json(summary_path, _summary_doc(cockpit))
    return cockpit


def cockpit_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing cockpit summary without mutating files."""
    project_dir = Path(project_dir)
    index_path = project_dir / "reports" / "cockpit" / "index.html"
    manifest_path = project_dir / "reports" / "cockpit_manifest.json"
    summary_path = project_dir / "workspace" / "cockpit_summary.json"
    markdown_path = project_dir / "workspace" / "COCKPIT_SUMMARY.md"
    zip_path = project_dir / "reports" / "cockpit.zip"
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
        "top_command": data.get("top_command"),
        "next_action_count": int(data.get("next_action_count", 0) or 0),
        "readiness_score": (data.get("summary", {}) or {}).get("readiness_score") if isinstance(data.get("summary"), dict) else None,
        "data_quality_status": (data.get("summary", {}) or {}).get("data_quality_status") if isinstance(data.get("summary"), dict) else None,
        "bench_lite_status": (data.get("summary", {}) or {}).get("bench_lite_status") if isinstance(data.get("summary"), dict) else None,
        "sha256": sha256_file(index_path) if index_path.exists() else None,
    }


def _bench_lite_summary(project_dir: Path) -> dict[str, Any]:
    candidates = [
        Path.cwd() / "benchmarks" / "openrepro_bench_lite" / "openrepro_bench_lite_summary.json",
        _repo_root() / "benchmarks" / "openrepro_bench_lite" / "openrepro_bench_lite_summary.json",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(path.with_name("OPENREPRO_BENCH_LITE_SUMMARY.md")) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing"),
        "task_count": int(data.get("task_count", 0) or 0),
        "tasks_passed": int(data.get("tasks_passed", 0) or 0),
        "suite_dir": data.get("suite_dir"),
        "top_command": None if data.get("status") == "passed" else "openrepro bench-lite",
    }


def _next_actions(project_dir: Path, **sections: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    _maybe_action(actions, "data_quality", "Run or fix the data quality gate.", sections["data_quality"].get("status") == "passed", str(sections["data_quality"].get("top_command") or f"openrepro data-quality run {project_dir}"), "high")
    _maybe_action(actions, "dataset_card", "Generate the dataset card.", sections["dataset_card"].get("present") and sections["dataset_card"].get("status") in {"ready", "ready_with_warnings"}, f"openrepro dataset-card generate {project_dir}", "medium")
    _maybe_action(actions, "run_index", "Build the run index so latest runs and quality gates are visible.", sections["runs"].get("present") and int(sections["runs"].get("run_count", 0) or 0) > 0, f"openrepro runs index {project_dir}", "medium")
    _maybe_action(actions, "claim_trace", "Generate and validate claim traceability.", sections["claim_trace"].get("present") and sections["claim_trace"].get("validation_status") in {"passed", "valid"}, f"openrepro trace-claims {project_dir} --validate", "high")
    _maybe_action(actions, "evidence_graph", "Generate the unified evidence graph.", sections["evidence_graph"].get("present") and int(sections["evidence_graph"].get("node_count", 0) or 0) > 0, f"openrepro evidence-graph {project_dir}", "high")
    _maybe_action(actions, "bench_lite", "Run OpenRepro-Bench Lite for workflow benchmark evidence.", sections["bench_lite"].get("status") == "passed", str(sections["bench_lite"].get("top_command") or "openrepro bench-lite"), "medium")
    _maybe_action(actions, "integrations", "Export or plan integration adapter execution.", sections["integrations"].get("present") and sections["integrations"].get("execution_status") in {"planned", "executed", "skipped_missing_dependency"}, f"openrepro integrations run {project_dir}", "low")
    _maybe_action(actions, "evidence_package", "Refresh the evidence package.", sections["evidence"].get("status") == "current" and not sections["evidence"].get("stale"), f"openrepro evidence-package {project_dir} --zip", "high")
    _maybe_action(actions, "freshness", "Refresh artifact freshness evidence.", sections["freshness"].get("status") == "current", str(sections["freshness"].get("top_command") or f"openrepro freshness {project_dir}"), "medium")
    _maybe_action(actions, "readiness_review", "Generate the readiness review.", sections["readiness"].get("present") and sections["readiness"].get("status") == "ready_for_human_review", f"openrepro readiness-review {project_dir} --zip", "medium")
    _maybe_action(actions, "review_decisions", "Resolve open human review decisions.", int(sections["review_decisions"].get("unresolved_item_count", 0) or 0) == 0, str(sections["review_decisions"].get("top_command") or f"openrepro review-board {project_dir}"), "high")
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(actions, key=lambda item: (severity_rank.get(item["severity"], 9), item["action_id"]))


def _maybe_action(actions: list[dict[str, Any]], action_id: str, title: str, satisfied: bool, command: str, severity: str) -> None:
    if satisfied:
        return
    actions.append({"action_id": action_id, "title": title, "severity": severity, "command": command})


def _artifact_links(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "workspace" / "DATASET_CARD.md",
        project_dir / "workspace" / "DATA_QUALITY_GATE.md",
        project_dir / "workspace" / "RUN_INDEX.md",
        project_dir / "workspace" / "CLAIM_TRACE.md",
        project_dir / "workspace" / "CLAIM_TRACE_VALIDATION.md",
        project_dir / "workspace" / "EVIDENCE_GRAPH.md",
        project_dir / "workspace" / "INTEGRATION_EXECUTION.md",
        project_dir / "reports" / "evidence_package.md",
        project_dir / "workspace" / "ARTIFACT_FRESHNESS.md",
        project_dir / "reports" / "readiness_review.json",
        project_dir / "reports" / "dashboard" / "index.html",
    ]
    return [
        {
            "label": path.name,
            "path": relpath(path, project_dir),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        }
        for path in paths
    ]


def _summary_doc(cockpit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": cockpit["schema_version"],
        "created_at": cockpit["created_at"],
        "project_name": cockpit["project_name"],
        "status": cockpit["status"],
        "top_command": cockpit["top_command"],
        "next_action_count": cockpit["next_action_count"],
        "summary": cockpit["summary"],
        "path": cockpit["index_path"],
        "manifest_path": cockpit["manifest_path"],
        "markdown_path": cockpit["markdown_path"],
        "zip_path": cockpit["zip_path"],
        "policy": cockpit["policy"],
    }


def _export_zip(project_dir: Path, cockpit: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "cockpit.zip"
    files = [
        project_dir / "reports" / "cockpit" / "index.html",
        project_dir / "reports" / "cockpit_manifest.json",
        project_dir / "workspace" / "cockpit_summary.json",
        project_dir / "workspace" / "COCKPIT_SUMMARY.md",
    ]
    files.extend(project_dir / str(item["path"]) for item in cockpit.get("artifact_links", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _render_markdown(cockpit: dict[str, Any]) -> str:
    action_rows = "\n".join(
        f"| {_cell(action['severity'])} | {_cell(action['action_id'])} | {_cell(action['title'])} | `{_cell(action['command'])}` |"
        for action in cockpit["next_actions"]
    ) or "| none | none | No open cockpit actions. |  |"
    summary_rows = "\n".join(f"| {_cell(key)} | {_cell(value)} |" for key, value in cockpit["summary"].items())
    artifact_rows = "\n".join(
        f"| {_cell(item['label'])} | {_cell(item['present'])} | `{_cell(item['path'])}` |"
        for item in cockpit["artifact_links"]
    )
    return f"""# Reproduction Cockpit

- schema_version: {cockpit['schema_version']}
- status: {cockpit['status']}
- top_command: {cockpit['top_command']}
- next_action_count: {cockpit['next_action_count']}

## Summary

| Metric | Value |
| --- | --- |
{summary_rows}

## Next Actions

| Severity | Action | Title | Command |
| --- | --- | --- | --- |
{action_rows}

## Artifacts

| Artifact | Present | Path |
| --- | --- | --- |
{artifact_rows}

## Policy

{cockpit['policy']}
"""


def _render_html(cockpit: dict[str, Any]) -> str:
    summary = cockpit["summary"]
    action_rows = "\n".join(
        f"""
        <tr>
          <td>{_badge(action.get('severity'))}</td>
          <td>{_cell(action.get('title'))}</td>
          <td><code>{_cell(action.get('command'))}</code></td>
        </tr>
        """
        for action in cockpit["next_actions"]
    ) or '<tr><td colspan="3">No open cockpit actions.</td></tr>'
    artifact_rows = "\n".join(
        f"""
        <tr>
          <td>{_cell(item.get('label'))}</td>
          <td>{_badge('present' if item.get('present') else 'missing')}</td>
          <td>{_artifact_link(item)}</td>
        </tr>
        """
        for item in cockpit["artifact_links"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Cockpit - {escape(cockpit['project_name'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #16202a; --muted: #5d6978; --line: #d7dde5; --soft: #f6f8fb; --good: #0b7a4b; --warn: #9a5b00; --bad: #b42318; --accent: #1b5e9c; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #fff; }}
    header {{ padding: 26px 32px 18px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 24px 28px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 32px 0 12px; font-size: 19px; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(188px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; min-height: 88px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 22px; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; }}
    .good {{ color: var(--good); background: #e9f7ef; }}
    .warn {{ color: var(--warn); background: #fff4df; }}
    .bad {{ color: var(--bad); background: #fdecec; }}
    .info {{ color: var(--accent); background: #eaf3ff; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid var(--line); background: #fff; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    code {{ font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <header>
    <h1>OpenRepro Cockpit: {escape(cockpit['project_name'])}</h1>
    <div>Status: {_badge(cockpit['status'])}</div>
    <p>Generated at {escape(cockpit['created_at'])}. {escape(cockpit['policy'])}</p>
    <p>Top command: <code>{_cell(cockpit.get('top_command') or '')}</code></p>
  </header>
  <main>
    <section>
      <h2>Operating State</h2>
      <div class="grid">
        <div class="metric"><span>Readiness score</span><strong>{_cell(summary.get('readiness_score'))}</strong></div>
        <div class="metric"><span>Readiness</span><strong>{_badge(summary.get('readiness_status'))}</strong></div>
        <div class="metric"><span>Open gaps</span><strong>{_cell(summary.get('open_gap_count'))}</strong></div>
        <div class="metric"><span>Data quality</span><strong>{_badge(summary.get('data_quality_status'))}</strong></div>
        <div class="metric"><span>Data failures</span><strong>{_cell(summary.get('data_quality_failed_count'))}</strong></div>
        <div class="metric"><span>Dataset card</span><strong>{_badge(summary.get('dataset_card_status'))}</strong></div>
        <div class="metric"><span>Claim trace</span><strong>{_badge(summary.get('claim_trace_status'))}</strong></div>
        <div class="metric"><span>Claim issues</span><strong>{_cell(summary.get('claim_trace_issue_count'))}</strong></div>
        <div class="metric"><span>Evidence graph</span><strong>{_badge(summary.get('evidence_graph_status'))}</strong></div>
        <div class="metric"><span>Graph nodes</span><strong>{_cell(summary.get('evidence_graph_node_count'))}</strong></div>
        <div class="metric"><span>Runs</span><strong>{_cell(summary.get('run_count'))}</strong></div>
        <div class="metric"><span>Passed gates</span><strong>{_cell(summary.get('quality_gate_passed_count'))}</strong></div>
        <div class="metric"><span>Bench Lite</span><strong>{_badge(summary.get('bench_lite_status'))}</strong></div>
        <div class="metric"><span>Integrations</span><strong>{_badge(summary.get('integration_execution_status'))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Next Actions</h2>
      <table>
        <thead><tr><th>Severity</th><th>Action</th><th>Command</th></tr></thead>
        <tbody>{action_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Evidence Links</h2>
      <table>
        <thead><tr><th>Artifact</th><th>Present</th><th>Path</th></tr></thead>
        <tbody>{artifact_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def _artifact_link(item: dict[str, Any]) -> str:
    if not item.get("present"):
        return _cell(item.get("path"))
    href = escape(str(item.get("path")).replace("\\", "/"))
    return f'<a href="../../{href}">{_cell(item.get("path"))}</a>'


def _badge(value: Any) -> str:
    text = _cell(value)
    normalized = str(value).lower()
    if normalized in {"ready", "ready_for_review", "current", "complete", "clear", "passed", "executed", "planned", "ready_for_human_review"}:
        kind = "good"
    elif normalized in {"missing", "stale", "failed", "needs_attention", "needs_work", "needs_refresh", "needs_freshness", "needs_evidence_package"}:
        kind = "bad"
    elif normalized in {"high", "medium", "low"}:
        kind = "info" if normalized == "low" else "warn"
    else:
        kind = "warn"
    return f'<span class="badge {kind}">{text}</span>'


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value))
    return escape(str(value))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
