"""Guided dry-run advance plans for reproduction workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .checkpoints import generate_workflow_checkpoints
from .gaps import generate_reproduction_gaps
from .utils import iso_now, read_json, safe_write_text, write_json
from .artifact_manager import sha256_file

ADVANCE_PLAN_SCHEMA_VERSION = "1.8.1"


def generate_advance_plan(project_dir: Path, dry_run: bool = True) -> dict[str, Any]:
    """Write a dry-run advance plan under workspace/."""
    project_dir = Path(project_dir)
    gaps = generate_reproduction_gaps(project_dir)
    checkpoints = generate_workflow_checkpoints(project_dir)
    action = _select_action(project_dir, gaps, checkpoints)
    actions = [action] if action else []
    result = {
        "schema_version": ADVANCE_PLAN_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "dry_run": dry_run,
        "status": "ready" if actions else "complete",
        "action_count": len(actions),
        "actions": actions,
        "top_command": actions[0]["command"] if actions else None,
        "source": actions[0]["source"] if actions else None,
        "checkpoints": {
            "status": checkpoints.get("status"),
            "next_checkpoint": checkpoints.get("next_checkpoint"),
            "next_command": checkpoints.get("next_command"),
        },
        "gaps": {
            "status": gaps.get("status"),
            "open_count": gaps.get("open_count"),
            "top_suggested_command": gaps.get("top_suggested_command"),
        },
        "policy": "Advance plans preview workflow commands only; they do not execute commands or create scientific evidence.",
    }
    write_json(project_dir / "workspace" / "advance_plan.json", result)
    safe_write_text(project_dir / "workspace" / "ADVANCE_PLAN.md", _render_advance_markdown(result))
    return result


def advance_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing advance plan summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "advance_plan.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "dry_run": bool(data.get("dry_run", False)) if path.exists() else False,
        "action_count": int(data.get("action_count", 0) or 0),
        "top_command": data.get("top_command"),
        "source": data.get("source"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _select_action(project_dir: Path, gaps: dict[str, Any], checkpoints: dict[str, Any]) -> dict[str, Any] | None:
    if gaps.get("open_count", 0) and gaps.get("top_suggested_command"):
        command = str(gaps["top_suggested_command"])
        return {
            "action_id": "address_top_gap",
            "source": "gaps",
            "command": command,
            "reason": "Top reproduction gap is still open.",
            "requires_human_input": "<" in command and ">" in command,
            "will_execute": False,
        }
    if checkpoints.get("next_command"):
        command = str(checkpoints["next_command"])
        return {
            "action_id": "advance_next_checkpoint",
            "source": "checkpoints",
            "command": command,
            "reason": f"Next incomplete checkpoint: {checkpoints.get('next_checkpoint')}.",
            "requires_human_input": "<" in command and ">" in command,
            "will_execute": False,
        }
    return None


def _render_advance_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Advance Plan",
        "",
        f"- schema_version: {plan['schema_version']}",
        f"- status: {plan['status']}",
        f"- dry_run: {plan['dry_run']}",
        f"- action_count: {plan['action_count']}",
        f"- top_command: {plan['top_command']}",
        "",
        "## Actions",
        "",
        "| Action | Source | Command | Reason | Will execute |",
        "| --- | --- | --- | --- | --- |",
    ]
    if plan["actions"]:
        for action in plan["actions"]:
            lines.append(
                "| {action_id} | {source} | `{command}` | {reason} | {will_execute} |".format(
                    action_id=action["action_id"],
                    source=action["source"],
                    command=action["command"],
                    reason=action["reason"],
                    will_execute=action["will_execute"],
                )
            )
    else:
        lines.append("| none | workflow |  | No next action is currently required. | False |")
    lines.extend(["", "## Policy", "", plan["policy"], ""])
    return "\n".join(lines)
