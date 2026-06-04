"""Artifact freshness graph for explaining stale or missing handoff outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .collaboration_pack import collaboration_pack_summary
from .evidence_fingerprint import evidence_package_status, evidence_source_fingerprint
from .protocol_preflight import protocol_preflight_summary
from .refresh import refresh_run_summary
from .review_decisions import review_decision_summary
from .review_site import review_site_summary
from .reviewer_packet import reviewer_packet_summary
from .timeline import project_timeline_summary
from .utils import iso_now, read_json, safe_write_text, write_json

ARTIFACT_FRESHNESS_SCHEMA_VERSION = "1.18.1"


def generate_artifact_freshness(project_dir: Path) -> dict[str, Any]:
    """Write workspace/artifact_freshness.json and Markdown."""
    project_dir = Path(project_dir)
    evidence = evidence_package_status(project_dir)
    review_site = review_site_summary(project_dir)
    collaboration = collaboration_pack_summary(project_dir)
    refresh = refresh_run_summary(project_dir)
    timeline = project_timeline_summary(project_dir)
    reviewer_packet = reviewer_packet_summary(project_dir)
    preflight = protocol_preflight_summary(project_dir)
    decisions = review_decision_summary(project_dir)
    fingerprint_diff = _fingerprint_diff(project_dir)
    nodes = [
        _node(
            "evidence_package",
            evidence["status"],
            evidence["status"] == "current",
            str(evidence["json_path"]),
            _evidence_reason(evidence, fingerprint_diff),
            f"openrepro evidence-package {project_dir} --zip",
        ),
        _node(
            "review_site",
            review_site["status"],
            review_site["present"] and review_site["status"] == "ready",
            review_site.get("path"),
            _simple_reason("review_site", review_site["status"], "ready"),
            str(review_site.get("top_command") or f"openrepro review-site {project_dir} --zip"),
        ),
        _node(
            "project_timeline",
            timeline["status"],
            timeline["present"] and timeline["status"] == "ready",
            timeline.get("path"),
            _simple_reason("project_timeline", timeline["status"], "ready"),
            f"openrepro timeline {project_dir}",
        ),
        _node(
            "reviewer_packet",
            reviewer_packet["status"],
            reviewer_packet["present"] and reviewer_packet["status"] == "ready",
            reviewer_packet.get("path"),
            _simple_reason("reviewer_packet", reviewer_packet["status"], "ready"),
            str(reviewer_packet.get("top_command") or f"openrepro reviewer-packet {project_dir} --zip"),
        ),
        _node(
            "protocol_preflight",
            preflight["status"],
            preflight["present"] and preflight["status"] == "ready",
            preflight.get("path"),
            _simple_reason("protocol_preflight", preflight["status"], "ready"),
            str(preflight.get("top_command") or f"openrepro protocol-preflight {project_dir}"),
        ),
        _node(
            "review_decisions",
            decisions["status"],
            decisions["unresolved_item_count"] == 0,
            decisions.get("path"),
            f"{decisions['unresolved_item_count']} review decision item(s) remain unresolved."
            if decisions["unresolved_item_count"]
            else "Review decisions are clear.",
            str(decisions.get("top_command") or f"openrepro review-decision {project_dir} --item-id <id> --decision needs_followup --reviewer <name>"),
        ),
        _node(
            "collaboration_pack",
            collaboration["status"],
            collaboration["present"] and collaboration["status"] == "ready" and collaboration["next_safe_command_count"] == 0,
            collaboration.get("path"),
            _collaboration_reason(collaboration),
            str(collaboration.get("top_command") or f"openrepro collaboration-pack {project_dir} --zip"),
        ),
        _node(
            "refresh_run",
            refresh["status"],
            refresh["present"] and refresh["status"] == "complete",
            refresh.get("path"),
            _simple_reason("refresh_run", refresh["status"], "complete"),
            str(refresh.get("top_command") or f"openrepro refresh {project_dir} --zip"),
        ),
    ]
    stale_nodes = [node for node in nodes if not node["current"]]
    graph = {
        "schema_version": ARTIFACT_FRESHNESS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "current" if not stale_nodes else "needs_refresh",
        "node_count": len(nodes),
        "stale_node_count": len(stale_nodes),
        "top_stale_node": stale_nodes[0]["id"] if stale_nodes else None,
        "top_stale_reason": stale_nodes[0]["reason"] if stale_nodes else None,
        "top_command": stale_nodes[0]["suggested_command"] if stale_nodes else None,
        "nodes": nodes,
        "edges": _edges(),
        "fingerprint_diff": fingerprint_diff,
        "policy": "Artifact freshness explains workflow artifact staleness only; it does not verify scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "artifact_freshness.json", graph)
    safe_write_text(project_dir / "workspace" / "ARTIFACT_FRESHNESS.md", _render_markdown(graph))
    return graph


def artifact_freshness_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing artifact freshness summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "artifact_freshness.json"
    markdown_path = project_dir / "workspace" / "ARTIFACT_FRESHNESS.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "node_count": int(data.get("node_count", 0) or 0),
        "stale_node_count": int(data.get("stale_node_count", 0) or 0),
        "top_stale_node": data.get("top_stale_node"),
        "top_stale_reason": data.get("top_stale_reason"),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _node(node_id: str, status: Any, current: bool, path: Any, reason: str, command: str) -> dict[str, Any]:
    return {
        "id": node_id,
        "status": status,
        "current": bool(current),
        "path": path,
        "reason": reason if not current else "Current.",
        "suggested_command": None if current else command,
    }


def _fingerprint_diff(project_dir: Path) -> dict[str, Any]:
    current = evidence_source_fingerprint(project_dir)
    package = read_json(project_dir / "reports" / "evidence_package.json", default={}) or {}
    package_fp = package.get("source_fingerprint", {}) if isinstance(package, dict) else {}
    package_files = package_fp.get("files", []) if isinstance(package_fp, dict) else []
    current_files = current.get("files", []) if isinstance(current, dict) else []
    old = {str(item.get("path")): str(item.get("sha256")) for item in package_files if isinstance(item, dict)}
    new = {str(item.get("path")): str(item.get("sha256")) for item in current_files if isinstance(item, dict)}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(path for path in set(old) & set(new) if old[path] != new[path])
    return {
        "package_sha256": package_fp.get("sha256") if isinstance(package_fp, dict) else None,
        "current_sha256": current.get("sha256"),
        "added": added[:25],
        "removed": removed[:25],
        "changed": changed[:25],
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
    }


def _evidence_reason(evidence: dict[str, Any], diff: dict[str, Any]) -> str:
    if evidence["status"] == "missing":
        return "Evidence package JSON or Markdown is missing."
    if evidence["status"] == "current":
        return "Evidence package fingerprint matches current source evidence."
    changed = diff["added_count"] + diff["removed_count"] + diff["changed_count"]
    return f"Evidence package fingerprint differs from current source evidence across {changed} file change(s)."


def _simple_reason(name: str, actual: Any, expected: str) -> str:
    if actual == expected:
        return f"{name} is {expected}."
    return f"{name} is {actual}; expected {expected}."


def _collaboration_reason(summary: dict[str, Any]) -> str:
    if not summary["present"]:
        return "Collaboration pack is missing."
    if summary["status"] != "ready":
        return f"Collaboration pack is {summary['status']}; expected ready."
    if summary["next_safe_command_count"] > 0:
        return f"Collaboration pack still lists {summary['next_safe_command_count']} next safe command(s)."
    return "Collaboration pack is ready."


def _edges() -> list[dict[str, str]]:
    return [
        {"source": "source_fingerprint", "target": "evidence_package"},
        {"source": "reviewer_packet", "target": "review_site"},
        {"source": "protocol_preflight", "target": "review_site"},
        {"source": "evidence_package", "target": "review_site"},
        {"source": "review_site", "target": "collaboration_pack"},
        {"source": "project_timeline", "target": "collaboration_pack"},
        {"source": "reviewer_packet", "target": "collaboration_pack"},
        {"source": "review_decisions", "target": "collaboration_pack"},
        {"source": "refresh_run", "target": "artifact_freshness"},
    ]


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(graph: dict[str, Any]) -> str:
    lines = [
        "# Artifact Freshness",
        "",
        f"- schema_version: {graph['schema_version']}",
        f"- status: {graph['status']}",
        f"- node_count: {graph['node_count']}",
        f"- stale_node_count: {graph['stale_node_count']}",
        f"- top_stale_node: {graph['top_stale_node']}",
        f"- top_stale_reason: {graph['top_stale_reason']}",
        f"- top_command: {graph['top_command']}",
        "",
        "## Nodes",
        "",
        "| Node | Status | Current | Reason | Suggested command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for node in graph["nodes"]:
        lines.append(
            "| {node} | {status} | {current} | {reason} | `{command}` |".format(
                node=_cell(node["id"]),
                status=_cell(node["status"]),
                current=_cell(node["current"]),
                reason=_cell(node["reason"]),
                command=_cell(node.get("suggested_command") or ""),
            )
        )
    lines.extend(["", "## Fingerprint Diff", ""])
    diff = graph["fingerprint_diff"]
    for key in ["added_count", "removed_count", "changed_count", "added", "removed", "changed"]:
        lines.append(f"- {key}: {_cell(diff.get(key))}")
    lines.extend(["", "## Edges", "", "| Source | Target |", "| --- | --- |"])
    for edge in graph["edges"]:
        lines.append(f"| {_cell(edge['source'])} | {_cell(edge['target'])} |")
    lines.extend(["", "## Policy", "", graph["policy"], ""])
    return "\n".join(lines)
