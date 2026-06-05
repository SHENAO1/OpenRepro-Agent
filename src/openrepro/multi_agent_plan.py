"""Multi-agent coordination plan generation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, read_json, safe_write_text, write_json

MULTI_AGENT_PLAN_SCHEMA_VERSION = "1.23.0"

AGENT_ROSTER: list[dict[str, str]] = [
    {
        "agent_id": "maintainer",
        "label": "Maintainer Agent",
        "owns": "derived artifacts, refresh runs, dashboards, delivery bundles, and repository hygiene",
    },
    {
        "agent_id": "reviewer",
        "label": "Reviewer Agent",
        "owns": "human review packets, review decisions, claim evidence reports, and readiness checks",
    },
    {
        "agent_id": "experimenter",
        "label": "Experimenter Agent",
        "owns": "data provenance, experiment specs, runs, quality gates, protocols, and gaps",
    },
    {
        "agent_id": "next_agent",
        "label": "Next Agent",
        "owns": "handoff intake, safe next commands, and cross-role coordination",
    },
]


def generate_multi_agent_plan(project_dir: Path) -> dict[str, Any]:
    """Write workspace/multi_agent_plan.json and workspace/MULTI_AGENT_PLAN.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    plan = build_multi_agent_plan(project_dir)
    write_json(project_dir / "workspace" / "multi_agent_plan.json", plan)
    safe_write_text(project_dir / "workspace" / "MULTI_AGENT_PLAN.md", _render_markdown(plan))
    return plan


def build_multi_agent_plan(project_dir: Path) -> dict[str, Any]:
    """Build a multi-agent plan payload without writing files."""
    project_dir = Path(project_dir)

    from .project_manager import get_status

    status = get_status(project_dir).to_dict()
    review_action_plan = _dict(project_dir / "workspace" / "review_action_plan.json")
    collaboration_pack = _dict(project_dir / "handoff" / "collaboration_pack.json")
    delivery_bundle = _dict(project_dir / "reports" / "delivery_bundle.json")
    tasks = _tasks(project_dir, status, review_action_plan, collaboration_pack, delivery_bundle)
    role_counts = Counter(task["agent_id"] for task in tasks)
    priority_counts = Counter(task["priority"] for task in tasks)
    return {
        "schema_version": MULTI_AGENT_PLAN_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": status.get("project_name") or project_dir.name,
        "project_dir": str(project_dir),
        "status": "complete" if not tasks else "ready",
        "agent_count": len(AGENT_ROSTER),
        "task_count": len(tasks),
        "open_task_count": len(tasks),
        "top_agent": tasks[0]["agent_id"] if tasks else None,
        "top_command": tasks[0]["command"] if tasks else None,
        "agent_roster": AGENT_ROSTER,
        "agent_task_counts": dict(role_counts),
        "priority_counts": dict(priority_counts),
        "tasks": tasks,
        "handoff_order": _handoff_order(tasks),
        "source": {
            "project_next_step": status.get("next_step"),
            "review_action_plan_status": review_action_plan.get("status", "missing"),
            "review_action_plan_open_action_count": int(review_action_plan.get("open_action_count", 0) or 0),
            "collaboration_pack_status": collaboration_pack.get("status", "missing"),
            "collaboration_pack_next_safe_command_count": int(collaboration_pack.get("next_safe_command_count", 0) or 0),
            "delivery_bundle_status": delivery_bundle.get("status", "missing"),
            "delivery_bundle_missing_file_count": int(delivery_bundle.get("missing_file_count", 0) or 0),
        },
        "guardrails": [
            "Does not execute agent tasks.",
            "Does not run experiments.",
            "Does not create or close human review decisions.",
            "Does not add claim signoffs.",
            "Does not fabricate missing scientific artifacts.",
        ],
        "policy": "Multi-agent plans coordinate workflow tasks only; they do not run autonomous agents or claim scientific reproduction success.",
    }


