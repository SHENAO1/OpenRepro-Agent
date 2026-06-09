"""Safe dry-run execution plan for derived multi-agent tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_dispatch import generate_agent_dispatch
from .artifact_manager import sha256_file
from .utils import iso_now, read_json, safe_write_text, write_json

AGENT_EXEC_PLAN_SCHEMA_VERSION = "1.25.0"

SAFE_COMMANDS = {
    "report",
    "handoff",
    "evidence-package",
    "review-site",
    "collaboration-pack",
    "refresh",
    "freshness",
    "dashboard",
    "readiness-review",
    "validate-readiness-review",
    "review-action-plan",
    "delivery-bundle",
    "multi-agent-plan",
    "validate-multi-agent-plan",
    "agent-board",
    "agent-dispatch",
    "agent-task-spec",
}
FORBIDDEN_COMMANDS = {
    "run-experiment",
    "rerun-experiment",
    "claim-signoff",
    "review-decision",
}


def generate_agent_exec_plan(project_dir: Path, dry_run: bool = True) -> dict[str, Any]:
    """Write workspace/agent_exec_plan.json and Markdown for safe derived tasks."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    if not dry_run:
        raise ValueError("Agent execution plans only support dry_run=True.")

    dispatch = _dispatch(project_dir)
    tasks = _tasks(dispatch)
    steps, blocked = _classify_tasks(tasks)
    status, top_command = _plan_status(dispatch, steps, blocked)
    plan = {
        "schema_version": AGENT_EXEC_PLAN_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": dispatch.get("project_name") or project_dir.name,
        "project_dir": str(project_dir),
        "dry_run": True,
        "status": status,
        "top_command": top_command,
        "task_count": len(tasks),
        "safe_step_count": len(steps),
        "blocked_task_count": len(blocked),
        "human_input_task_count": sum(1 for task in tasks if task.get("requires_human_input")),
        "steps": steps,
        "blocked_tasks": blocked,
        "source": {
            "agent_dispatch_status": dispatch.get("status"),
            "agent_dispatch_task_count": dispatch.get("task_count", 0),
            "agent_dispatch_validation_status": dispatch.get("validation_status"),
        },
        "safe_commands": sorted(SAFE_COMMANDS),
        "forbidden_commands": sorted(FORBIDDEN_COMMANDS),
        "guardrails": [
            "Dry-run only.",
            "Does not execute commands.",
            "Does not run experiments.",
            "Does not create or close human review decisions.",
            "Does not add claim signoffs.",
            "Does not apply repairs.",
            "Does not fabricate missing scientific artifacts.",
        ],
        "policy": "Agent execution plans classify safe derived-artifact commands only; they do not execute agents or commands.",
    }
    write_json(project_dir / "workspace" / "agent_exec_plan.json", plan)
    safe_write_text(project_dir / "workspace" / "AGENT_EXEC_PLAN.md", _render_markdown(plan))
    return plan


