"""Per-agent task dispatch pack generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .multi_agent_plan import AGENT_ROSTER, generate_multi_agent_plan
from .multi_agent_plan_validation import validate_multi_agent_plan
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

AGENT_DISPATCH_SCHEMA_VERSION = "1.24.1"


def generate_agent_dispatch(project_dir: Path) -> dict[str, Any]:
    """Write workspace/agent_dispatch.json, Markdown, and per-agent task files."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    plan = _plan(project_dir)
    validation = _validation(project_dir)
    agents = _agents(project_dir, plan)
    status, top_command = _dispatch_status(project_dir, plan, validation)
    dispatch = {
        "schema_version": AGENT_DISPATCH_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": plan.get("project_name") or project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": top_command,
        "agent_count": len(agents),
        "task_count": int(plan.get("task_count", 0) or 0),
        "open_task_count": int(plan.get("open_task_count", 0) or 0),
        "human_input_task_count": sum(agent["human_input_task_count"] for agent in agents),
        "validation_status": validation.get("status", "missing"),
        "validation_issue_count": int(validation.get("issue_count", 0) or 0),
        "agents": agents,
        "source": {
            "multi_agent_plan_status": plan.get("status"),
            "multi_agent_plan_task_count": plan.get("task_count", 0),
            "multi_agent_plan_top_command": plan.get("top_command"),
            "multi_agent_plan_validation_status": validation.get("status", "missing"),
            "multi_agent_plan_validation_issue_count": validation.get("issue_count", 0),
        },
        "guardrails": [
            "Does not execute agent tasks.",
            "Does not run experiments.",
            "Does not create or close human review decisions.",
            "Does not add claim signoffs.",
            "Does not fabricate missing scientific artifacts.",
        ],
        "policy": "Agent dispatch packs split guarded tasks into per-role instructions only; they do not dispatch or execute agents.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "agent_dispatch.json", dispatch)
    safe_write_text(workspace / "AGENT_DISPATCH.md", _render_markdown(dispatch))
    for agent in agents:
        path = project_dir / str(agent["tasks_markdown_path"])
        safe_write_text(path, _render_agent_tasks(dispatch, agent))
        agent["tasks_markdown_sha256"] = sha256_file(path)
    write_json(workspace / "agent_dispatch.json", dispatch)
    safe_write_text(workspace / "AGENT_DISPATCH.md", _render_markdown(dispatch))
    return dispatch


def agent_dispatch_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing dispatch summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "agent_dispatch.json"
    markdown_path = project_dir / "workspace" / "AGENT_DISPATCH.md"
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
        "human_input_task_count": int(data.get("human_input_task_count", 0) or 0),
        "validation_status": data.get("validation_status", "missing" if not path.exists() else None),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _plan(project_dir: Path) -> dict[str, Any]:
    plan = read_json(project_dir / "workspace" / "multi_agent_plan.json", default={}) or {}
    if not isinstance(plan, dict) or not plan:
        plan = generate_multi_agent_plan(project_dir)
    return plan


def _validation(project_dir: Path) -> dict[str, Any]:
    validation = read_json(project_dir / "workspace" / "multi_agent_plan_validation.json", default={}) or {}
    if not isinstance(validation, dict) or not validation:
        validation = validate_multi_agent_plan(project_dir)
    return validation


def _dispatch_status(project_dir: Path, plan: dict[str, Any], validation: dict[str, Any]) -> tuple[str, str | None]:
    if validation.get("status") != "passed":
        command = validation.get("top_command") or f"openrepro validate-multi-agent-plan {project_dir}"
        return "needs_validation", str(command)
    if plan.get("status") == "complete":
        return "complete", None
    return "ready", plan.get("top_command")


def _agents(project_dir: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = [task for task in plan.get("tasks", []) if isinstance(task, dict)]
    agents: list[dict[str, Any]] = []
    for agent in AGENT_ROSTER:
        agent_id = agent["agent_id"]
        agent_tasks = [task for task in tasks if task.get("agent_id") == agent_id]
        tasks_path = project_dir / "workspace" / "agents" / agent_id / "TASKS.md"
        agents.append(
            {
                "agent_id": agent_id,
                "label": agent["label"],
                "owns": agent["owns"],
                "task_count": len(agent_tasks),
                "open_task_count": sum(1 for task in agent_tasks if task.get("status") == "open"),
                "human_input_task_count": sum(1 for task in agent_tasks if task.get("requires_human_input")),
                "first_command": agent_tasks[0].get("command") if agent_tasks else None,
                "tasks_markdown_path": relpath(tasks_path, project_dir),
                "tasks_markdown_sha256": None,
                "tasks": agent_tasks,
            }
        )
    return agents


def _render_markdown(dispatch: dict[str, Any]) -> str:
    rows = [
        "| Agent | Tasks | Human input | First command | Task file |",
        "| --- | --- | --- | --- | --- |",
    ]
    for agent in dispatch["agents"]:
        rows.append(
            "| {agent} | {tasks} | {human} | `{command}` | `{path}` |".format(
                agent=_cell(agent["agent_id"]),
                tasks=_cell(agent["task_count"]),
                human=_cell(agent["human_input_task_count"]),
                command=_cell(agent.get("first_command")),
                path=_cell(agent["tasks_markdown_path"]),
            )
        )
    guardrails = "\n".join(f"- {item}" for item in dispatch["guardrails"])
    return f"""# Agent Dispatch Pack

- schema_version: {dispatch['schema_version']}
- created_at: {dispatch['created_at']}
- project_name: {dispatch['project_name']}
- status: {dispatch['status']}
- task_count: {dispatch['task_count']}
- open_task_count: {dispatch['open_task_count']}
- human_input_task_count: {dispatch['human_input_task_count']}
- validation_status: {dispatch['validation_status']}
- top_command: {dispatch['top_command']}

## Agents

{chr(10).join(rows)}

## Guardrails

{guardrails}

## Policy

{dispatch['policy']}
"""


def _render_agent_tasks(dispatch: dict[str, Any], agent: dict[str, Any]) -> str:
    rows = [
        "| Task | Priority | Source | Human input | Command | Title |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in agent["tasks"]:
        rows.append(
            "| {task_id} | {priority} | {source} | {human} | `{command}` | {title} |".format(
                task_id=_cell(task.get("task_id")),
                priority=_cell(task.get("priority")),
                source=_cell(task.get("source")),
                human=_cell(task.get("requires_human_input")),
                command=_cell(task.get("command")),
                title=_cell(task.get("title")),
            )
        )
    if not agent["tasks"]:
        rows.append("| none |  |  |  |  | No open tasks. |")
    return f"""# {agent['label']} Tasks

- dispatch_schema_version: {dispatch['schema_version']}
- dispatch_status: {dispatch['status']}
- agent_id: {agent['agent_id']}
- owns: {agent['owns']}
- task_count: {agent['task_count']}
- open_task_count: {agent['open_task_count']}
- human_input_task_count: {agent['human_input_task_count']}

## Tasks

{chr(10).join(rows)}

## Guardrails

- Do not execute task commands automatically.
- Do not run experiments.
- Do not close review decisions or add claim signoffs.
- Treat commands with placeholders as requiring human input.
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