def multi_agent_plan_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing multi-agent plan summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "multi_agent_plan.json"
    markdown_path = project_dir / "workspace" / "MULTI_AGENT_PLAN.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "agent_count": int(data.get("agent_count", 0) or 0),
        "task_count": int(data.get("task_count", 0) or 0),
        "open_task_count": int(data.get("open_task_count", 0) or 0),
        "top_agent": data.get("top_agent"),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _tasks(
    project_dir: Path,
    status: dict[str, Any],
    review_action_plan: dict[str, Any],
    collaboration_pack: dict[str, Any],
    delivery_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(_tasks_from_review_action_plan(review_action_plan))
    candidates.extend(_tasks_from_collaboration_pack(collaboration_pack))
    candidates.extend(_tasks_from_delivery_bundle(delivery_bundle))
    candidates.extend(_tasks_from_project_status(project_dir, status))
    return _dedupe_tasks(candidates)


def _tasks_from_review_action_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for action in plan.get("actions", []) if isinstance(plan.get("actions", []), list) else []:
        if not isinstance(action, dict) or action.get("status") not in {None, "open"}:
            continue
        tasks.append(
            _task(
                source="review_action_plan",
                title=str(action.get("title") or action.get("source_check_id") or "Review action"),
                agent_id=str(action.get("role") or "next_agent"),
                priority=str(action.get("priority") or "P2"),
                command=str(action.get("command") or ""),
                requires_human_input=bool(action.get("requires_human_input")),
                details={"action_id": action.get("action_id"), "source_check_id": action.get("source_check_id")},
            )
        )
    return tasks


def _tasks_from_collaboration_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    role_checklists = pack.get("role_checklists", {})
    if not isinstance(role_checklists, dict):
        return tasks
    for role, checks in role_checklists.items():
        for check in checks if isinstance(checks, list) else []:
            if not isinstance(check, dict) or check.get("complete"):
                continue
            command = str(check.get("suggested_command") or "")
            tasks.append(
                _task(
                    source="collaboration_pack",
                    title=str(check.get("label") or "Collaboration follow-up"),
                    agent_id=_agent(role),
                    priority=_priority_for_command(command),
                    command=command,
                    requires_human_input=_requires_human(command),
                    details={"role": role},
                )
            )
    return tasks


def _tasks_from_delivery_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    if not bundle or bundle.get("status") in {"ready", "complete"}:
        return []
    command = str(bundle.get("top_command") or "")
    return [
        _task(
            source="delivery_bundle",
            title="Bring final delivery bundle to ready state.",
            agent_id="maintainer",
            priority="P0",
            command=command,
            requires_human_input=False,
            details={"missing_file_count": bundle.get("missing_file_count", 0)},
        )
    ]


def _tasks_from_project_status(project_dir: Path, status: dict[str, Any]) -> list[dict[str, Any]]:
    command = str(status.get("next_step") or "").removeprefix("Run: ").strip()
    coordination_commands = [
        "openrepro multi-agent-plan",
        "openrepro validate-multi-agent-plan",
        "openrepro agent-board",
        "openrepro agent-dispatch",
        "openrepro agent-exec-plan",
        "openrepro paper-lineage",
    ]
    if not command or command.startswith("Project v") or any(command.startswith(item) for item in coordination_commands):
        return []
    return [
        _task(
            source="project_status",
            title="Run the current project next step.",
            agent_id=_agent_for_command(command),
            priority=_priority_for_command(command),
            command=command or f"openrepro status {project_dir}",
            requires_human_input=_requires_human(command),
            details={"next_step": status.get("next_step")},
        )
    ]


def _dedupe_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for index, task in enumerate(sorted(tasks, key=_sort_key), start=1):
        key = (str(task.get("agent_id")), str(task.get("command") or task.get("title")))
        if key in seen:
            continue
        seen.add(key)
        task["task_id"] = f"M{len(unique) + 1:03d}"
        unique.append(task)
    return unique


def _sort_key(task: dict[str, Any]) -> tuple[int, int, str]:
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    agent_order = {"maintainer": 0, "reviewer": 1, "experimenter": 2, "next_agent": 3}
    return (
        priority_order.get(str(task.get("priority")), 9),
        agent_order.get(str(task.get("agent_id")), 9),
        str(task.get("title")),
    )


def _task(
    source: str,
    title: str,
    agent_id: str,
    priority: str,
    command: str,
    requires_human_input: bool,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task_id": "",
        "source": source,
        "title": title,
        "agent_id": _agent(agent_id),
        "priority": priority if priority in {"P0", "P1", "P2"} else "P2",
        "status": "open",
        "command": command or None,
        "requires_human_input": bool(requires_human_input),
        "details": details,
    }


def _handoff_order(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for agent in AGENT_ROSTER:
        agent_id = agent["agent_id"]
        agent_tasks = [task for task in tasks if task["agent_id"] == agent_id]
        rows.append(
            {
                "agent_id": agent_id,
                "task_count": len(agent_tasks),
                "first_task_id": agent_tasks[0]["task_id"] if agent_tasks else None,
                "first_command": agent_tasks[0]["command"] if agent_tasks else None,
            }
        )
    return sorted(rows, key=lambda item: (0 if item["task_count"] else 1, item["agent_id"]))


def _agent(value: Any) -> str:
    agent = str(value or "next_agent").strip().lower().replace("-", "_")
    if agent in {"maintainer", "reviewer", "experimenter", "next_agent"}:
        return agent
    return "next_agent"


def _agent_for_command(command: str) -> str:
    command = command.lower()
    if any(token in command for token in ["review", "claim-signoff", "readiness"]):
        return "reviewer"
    if any(token in command for token in ["experiment", "data", "quality-gate", "protocol", "gaps", "scorecard"]):
        return "experimenter"
    if any(token in command for token in ["refresh", "dashboard", "package", "handoff", "delivery", "report", "freshness"]):
        return "maintainer"
    return "next_agent"


def _priority_for_command(command: str) -> str:
    command = command.lower()
    if "<" in command or any(token in command for token in ["ingest", "review-decision", "claim-signoff"]):
        return "P0"
    if any(token in command for token in ["protocol", "gaps", "quality-gate", "refresh", "delivery"]):
        return "P1"
    return "P2"


def _requires_human(command: str) -> bool:
    command = command.lower()
    return "<" in command or "review-decision" in command or "claim-signoff" in command or "--reviewer" in command


def _dict(path: Path) -> dict[str, Any]:
    data = read_json(path, default={}) or {}
    return data if isinstance(data, dict) else {}


def _render_markdown(plan: dict[str, Any]) -> str:
    roster_rows = [
        "| Agent | Owns | Task count | First command |",
        "| --- | --- | --- | --- |",
    ]
    order = {item["agent_id"]: item for item in plan["handoff_order"]}
    for agent in plan["agent_roster"]:
        item = order.get(agent["agent_id"], {})
        roster_rows.append(
            "| {agent} | {owns} | {count} | `{command}` |".format(
                agent=_cell(agent["agent_id"]),
                owns=_cell(agent["owns"]),
                count=_cell(item.get("task_count", 0)),
                command=_cell(item.get("first_command")),
            )
        )
    task_rows = [
        "| Task | Priority | Agent | Source | Human input | Command | Title |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for task in plan["tasks"]:
        task_rows.append(
            "| {task_id} | {priority} | {agent} | {source} | {human} | `{command}` | {title} |".format(
                task_id=_cell(task["task_id"]),
                priority=_cell(task["priority"]),
                agent=_cell(task["agent_id"]),
                source=_cell(task["source"]),
                human=_cell(task["requires_human_input"]),
                command=_cell(task.get("command")),
                title=_cell(task["title"]),
            )
        )
    guardrails = "\n".join(f"- {item}" for item in plan["guardrails"])
    return f"""# Multi-Agent Plan

- schema_version: {plan['schema_version']}
- created_at: {plan['created_at']}
- project_name: {plan['project_name']}
- status: {plan['status']}
- agent_count: {plan['agent_count']}
- task_count: {plan['task_count']}
- open_task_count: {plan['open_task_count']}
- top_agent: {plan['top_agent']}
- top_command: {plan['top_command']}
- agent_task_counts: {plan['agent_task_counts']}
- priority_counts: {plan['priority_counts']}

## Agent Roster

{chr(10).join(roster_rows)}

## Tasks

{chr(10).join(task_rows)}

## Source

- project_next_step: {plan['source']['project_next_step']}
- review_action_plan_status: {plan['source']['review_action_plan_status']}
- review_action_plan_open_action_count: {plan['source']['review_action_plan_open_action_count']}
- collaboration_pack_status: {plan['source']['collaboration_pack_status']}
- collaboration_pack_next_safe_command_count: {plan['source']['collaboration_pack_next_safe_command_count']}
- delivery_bundle_status: {plan['source']['delivery_bundle_status']}
- delivery_bundle_missing_file_count: {plan['source']['delivery_bundle_missing_file_count']}

## Guardrails

{guardrails}

## Policy

{plan['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
