"""Collaboration pack generation for role-based project handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .evidence_fingerprint import evidence_package_status
from .protocol_preflight import protocol_preflight_summary
from .review_decisions import review_decision_summary
from .review_site import review_site_summary
from .reviewer_packet import reviewer_packet_summary
from .timeline import project_timeline_summary
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

COLLABORATION_PACK_SCHEMA_VERSION = "1.17.0"


def generate_collaboration_pack(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write handoff/collaboration_pack.json and Markdown, optionally zipped."""
    project_dir = Path(project_dir)

    from .project_manager import get_status

    status = get_status(project_dir).to_dict()
    evidence_status = evidence_package_status(project_dir)
    review_site = review_site_summary(project_dir)
    timeline = project_timeline_summary(project_dir)
    reviewer_packet = reviewer_packet_summary(project_dir)
    review_decisions = review_decision_summary(project_dir)
    preflight = protocol_preflight_summary(project_dir)
    readiness = {
        "project_status_next_step": status.get("next_step"),
        "evidence_package_status": evidence_status.get("status"),
        "evidence_package_stale": evidence_status.get("stale"),
        "review_site_status": review_site.get("status"),
        "project_timeline_status": timeline.get("status"),
        "reviewer_packet_status": reviewer_packet.get("status"),
        "protocol_preflight_status": preflight.get("status"),
        "review_decision_status": review_decisions.get("status"),
        "handoff_complete": status.get("handoff_complete"),
    }
    unresolved = _unresolved_decisions(project_dir)
    commands = _next_safe_commands(project_dir, status, evidence_status, review_site, timeline, reviewer_packet, preflight, review_decisions)
    files = _files_to_inspect(project_dir)
    pack = {
        "schema_version": COLLABORATION_PACK_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": status.get("project_name", project_dir.name),
        "project_dir": str(project_dir),
        "status": _pack_status(evidence_status, review_site, timeline, reviewer_packet, review_decisions),
        "role_count": 4,
        "unresolved_decision_count": len(unresolved),
        "next_safe_command_count": len(commands),
        "top_command": commands[0]["command"] if commands else None,
        "readiness_summary": readiness,
        "role_checklists": _role_checklists(status, readiness, files, commands),
        "unresolved_decisions": unresolved,
        "next_safe_commands": commands,
        "files_to_inspect_first": files,
        "policy": "Collaboration packs coordinate workflow handoff only; they do not prove scientific reproduction.",
    }
    handoff = project_dir / "handoff"
    write_json(handoff / "collaboration_pack.json", pack)
    safe_write_text(handoff / "COLLABORATION_PACK.md", _render_markdown(pack))
    if export_zip:
        pack["zip_path"] = str(_export_zip(project_dir, pack))
        write_json(handoff / "collaboration_pack.json", pack)
    else:
        pack["zip_path"] = str(handoff / "collaboration_pack.zip") if (handoff / "collaboration_pack.zip").exists() else None
    return pack


