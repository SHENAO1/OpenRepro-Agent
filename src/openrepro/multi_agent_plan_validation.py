"""Multi-agent coordination plan validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .multi_agent_plan import AGENT_ROSTER, MULTI_AGENT_PLAN_SCHEMA_VERSION, build_multi_agent_plan
from .utils import iso_now, read_json, safe_write_text, write_json

MULTI_AGENT_PLAN_VALIDATION_SCHEMA_VERSION = "1.23.1"

ALLOWED_PRIORITIES = {"P0", "P1", "P2"}
ALLOWED_TASK_STATUSES = {"open"}
FORBIDDEN_COMMANDS = {
    "run-experiment",
    "rerun-experiment",
    "review-decision",
    "claim-signoff",
}


def validate_multi_agent_plan(project_dir: Path) -> dict[str, Any]:
    """Write workspace/multi_agent_plan_validation.json and Markdown."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    validation = build_multi_agent_plan_validation(project_dir)
    write_json(project_dir / "workspace" / "multi_agent_plan_validation.json", validation)
    safe_write_text(project_dir / "workspace" / "MULTI_AGENT_PLAN_VALIDATION.md", _render_markdown(validation))
    return validation


def build_multi_agent_plan_validation(project_dir: Path) -> dict[str, Any]:
    """Build a validation payload without writing files."""
    project_dir = Path(project_dir)
    plan_path = project_dir / "workspace" / "multi_agent_plan.json"
    markdown_path = project_dir / "workspace" / "MULTI_AGENT_PLAN.md"
    plan = read_json(plan_path, default={}) or {}
    plan = plan if isinstance(plan, dict) else {}
    current_plan = build_multi_agent_plan(project_dir)

    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not plan_path.exists():
        issues.append(_finding("missing_plan", "Multi-agent plan JSON is missing.", str(plan_path)))
    if not markdown_path.exists():
        warnings.append(_finding("missing_markdown", "Multi-agent plan Markdown is missing.", str(markdown_path)))
    if plan_path.exists() and not isinstance(plan, dict):
        issues.append(_finding("invalid_plan_json", "Multi-agent plan JSON is not an object.", str(plan_path)))

    if plan:
        _validate_required_fields(plan, issues)
        _validate_counts(plan, issues)
        _validate_tasks(plan, issues, warnings)
        _validate_staleness(plan, current_plan, issues, warnings)

    status = "passed" if not issues else "failed"
    top_command = None if status == "passed" else f"openrepro multi-agent-plan {project_dir}"
    if any(item["code"] == "missing_plan" for item in issues):
        top_command = f"openrepro multi-agent-plan {project_dir}"
    return {
        "schema_version": MULTI_AGENT_PLAN_VALIDATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": status,
        "valid": status == "passed",
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "top_command": top_command,
        "plan_path": str(plan_path),
        "plan_markdown_path": str(markdown_path),
        "plan_sha256": sha256_file(plan_path) if plan_path.exists() else None,
        "stable_plan_sha256": _stable_hash(plan) if plan else None,
        "current_stable_plan_sha256": _stable_hash(current_plan),
        "issues": issues,
        "warnings": warnings,
        "guardrails": [
            "Does not execute agent tasks.",
            "Does not run experiments.",
            "Does not create or close human review decisions.",
            "Does not add claim signoffs.",
            "Does not fabricate missing scientific artifacts.",
        ],
        "policy": "Multi-agent plan validation checks coordination artifacts only; it does not authorize autonomous execution or scientific reproduction claims.",
    }


