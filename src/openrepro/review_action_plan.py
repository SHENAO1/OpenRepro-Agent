"""Action plans derived from readiness review blockers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .readiness_review import build_readiness_review
from .utils import iso_now, read_json, safe_write_text, write_json

REVIEW_ACTION_PLAN_SCHEMA_VERSION = "1.22.0"


def generate_review_action_plan(project_dir: Path) -> dict[str, Any]:
    """Write workspace/review_action_plan.json and workspace/REVIEW_ACTION_PLAN.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    plan = build_review_action_plan(project_dir)
    write_json(project_dir / "workspace" / "review_action_plan.json", plan)
    safe_write_text(project_dir / "workspace" / "REVIEW_ACTION_PLAN.md", _render_markdown(plan))
    return plan


def build_review_action_plan(project_dir: Path) -> dict[str, Any]:
    """Build a review action plan payload without writing files."""
    project_dir = Path(project_dir)
    review = _load_or_build_review(project_dir)
    validation = read_json(project_dir / "reports" / "readiness_review_validation.json", default={}) or {}
    validation = validation if isinstance(validation, dict) else {}
    blocked = [item for item in review.get("checks", []) if isinstance(item, dict) and item.get("status") != "passed"]
    actions = [_action(index, check, project_dir) for index, check in enumerate(blocked, start=1)]
    role_counts = Counter(action["role"] for action in actions)
    priority_counts = Counter(action["priority"] for action in actions)
    status = "complete" if not actions else "ready"
    return {
        "schema_version": REVIEW_ACTION_PLAN_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": review.get("project_name") or project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "action_count": len(actions),
        "open_action_count": len(actions),
        "top_command": actions[0]["command"] if actions else None,
        "top_role": actions[0]["role"] if actions else None,
        "role_counts": dict(role_counts),
        "priority_counts": dict(priority_counts),
        "actions": actions,
        "source": {
            "readiness_review_status": review.get("status"),
            "readiness_review_blocker_count": review.get("blocker_count"),
            "readiness_review_path": str(project_dir / "reports" / "readiness_review.json"),
            "validation_status": validation.get("status", "missing"),
            "validation_issue_count": validation.get("issue_count", 0),
        },
        "policy": "Review action plans are advisory workflow task lists only; they do not execute commands, close decisions, or claim scientific reproduction success.",
    }


def review_action_plan_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing review action plan summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "review_action_plan.json"
    markdown_path = project_dir / "workspace" / "REVIEW_ACTION_PLAN.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "action_count": int(data.get("action_count", 0) or 0),
        "open_action_count": int(data.get("open_action_count", 0) or 0),
        "top_command": data.get("top_command"),
        "top_role": data.get("top_role"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _load_or_build_review(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "reports" / "readiness_review.json"
    review = read_json(path, default=None)
    if isinstance(review, dict):
        return review
    return build_readiness_review(project_dir)


def _action(index: int, check: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    check_id = str(check.get("check_id") or "readiness_check")
    command = str(check.get("suggested_command") or f"openrepro readiness-review {project_dir} --zip")
    return {
        "action_id": f"A{index:03d}",
        "source_check_id": check_id,
        "title": str(check.get("label") or check_id),
        "role": _role(check_id),
        "priority": _priority(check_id),
        "status": "open",
        "command": command,
        "requires_human_input": "<" in command or "review" in check_id,
        "details": check.get("details", {}),
    }


def _role(check_id: str) -> str:
    if check_id in {"review_site_ready", "reviewer_packet_ready", "review_decisions_clear"}:
        return "reviewer"
    if check_id in {"protocol_preflight_ready", "scorecard_ready", "gaps_clear"}:
        return "experimenter"
    if check_id in {"collaboration_pack_ready", "dashboard_ready", "refresh_complete", "artifact_freshness_current"}:
        return "maintainer"
    return "next_agent"


def _priority(check_id: str) -> str:
    if check_id in {"project_profile_ready", "acceptance_criteria_ready", "evidence_package_current"}:
        return "P0"
    if check_id in {"artifact_freshness_current", "refresh_complete", "protocol_preflight_ready", "gaps_clear"}:
        return "P1"
    return "P2"


def _render_markdown(plan: dict[str, Any]) -> str:
    rows = [
        "| Action | Priority | Role | Status | Source check | Command |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for action in plan["actions"]:
        rows.append(
            "| {action} | {priority} | {role} | {status} | {check} | `{command}` |".format(
                action=_cell(action["action_id"]),
                priority=_cell(action["priority"]),
                role=_cell(action["role"]),
                status=_cell(action["status"]),
                check=_cell(action["source_check_id"]),
                command=_cell(action["command"]),
            )
        )
    return f"""# Review Action Plan

- schema_version: {plan['schema_version']}
- created_at: {plan['created_at']}
- project_name: {plan['project_name']}
- status: {plan['status']}
- action_count: {plan['action_count']}
- open_action_count: {plan['open_action_count']}
- top_role: {plan['top_role']}
- top_command: {plan['top_command']}
- role_counts: {plan['role_counts']}
- priority_counts: {plan['priority_counts']}

## Actions

{chr(10).join(rows)}

## Source

- readiness_review_status: {plan['source']['readiness_review_status']}
- readiness_review_blocker_count: {plan['source']['readiness_review_blocker_count']}
- validation_status: {plan['source']['validation_status']}
- validation_issue_count: {plan['source']['validation_issue_count']}

## Policy

{plan['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
