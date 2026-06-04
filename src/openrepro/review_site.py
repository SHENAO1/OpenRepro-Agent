"""Static review site generation for human-facing evidence handoff."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .evidence_fingerprint import evidence_package_status
from .reviewer_packet import generate_reviewer_packet
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

REVIEW_SITE_SCHEMA_VERSION = "1.16.0"


def generate_review_site(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write a static HTML review site and manifest for a project."""
    project_dir = Path(project_dir)
    packet_path = project_dir / "reports" / "reviewer_packet.json"
    packet = read_json(packet_path, default={}) or {}
    if not isinstance(packet, dict) or not packet:
        packet = generate_reviewer_packet(project_dir)

    from .project_manager import get_status

    inspect_summary = read_json(project_dir / "workspace" / "inspect_summary.json", default={}) or {}
    inspect_summary = inspect_summary if isinstance(inspect_summary, dict) else {}
    status = get_status(project_dir).to_dict()
    evidence_status = evidence_package_status(project_dir)
    evidence_package = read_json(project_dir / "reports" / "evidence_package.json", default={}) or {}
    preflight = read_json(project_dir / "workspace" / "protocol_preflight.json", default={}) or {}
    open_actions = _open_actions(project_dir, packet, preflight, evidence_status)
    blockers = _blockers(packet, preflight)
    artifacts = _artifact_index(project_dir)
    site = {
        "schema_version": REVIEW_SITE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": status.get("project_name", project_dir.name),
        "project_dir": str(project_dir),
        "status": _site_status(packet, evidence_status, blockers),
        "open_action_count": len(open_actions),
        "blocker_count": len(blockers),
        "top_command": open_actions[0]["suggested_command"] if open_actions else None,
        "overview": {
            "reviewer_packet_status": packet.get("status"),
            "claim_count": packet.get("claim_count", 0),
            "review_item_count": packet.get("review_item_count", 0),
            "evidence_package_status": evidence_status.get("status"),
            "evidence_package_stale": evidence_status.get("stale"),
            "protocol_preflight_status": preflight.get("status", "missing") if isinstance(preflight, dict) else "missing",
            "quality_gate_passed_count": inspect_summary.get("quality_gate_passed_count", 0),
            "quality_gate_failed_count": inspect_summary.get("quality_gate_failed_count", 0),
            "readiness_score": inspect_summary.get("scorecard_overall_score", 0.0),
        },
        "claim_matrix": packet.get("review_items", []),
        "open_actions": open_actions,
        "blockers": blockers,
        "validation_status": packet.get("validation_status", {}),
        "quality_gates": inspect_summary.get("quality_gates", []),
        "artifacts": artifacts,
        "evidence_package": {
            "schema_version": evidence_package.get("schema_version") if isinstance(evidence_package, dict) else None,
            "freshness": evidence_package.get("freshness", evidence_status) if isinstance(evidence_package, dict) else evidence_status,
            "path": str(project_dir / "reports" / "evidence_package.json"),
            "markdown_path": str(project_dir / "reports" / "evidence_package.md"),
            "zip_path": str(project_dir / "reports" / "evidence_package.zip"),
        },
        "policy": "Review sites present workflow evidence for human review; they do not prove scientific reproduction.",
    }
    site_dir = project_dir / "reports" / "review_site"
    index_path = site_dir / "index.html"
    manifest_path = project_dir / "reports" / "review_site_manifest.json"
    site["index_path"] = str(index_path)
    site["manifest_path"] = str(manifest_path)
    site["zip_path"] = str(project_dir / "reports" / "review_site.zip") if export_zip else None
    safe_write_text(index_path, _render_html(site))
    write_json(manifest_path, site)
    if export_zip:
        site["zip_path"] = str(_export_zip(project_dir, site))
        write_json(manifest_path, site)
    return site