def agent_exec_plan_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing agent execution plan summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "agent_exec_plan.json"
    markdown_path = project_dir / "workspace" / "AGENT_EXEC_PLAN.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "dry_run": bool(data.get("dry_run")) if path.exists() else False,
        "task_count": int(data.get("task_count", 0) or 0),
        "safe_step_count": int(data.get("safe_step_count", 0) or 0),
        "blocked_task_count": int(data.get("blocked_task_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _dispatch(project_dir: Path) -> dict[str, Any]:
    dispatch = read_json(project_dir / "workspace" / "agent_dispatch.json", default={}) or {}
    if not isinstance(dispatch, dict) or not dispatch:
        dispatch = generate_agent_dispatch(project_dir)
    return dispatch


def _tasks(dispatch: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for agent in dispatch.get("agents", []) if isinstance(dispatch.get("agents", []), list) else []:
        if not isinstance(agent, dict):
            continue
        for task in agent.get("tasks", []) if isinstance(agent.get("tasks", []), list) else []:
            if isinstance(task, dict):
                tasks.append({**task, "agent_id": task.get("agent_id") or agent.get("agent_id")})
    return tasks


def _classify_tasks(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    steps: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for task in tasks:
        command = str(task.get("command") or "")
        command_name = _command_name(command)
        reason = _blocked_reason(command, command_name, task)
        if reason:
            blocked.append(_blocked_task(task, reason))
            continue
        steps.append(
            {
                "step_id": f"E{len(steps) + 1:03d}",
                "task_id": task.get("task_id"),
                "agent_id": task.get("agent_id"),
                "source": task.get("source"),
                "priority": task.get("priority"),
                "command_name": command_name,
                "command": command,
                "would_execute": False,
                "dry_run": True,
                "reason": "safe derived-artifact command",
            }
        )
    return steps, blocked


def _blocked_reason(command: str, command_name: str, task: dict[str, Any]) -> str | None:
    if not command:
        return "missing command"
    if "<" in command or ">" in command:
        return "placeholder command requires human input"
    if task.get("requires_human_input"):
        return "task requires human input"
    if command_name in FORBIDDEN_COMMANDS:
        return f"forbidden command: {command_name}"
    tokens = command.split()
    if command_name == "repair" and "--apply" in tokens:
        return "repair --apply is forbidden"
    if command_name not in SAFE_COMMANDS:
        return f"command is not in safe allowlist: {command_name}"
    return None


def _command_name(command: str) -> str:
    tokens = command.split()
    if not tokens:
        return ""
    if tokens[0] == "openrepro" and len(tokens) >= 2:
        return tokens[1]
    return tokens[0]


def _blocked_task(task: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "agent_id": task.get("agent_id"),
        "source": task.get("source"),
        "priority": task.get("priority"),
        "command": task.get("command"),
        "requires_human_input": bool(task.get("requires_human_input")),
        "reason": reason,
    }


def _plan_status(
    dispatch: dict[str, Any],
    steps: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
) -> tuple[str, str | None]:
    if dispatch.get("validation_status") != "passed":
        return "needs_validation", dispatch.get("top_command")
    if blocked:
        return "blocked", blocked[0].get("command")
    if steps:
        return "ready", steps[0].get("command")
    return "complete", None


def _render_markdown(plan: dict[str, Any]) -> str:
    step_rows = [
        "| Step | Agent | Task | Priority | Command | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not plan["steps"]:
        step_rows.append("| none |  |  |  |  | No safe dry-run steps. |")
    for step in plan["steps"]:
        step_rows.append(
            "| {step_id} | {agent} | {task} | {priority} | `{command}` | {reason} |".format(
                step_id=_cell(step["step_id"]),
                agent=_cell(step.get("agent_id")),
                task=_cell(step.get("task_id")),
                priority=_cell(step.get("priority")),
                command=_cell(step.get("command")),
                reason=_cell(step.get("reason")),
            )
        )
    blocked_rows = [
        "| Task | Agent | Priority | Command | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not plan["blocked_tasks"]:
        blocked_rows.append("| none |  |  |  | No blocked tasks. |")
    for task in plan["blocked_tasks"]:
        blocked_rows.append(
            "| {task_id} | {agent} | {priority} | `{command}` | {reason} |".format(
                task_id=_cell(task.get("task_id")),
                agent=_cell(task.get("agent_id")),
                priority=_cell(task.get("priority")),
                command=_cell(task.get("command")),
                reason=_cell(task.get("reason")),
            )
        )
    guardrails = "\n".join(f"- {item}" for item in plan["guardrails"])
    return f"""# Agent Execution Plan

- schema_version: {plan['schema_version']}
- created_at: {plan['created_at']}
- project_name: {plan['project_name']}
- dry_run: {plan['dry_run']}
- status: {plan['status']}
- task_count: {plan['task_count']}
- safe_step_count: {plan['safe_step_count']}
- blocked_task_count: {plan['blocked_task_count']}
- top_command: {plan['top_command']}

## Safe Dry-Run Steps

{chr(10).join(step_rows)}

## Blocked Tasks

{chr(10).join(blocked_rows)}

## Guardrails

{guardrails}

## Policy

{plan['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
