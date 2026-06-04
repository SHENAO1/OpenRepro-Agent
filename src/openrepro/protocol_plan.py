"""Action plans derived from protocol coverage gaps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .protocol_coverage import generate_protocol_coverage, protocol_coverage_summary
from .utils import iso_now, read_json, safe_write_text, write_json

PROTOCOL_PLAN_SCHEMA_VERSION = "1.11.0"


def generate_protocol_plan(project_dir: Path) -> dict[str, Any]:
    """Write workspace/protocol_plan.json and Markdown."""
    project_dir = Path(project_dir)
    coverage_path = project_dir / "workspace" / "protocol_coverage.json"
    coverage = read_json(coverage_path, default={}) or {}
    if not isinstance(coverage, dict) or not coverage_path.exists():
        coverage = generate_protocol_coverage(project_dir)
    actions = _plan_actions(project_dir, coverage)
    result = {
        "schema_version": PROTOCOL_PLAN_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "coverage_schema_version": coverage.get("schema_version"),
        "coverage_status": coverage.get("status"),
        "status": "complete" if not actions else "ready",
        "action_count": len(actions),
        "critical_count": sum(1 for item in actions if item["priority"] == "critical"),
        "high_count": sum(1 for item in actions if item["priority"] == "high"),
        "top_command": actions[0]["suggested_command"] if actions else None,
        "actions": actions,
        "policy": "Protocol plans preview workflow actions only; they do not execute commands or prove scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "protocol_plan.json", result)
    safe_write_text(project_dir / "workspace" / "PROTOCOL_PLAN.md", _render_protocol_plan_markdown(result))
    return result


def protocol_plan_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing protocol plan summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "protocol_plan.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    coverage = protocol_coverage_summary(project_dir)
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "action_count": int(data.get("action_count", coverage["uncovered_count"]) or 0),
        "critical_count": int(data.get("critical_count", 0) or 0),
        "high_count": int(data.get("high_count", 0) or 0),
        "top_command": data.get("top_command") or coverage.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _plan_actions(project_dir: Path, coverage: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    dimensions = coverage.get("dimensions", [])
    if not isinstance(dimensions, list):
        dimensions = []
    for index, dimension in enumerate(dimensions, start=1):
        if not isinstance(dimension, dict) or dimension.get("status") == "complete":
            continue
        command = _command_for_dimension(project_dir, dimension, coverage)
        uncovered_items = _uncovered_items(dimension)
        source = str(dimension.get("key") or f"dimension_{index}")
        actions.append(
            {
                "action_id": f"protocol_plan_{index:02d}_{source}",
                "priority": _priority_for_dimension(dimension),
                "source": source,
                "title": _title_for_dimension(dimension),
                "status": "open",
                "suggested_command": command,
                "blocked_by": [item["id"] for item in uncovered_items if item.get("id")],
                "covered_count": int(dimension.get("covered_count", 0) or 0),
                "total_count": int(dimension.get("total_count", 0) or 0),
                "uncovered_count": int(dimension.get("uncovered_count", 0) or 0),
                "coverage_percent": float(dimension.get("coverage_percent", 0.0) or 0.0),
                "will_execute": False,
                "requires_human_input": "<" in command and ">" in command,
                "details": uncovered_items,
            }
        )
    return sorted(actions, key=lambda item: (_priority_rank(str(item["priority"])), str(item["source"])))


def _command_for_dimension(project_dir: Path, dimension: dict[str, Any], coverage: dict[str, Any]) -> str:
    command = str(dimension.get("top_command") or coverage.get("top_command") or f"openrepro protocol-plan {project_dir}")
    return command.replace("<project>", str(project_dir))


def _uncovered_items(dimension: dict[str, Any]) -> list[dict[str, Any]]:
    items = dimension.get("items", [])
    if not isinstance(items, list):
        return []
    uncovered: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("covered"):
            continue
        uncovered.append(
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "suggested_command": item.get("suggested_command"),
                "quality_gate_status": item.get("quality_gate_status"),
                "linked_experiments": item.get("linked_experiments", []),
                "linked_runs": item.get("linked_runs", []),
            }
        )
    return uncovered


def _priority_for_dimension(dimension: dict[str, Any]) -> str:
    key = str(dimension.get("key") or "")
    status = str(dimension.get("status") or "")
    if key in {"target_claims", "acceptance_criteria"}:
        return "critical" if status in {"missing", "blocked"} else "high"
    if key in {"required_data", "required_experiments", "required_runs"}:
        return "high" if status in {"missing", "blocked"} else "medium"
    return "medium"


def _priority_rank(priority: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 4)


def _title_for_dimension(dimension: dict[str, Any]) -> str:
    label = str(dimension.get("label") or dimension.get("key") or "Protocol coverage")
    status = str(dimension.get("status") or "needs action")
    return f"{label} ({status})"


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_protocol_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Protocol Plan",
        "",
        f"- schema_version: {plan['schema_version']}",
        f"- status: {plan['status']}",
        f"- action_count: {plan['action_count']}",
        f"- critical_count: {plan['critical_count']}",
        f"- high_count: {plan['high_count']}",
        f"- top_command: {plan['top_command']}",
        "",
        "## Actions",
        "",
        "| Action | Priority | Source | Status | Suggested command |",
        "| --- | --- | --- | --- | --- |",
    ]
    if plan["actions"]:
        for action in plan["actions"]:
            lines.append(
                "| {action_id} | {priority} | {source} | {status} | `{command}` |".format(
                    action_id=_cell(action["action_id"]),
                    priority=_cell(action["priority"]),
                    source=_cell(action["source"]),
                    status=_cell(action["status"]),
                    command=_cell(action["suggested_command"]),
                )
            )
    else:
        lines.append("| none | none | none | complete | none |")
    lines.extend(["", "## Policy", "", plan["policy"], ""])
    return "\n".join(lines)