def collaboration_pack_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing collaboration pack summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "handoff" / "collaboration_pack.json"
    markdown_path = project_dir / "handoff" / "COLLABORATION_PACK.md"
    zip_path = project_dir / "handoff" / "collaboration_pack.zip"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists() and markdown_path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "role_count": int(data.get("role_count", 0) or 0),
        "unresolved_decision_count": int(data.get("unresolved_decision_count", 0) or 0),
        "next_safe_command_count": int(data.get("next_safe_command_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _pack_status(
    evidence_status: dict[str, Any],
    review_site: dict[str, Any],
    timeline: dict[str, Any],
    reviewer_packet: dict[str, Any],
    review_decisions: dict[str, Any],
) -> str:
    if evidence_status.get("status") != "current":
        return "needs_package"
    if review_site.get("status") != "ready":
        return "needs_review_site"
    if timeline.get("status") != "ready":
        return "needs_timeline"
    if reviewer_packet.get("status") != "ready":
        return "needs_review"
    if int(review_decisions.get("unresolved_item_count", 0) or 0) > 0:
        return "needs_decisions"
    return "ready"


def _unresolved_decisions(project_dir: Path) -> list[dict[str, Any]]:
    data = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    data = data if isinstance(data, dict) else {}
    items = data.get("unresolved_items", [])
    return [item for item in items if isinstance(item, dict)]


def _next_safe_commands(
    project_dir: Path,
    status: dict[str, Any],
    evidence_status: dict[str, Any],
    review_site: dict[str, Any],
    timeline: dict[str, Any],
    reviewer_packet: dict[str, Any],
    preflight: dict[str, Any],
    review_decisions: dict[str, Any],
) -> list[dict[str, str]]:
    candidates = [
        ("evidence_package", f"openrepro evidence-package {project_dir} --zip" if evidence_status.get("status") != "current" else ""),
        ("review_site", f"openrepro review-site {project_dir} --zip" if review_site.get("status") != "ready" else ""),
        ("timeline", f"openrepro timeline {project_dir}" if timeline.get("status") != "ready" else ""),
        ("project_status", str(status.get("next_step") or "")),
        ("reviewer_packet", str(reviewer_packet.get("top_command") or "")),
        ("protocol_preflight", str(preflight.get("top_command") or "")),
        ("review_decisions", str(review_decisions.get("top_command") or "")),
    ]
    commands: list[dict[str, str]] = []
    seen: set[str] = set()
    for source, command in candidates:
        command = command.removeprefix("Run: ").strip()
        if (
            not command
            or command in seen
            or command.startswith("Project v")
            or command.startswith("openrepro collaboration-pack")
            or command.startswith("openrepro refresh")
            or command.startswith("openrepro freshness")
        ):
            continue
        seen.add(command)
        commands.append({"source": source, "command": command})
    return commands


def _files_to_inspect(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "handoff" / "AGENT_HANDOFF.md",
        project_dir / "handoff" / "PROJECT_TIMELINE.md",
        project_dir / "handoff" / "REVIEWER_PACKET.md",
        project_dir / "handoff" / "EVIDENCE_PACKAGE.md",
        project_dir / "reports" / "review_site" / "index.html",
        project_dir / "reports" / "reviewer_packet.md",
        project_dir / "reports" / "evidence_package.md",
        project_dir / "workspace" / "PROJECT_TIMELINE.md",
        project_dir / "workspace" / "PROTOCOL_PREFLIGHT.md",
        project_dir / "workspace" / "REPRODUCTION_GAPS.md",
    ]
    files = []
    for path in paths:
        files.append(
            {
                "label": path.name,
                "path": relpath(path, project_dir),
                "present": path.exists(),
                "sha256": sha256_file(path) if path.exists() else None,
            }
        )
    return files


def _role_checklists(
    status: dict[str, Any],
    readiness: dict[str, Any],
    files: list[dict[str, Any]],
    commands: list[dict[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    command = commands[0]["command"] if commands else None
    file_names = {item["label"]: item for item in files}
    return {
        "maintainer": [
            _check("Review project status and next safe command.", bool(status.get("exists")), command),
            _check("Confirm evidence package is current.", readiness.get("evidence_package_status") == "current", "openrepro evidence-package <project> --zip"),
            _check("Confirm handoff files are complete.", bool(readiness.get("handoff_complete")), "openrepro handoff <project>"),
            _check("Open the static review site.", bool(file_names.get("index.html", {}).get("present")), "openrepro review-site <project> --zip"),
        ],
        "reviewer": [
            _check("Read reviewer packet.", bool(file_names.get("reviewer_packet.md", {}).get("present")), "openrepro reviewer-packet <project> --zip"),
            _check("Review project timeline decisions.", bool(file_names.get("PROJECT_TIMELINE.md", {}).get("present")), "openrepro timeline <project>"),
            _check("Check protocol preflight status.", readiness.get("protocol_preflight_status") == "ready", "openrepro protocol-preflight <project>"),
            _check("Resolve open review decisions.", readiness.get("review_decision_status") in {"clear", "complete"}, "openrepro review-decision <project> --item-id <id> --decision needs_followup --reviewer <name>"),
        ],
        "experimenter": [
            _check("Confirm experiment specs and data are current.", not status.get("evidence_package_stale"), "openrepro status <project>"),
            _check("Review quality gates.", status.get("latest_experiment_quality_gate_status") == "passed", "openrepro quality-gate <project> --all"),
            _check("Inspect run lineage.", bool(status.get("lineage_exists")), "openrepro lineage <project>"),
            _check("Inspect reproduction gaps.", status.get("gaps_status") == "clear", "openrepro gaps <project>"),
        ],
        "next_agent": [
            _check("Start from AGENT_HANDOFF.", bool(file_names.get("AGENT_HANDOFF.md", {}).get("present")), "openrepro handoff <project>"),
            _check("Read the project timeline.", bool(file_names.get("PROJECT_TIMELINE.md", {}).get("present")), "openrepro timeline <project>"),
            _check("Open evidence package summary.", bool(file_names.get("evidence_package.md", {}).get("present")), "openrepro evidence-package <project> --zip"),
            _check("Run only the next safe command.", command is None, command),
        ],
    }


def _check(label: str, complete: bool, suggested_command: str | None) -> dict[str, Any]:
    return {
        "label": label,
        "complete": bool(complete),
        "suggested_command": suggested_command,
    }


def _export_zip(project_dir: Path, pack: dict[str, Any]) -> Path:
    zip_path = project_dir / "handoff" / "collaboration_pack.zip"
    files = [
        project_dir / "handoff" / "collaboration_pack.json",
        project_dir / "handoff" / "COLLABORATION_PACK.md",
    ]
    files.extend(project_dir / str(item["path"]) for item in pack.get("files_to_inspect_first", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# Collaboration Pack",
        "",
        f"- schema_version: {pack['schema_version']}",
        f"- status: {pack['status']}",
        f"- unresolved_decision_count: {pack['unresolved_decision_count']}",
        f"- next_safe_command_count: {pack['next_safe_command_count']}",
        f"- top_command: {pack['top_command']}",
        "",
        "## Readiness Summary",
        "",
    ]
    for key, value in pack["readiness_summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Role Checklists", ""])
    for role, checks in pack["role_checklists"].items():
        lines.extend([f"### {role}", "", "| Complete | Task | Suggested command |", "| --- | --- | --- |"])
        for check in checks:
            lines.append(f"| {check['complete']} | {_cell(check['label'])} | `{_cell(check.get('suggested_command'))}` |")
        lines.append("")
    lines.extend(["## Next Safe Commands", "", "| Source | Command |", "| --- | --- |"])
    if pack["next_safe_commands"]:
        for item in pack["next_safe_commands"]:
            lines.append(f"| {_cell(item['source'])} | `{_cell(item['command'])}` |")
    else:
        lines.append("| none | No safe follow-up command is pending. |")
    lines.extend(["", "## Files To Inspect First", "", "| Present | File | SHA-256 |", "| --- | --- | --- |"])
    for item in pack["files_to_inspect_first"]:
        lines.append(f"| {item['present']} | `{_cell(item['path'])}` | `{_cell(item.get('sha256'))}` |")
    lines.extend(["", "## Unresolved Decisions", "", "| Priority | Source | Title | Suggested command |", "| --- | --- | --- | --- |"])
    if pack["unresolved_decisions"]:
        for item in pack["unresolved_decisions"]:
            lines.append(
                "| {priority} | {source} | {title} | `{command}` |".format(
                    priority=_cell(item.get("priority")),
                    source=_cell(item.get("source")),
                    title=_cell(item.get("title")),
                    command=_cell(item.get("suggested_command")),
                )
            )
    else:
        lines.append("| none | workflow | No unresolved review decisions. |  |")
    lines.extend(["", "## Policy", "", pack["policy"], ""])
    return "\n".join(lines)