def review_site_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing review-site summary without mutating project files."""
    project_dir = Path(project_dir)
    index_path = project_dir / "reports" / "review_site" / "index.html"
    manifest_path = project_dir / "reports" / "review_site_manifest.json"
    zip_path = project_dir / "reports" / "review_site.zip"
    data = read_json(manifest_path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": index_path.exists(),
        "path": str(index_path) if index_path.exists() else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if index_path.exists() else "missing"),
        "open_action_count": int(data.get("open_action_count", 0) or 0),
        "blocker_count": int(data.get("blocker_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(index_path) if index_path.exists() else None,
    }


def _site_status(packet: dict[str, Any], evidence_status: dict[str, Any], blockers: list[dict[str, Any]]) -> str:
    if evidence_status.get("status") != "current":
        return "needs_package"
    if packet.get("status") != "ready" or blockers:
        return "needs_review"
    return "ready"


def _open_actions(
    project_dir: Path,
    packet: dict[str, Any],
    preflight: dict[str, Any],
    evidence_status: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if evidence_status.get("status") != "current":
        actions.append(
            {
                "source": "evidence_package",
                "severity": "high",
                "message": f"Evidence package is {evidence_status.get('status')}.",
                "suggested_command": f"openrepro evidence-package {project_dir} --zip",
            }
        )
    for item in packet.get("open_actions", []):
        actions.append(
            {
                "source": "reviewer_packet",
                "severity": "high",
                "message": f"Claim {item.get('claim_id')} has an open evidence action.",
                "suggested_command": item.get("next_step") or packet.get("top_command"),
            }
        )
    for item in packet.get("validation_issues", []):
        actions.append(
            {
                "source": item.get("source"),
                "severity": "high",
                "message": f"{item.get('source')} status is {item.get('status')}.",
                "suggested_command": item.get("top_command"),
            }
        )
    for check in preflight.get("checks", []) if isinstance(preflight, dict) else []:
        if isinstance(check, dict) and check.get("status") != "passed" and check.get("severity") != "warning":
            actions.append(
                {
                    "source": "protocol_preflight",
                    "severity": check.get("severity", "warning"),
                    "message": check.get("label") or check.get("message") or "Protocol preflight check is not passed.",
                    "suggested_command": check.get("suggested_command"),
                }
            )
    return actions


def _blockers(packet: dict[str, Any], preflight: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if packet.get("status") not in {"ready", None}:
        blockers.append({"source": "reviewer_packet", "message": f"Reviewer packet status is {packet.get('status')}."})
    for check in preflight.get("checks", []) if isinstance(preflight, dict) else []:
        if isinstance(check, dict) and check.get("severity") == "blocking" and check.get("status") != "passed":
            blockers.append({"source": "protocol_preflight", "message": check.get("label") or check.get("message")})
    return blockers


def _artifact_index(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "reports" / "report.md",
        project_dir / "reports" / "evidence_package.md",
        project_dir / "reports" / "evidence_package.json",
        project_dir / "reports" / "evidence_package.zip",
        project_dir / "handoff" / "COLLABORATION_PACK.md",
        project_dir / "handoff" / "collaboration_pack.json",
        project_dir / "handoff" / "collaboration_pack.zip",
        project_dir / "reports" / "reviewer_packet.md",
        project_dir / "reports" / "reviewer_packet.json",
        project_dir / "reports" / "reviewer_packet.zip",
        project_dir / "workspace" / "PROJECT_TIMELINE.md",
        project_dir / "workspace" / "project_timeline.json",
        project_dir / "reports" / "claim_evidence_report.md",
        project_dir / "reports" / "claim_evidence_report_validation.md",
        project_dir / "workspace" / "PROTOCOL_PREFLIGHT.md",
        project_dir / "workspace" / "REPRODUCTION_SCORECARD.md",
        project_dir / "workspace" / "REPRODUCTION_GAPS.md",
        project_dir / "workspace" / "QUALITY_GATE_SUMMARY.md",
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


def _export_zip(project_dir: Path, site: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "review_site.zip"
    files = [
        project_dir / "reports" / "review_site" / "index.html",
        project_dir / "reports" / "review_site_manifest.json",
    ]
    files.extend(project_dir / str(item["path"]) for item in site.get("artifacts", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _badge(value: Any) -> str:
    text = escape(str(value))
    normalized = str(value).lower()
    if normalized in {"ready", "current", "passed", "complete", "clear"}:
        kind = "good"
    elif normalized in {"missing", "stale", "needs_package", "needs_review", "failed"}:
        kind = "bad"
    else:
        kind = "warn"
    return f'<span class="badge {kind}">{text}</span>'


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value))
    return escape(str(value))


def _artifact_link(item: dict[str, Any]) -> str:
    if not item.get("present"):
        return _cell(item.get("path"))
    href = escape(str(item.get("path")).replace("\\", "/"))
    return f'<a href="../{href}">{_cell(item.get("path"))}</a>'


def _render_html(site: dict[str, Any]) -> str:
    overview = site["overview"]
    claim_rows = "\n".join(
        f"""
        <tr>
          <td>{_cell(item.get("claim_id"))}</td>
          <td>{_cell(item.get("evidence_status"))}</td>
          <td>{_cell(item.get("signoff_decision"))}</td>
          <td>{_cell(item.get("signoff_reviewer"))}</td>
          <td>{_cell(item.get("quality_gate_status"))}</td>
          <td>{_cell(item.get("risk_flags", []))}</td>
          <td>{_cell(item.get("next_step"))}</td>
        </tr>
        """
        for item in site.get("claim_matrix", [])
    ) or '<tr><td colspan="7">No claims are available yet.</td></tr>'
    action_rows = "\n".join(
        f"""
        <tr>
          <td>{_cell(item.get("severity"))}</td>
          <td>{_cell(item.get("source"))}</td>
          <td>{_cell(item.get("message"))}</td>
          <td><code>{_cell(item.get("suggested_command"))}</code></td>
        </tr>
        """
        for item in site.get("open_actions", [])
    ) or '<tr><td colspan="4">No open actions.</td></tr>'
    quality_rows = "\n".join(
        f"""
        <tr>
          <td>{_cell(item.get("run_dir"))}</td>
          <td>{_badge(item.get("status"))}</td>
          <td>{_cell(item.get("failed_check_count"))}</td>
          <td>{_cell(item.get("failed_check_names", []))}</td>
        </tr>
        """
        for item in site.get("quality_gates", [])
    ) or '<tr><td colspan="4">No quality gate records.</td></tr>'
    artifact_rows = "\n".join(
        f"""
        <tr>
          <td>{_cell(item.get("label"))}</td>
          <td>{_badge("present" if item.get("present") else "missing")}</td>
          <td>{_artifact_link(item)}</td>
          <td><code>{_cell(item.get("sha256"))}</code></td>
        </tr>
        """
        for item in site.get("artifacts", [])
    )
    validation_rows = "\n".join(
        f"<tr><td>{escape(str(key))}</td><td>{_badge(value)}</td></tr>"
        for key, value in site.get("validation_status", {}).items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Review Site - {escape(site['project_name'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #17212b; --muted: #607083; --line: #d9e2ec; --soft: #f6f8fb; --good: #0f7b4f; --warn: #9a5b00; --bad: #b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #ffffff; }}
    header {{ padding: 28px 32px 18px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px 28px 48px; }}
    h1 {{ margin: 0 0 10px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin-top: 34px; font-size: 20px; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    nav a {{ display: inline-block; margin: 10px 14px 0 0; color: #175cd3; text-decoration: none; font-weight: 600; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 18px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; }}
    .metric strong {{ display: block; font-size: 22px; margin-top: 6px; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; }}
    .good {{ color: var(--good); background: #e9f7ef; }}
    .warn {{ color: var(--warn); background: #fff4df; }}
    .bad {{ color: var(--bad); background: #fdecec; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid var(--line); background: #fff; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    code {{ font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
    footer {{ margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); }}
  </style>
</head>
<body>
  <header>
    <h1>OpenRepro Review Site: {escape(site['project_name'])}</h1>
    <div>Status: {_badge(site['status'])}</div>
    <p>Generated at {escape(site['created_at'])}. {escape(site['policy'])}</p>
    <nav>
      <a href="#overview">Overview</a>
      <a href="#claims">Claims</a>
      <a href="#actions">Actions</a>
      <a href="#quality">Quality Gates</a>
      <a href="#artifacts">Artifacts</a>
    </nav>
  </header>
  <main>
    <section id="overview">
      <h2>Overview</h2>
      <div class="grid">
        <div class="metric">Reviewer packet<strong>{_badge(overview.get('reviewer_packet_status'))}</strong></div>
        <div class="metric">Evidence package<strong>{_badge(overview.get('evidence_package_status'))}</strong></div>
        <div class="metric">Protocol preflight<strong>{_badge(overview.get('protocol_preflight_status'))}</strong></div>
        <div class="metric">Claims<strong>{_cell(overview.get('claim_count'))}</strong></div>
        <div class="metric">Open actions<strong>{_cell(site.get('open_action_count'))}</strong></div>
        <div class="metric">Blockers<strong>{_cell(site.get('blocker_count'))}</strong></div>
        <div class="metric">Readiness score<strong>{_cell(overview.get('readiness_score'))}</strong></div>
        <div class="metric">Quality gates passed<strong>{_cell(overview.get('quality_gate_passed_count'))}</strong></div>
      </div>
      <h2>Validation Status</h2>
      <table><thead><tr><th>Source</th><th>Status</th></tr></thead><tbody>{validation_rows}</tbody></table>
    </section>
    <section id="claims">
      <h2>Claim Evidence Matrix</h2>
      <table>
        <thead><tr><th>Claim</th><th>Evidence</th><th>Signoff</th><th>Reviewer</th><th>Quality gate</th><th>Risk flags</th><th>Next step</th></tr></thead>
        <tbody>{claim_rows}</tbody>
      </table>
    </section>
    <section id="actions">
      <h2>Open Actions</h2>
      <table><thead><tr><th>Severity</th><th>Source</th><th>Message</th><th>Suggested command</th></tr></thead><tbody>{action_rows}</tbody></table>
    </section>
    <section id="quality">
      <h2>Quality Gates</h2>
      <table><thead><tr><th>Run</th><th>Status</th><th>Failed checks</th><th>Failed names</th></tr></thead><tbody>{quality_rows}</tbody></table>
    </section>
    <section id="artifacts">
      <h2>Review Artifacts</h2>
      <table><thead><tr><th>Artifact</th><th>Present</th><th>Path</th><th>SHA-256</th></tr></thead><tbody>{artifact_rows}</tbody></table>
    </section>
    <footer>
      <p>Top command: <code>{_cell(site.get('top_command'))}</code></p>
    </footer>
  </main>
</body>
</html>
"""