def multi_agent_plan_validation_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing validation summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "multi_agent_plan_validation.json"
    markdown_path = project_dir / "workspace" / "MULTI_AGENT_PLAN_VALIDATION.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "valid": bool(data.get("valid")) if path.exists() else False,
        "issue_count": int(data.get("issue_count", 0) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _validate_required_fields(plan: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    required = [
        "schema_version",
        "status",
        "agent_count",
        "task_count",
        "open_task_count",
        "agent_roster",
        "tasks",
        "guardrails",
        "policy",
    ]
    for field in required:
        if field not in plan:
            issues.append(_finding("missing_field", f"Required field is missing: {field}", field))
    if plan.get("schema_version") != MULTI_AGENT_PLAN_SCHEMA_VERSION:
        issues.append(
            _finding(
                "schema_mismatch",
                f"Plan schema is {plan.get('schema_version')!r}; expected {MULTI_AGENT_PLAN_SCHEMA_VERSION!r}.",
                "schema_version",
            )
        )


def _validate_counts(plan: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    tasks = plan.get("tasks", [])
    tasks = tasks if isinstance(tasks, list) else []
    roster = plan.get("agent_roster", [])
    roster = roster if isinstance(roster, list) else []
    if int(plan.get("agent_count", 0) or 0) != len(roster):
        issues.append(_finding("agent_count_mismatch", "agent_count does not match agent_roster length.", "agent_count"))
    if int(plan.get("agent_count", 0) or 0) != len(AGENT_ROSTER):
        issues.append(_finding("unexpected_agent_count", "agent_count does not match the expected roster.", "agent_count"))
    if int(plan.get("task_count", 0) or 0) != len(tasks):
        issues.append(_finding("task_count_mismatch", "task_count does not match tasks length.", "task_count"))
    open_count = sum(1 for task in tasks if isinstance(task, dict) and task.get("status") == "open")
    if int(plan.get("open_task_count", 0) or 0) != open_count:
        issues.append(_finding("open_task_count_mismatch", "open_task_count does not match open tasks.", "open_task_count"))
    top_task = tasks[0] if tasks and isinstance(tasks[0], dict) else {}
    expected_top_agent = top_task.get("agent_id") if top_task else None
    expected_top_command = top_task.get("command") if top_task else None
    if plan.get("top_agent") != expected_top_agent:
        issues.append(_finding("top_agent_mismatch", "top_agent does not match the first task.", "top_agent"))
    if plan.get("top_command") != expected_top_command:
        issues.append(_finding("top_command_mismatch", "top_command does not match the first task.", "top_command"))


def _validate_tasks(
    plan: dict[str, Any],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    allowed_agents = {agent["agent_id"] for agent in AGENT_ROSTER}
    task_ids: set[str] = set()
    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list):
        issues.append(_finding("tasks_not_list", "tasks must be a list.", "tasks"))
        return
    for index, task in enumerate(tasks, start=1):
        location = f"tasks[{index - 1}]"
        if not isinstance(task, dict):
            issues.append(_finding("task_not_object", "Task is not an object.", location))
            continue
        task_id = str(task.get("task_id") or "")
        if not task_id:
            issues.append(_finding("missing_task_id", "Task is missing task_id.", location))
        elif task_id in task_ids:
            issues.append(_finding("duplicate_task_id", f"Duplicate task_id: {task_id}", location))
        task_ids.add(task_id)
        agent_id = str(task.get("agent_id") or "")
        if agent_id not in allowed_agents:
            issues.append(_finding("invalid_agent_id", f"Unknown agent_id: {agent_id}", location))
        priority = str(task.get("priority") or "")
        if priority not in ALLOWED_PRIORITIES:
            issues.append(_finding("invalid_priority", f"Invalid priority: {priority}", location))
        status = str(task.get("status") or "")
        if status not in ALLOWED_TASK_STATUSES:
            issues.append(_finding("invalid_task_status", f"Invalid task status: {status}", location))
        command = task.get("command")
        if command is not None:
            _validate_command(str(command), task, location, issues, warnings)


def _validate_command(
    command: str,
    task: dict[str, Any],
    location: str,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    tokens = command.split()
    command_name = tokens[1] if len(tokens) >= 2 and tokens[0] == "openrepro" else tokens[0] if tokens else ""
    if command_name in FORBIDDEN_COMMANDS:
        issues.append(
            _finding(
                "forbidden_command",
                f"Task command is not safe for autonomous dispatch: {command_name}",
                location,
            )
        )
    if command_name == "repair" and "--apply" in tokens:
        issues.append(_finding("forbidden_command", "repair --apply is not safe for autonomous dispatch.", location))
    if ("<" in command or ">" in command) and not task.get("requires_human_input"):
        warnings.append(_finding("human_input_flag_missing", "Placeholder command should require human input.", location))
    if any(item in command_name for item in ["decision", "signoff"]) and not task.get("requires_human_input"):
        warnings.append(_finding("human_input_flag_missing", "Decision/signoff command should require human input.", location))


def _validate_staleness(
    plan: dict[str, Any],
    current_plan: dict[str, Any],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    plan_hash = _stable_hash(plan)
    current_hash = _stable_hash(current_plan)
    if plan_hash != current_hash:
        issues.append(
            _finding(
                "stale_plan",
                "Stored multi-agent plan no longer matches the current project status.",
                "workspace/multi_agent_plan.json",
            )
        )
    if plan.get("status") not in {"complete", "ready"}:
        warnings.append(_finding("unexpected_plan_status", f"Unexpected plan status: {plan.get('status')}", "status"))


def _stable_hash(plan: dict[str, Any]) -> str:
    payload = _stable_plan(plan)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_plan(plan: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(plan, ensure_ascii=False))
    if not isinstance(payload, dict):
        return {}
    for field in ["created_at", "project_dir"]:
        payload.pop(field, None)
    source = payload.get("source")
    if isinstance(source, dict):
        source.pop("project_next_step", None)
    return payload


def _finding(code: str, message: str, location: str) -> dict[str, str]:
    return {"code": code, "message": message, "location": location}


def _render_markdown(validation: dict[str, Any]) -> str:
    issue_rows = _finding_rows(validation["issues"])
    warning_rows = _finding_rows(validation["warnings"])
    guardrails = "\n".join(f"- {item}" for item in validation["guardrails"])
    return f"""# Multi-Agent Plan Validation

- schema_version: {validation['schema_version']}
- created_at: {validation['created_at']}
- status: {validation['status']}
- valid: {validation['valid']}
- issue_count: {validation['issue_count']}
- warning_count: {validation['warning_count']}
- top_command: {validation['top_command']}
- plan_sha256: {validation['plan_sha256']}
- stable_plan_sha256: {validation['stable_plan_sha256']}
- current_stable_plan_sha256: {validation['current_stable_plan_sha256']}

## Issues

{issue_rows}

## Warnings

{warning_rows}

## Guardrails

{guardrails}

## Policy

{validation['policy']}
"""


def _finding_rows(items: list[dict[str, Any]]) -> str:
    rows = [
        "| Code | Location | Message |",
        "| --- | --- | --- |",
    ]
    if not items:
        rows.append("| none |  | No findings. |")
        return "\n".join(rows)
    for item in items:
        rows.append(
            "| {code} | {location} | {message} |".format(
                code=_cell(item.get("code")),
                location=_cell(item.get("location")),
                message=_cell(item.get("message")),
            )
        )
    return "\n".join(rows)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
