"""Runner-neutral supervised agent task specifications."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_dispatch import generate_agent_dispatch
from .agent_exec_plan import generate_agent_exec_plan
from .artifact_manager import sha256_file
from .evidence_graph import generate_evidence_graph
from .utils import iso_now, read_json, safe_write_text, write_json

AGENT_TASK_SPEC_SCHEMA_VERSION = "1.58.0"


def generate_agent_task_spec(project_dir: Path, max_tasks: int = 20, refresh_evidence_graph: bool = True) -> dict[str, Any]:
    """Write a supervised, runner-neutral task contract for external agents."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    evidence_graph = generate_evidence_graph(project_dir) if refresh_evidence_graph else _load_existing_evidence_graph(project_dir)
    dispatch = generate_agent_dispatch(project_dir)
    exec_plan = generate_agent_exec_plan(project_dir, dry_run=True)
    task_contracts = _task_contracts(project_dir, evidence_graph, dispatch, exec_plan, max_tasks=max_tasks)
    blocked = [task for task in task_contracts if task["status"] == "blocked"]
    human_input = [task for task in task_contracts if task["requires_human_input"]]
    runnable = [task for task in task_contracts if task["status"] == "ready_for_supervised_runner"]
    status = "blocked" if blocked else "ready" if runnable else "complete"
    spec = {
        "schema_version": AGENT_TASK_SPEC_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": runnable[0]["command"] if runnable else blocked[0]["command"] if blocked else None,
        "max_tasks": int(max_tasks),
        "task_contract_count": len(task_contracts),
        "ready_task_count": len(runnable),
        "blocked_task_count": len(blocked),
        "human_input_task_count": len(human_input),
        "input_artifacts": _input_artifacts(project_dir),
        "result_contract": _result_contract(project_dir),
        "tasks": task_contracts,
        "source": {
            "evidence_graph_status": evidence_graph.get("status"),
            "evidence_graph_node_count": evidence_graph.get("node_count"),
            "evidence_graph_sha256": sha256_file(project_dir / "workspace" / "evidence_graph.json"),
            "agent_dispatch_status": dispatch.get("status"),
            "agent_dispatch_task_count": dispatch.get("task_count"),
            "agent_dispatch_sha256": sha256_file(project_dir / "workspace" / "agent_dispatch.json"),
            "agent_exec_plan_status": exec_plan.get("status"),
            "agent_exec_plan_safe_step_count": exec_plan.get("safe_step_count"),
            "agent_exec_plan_blocked_task_count": exec_plan.get("blocked_task_count"),
            "agent_exec_plan_sha256": sha256_file(project_dir / "workspace" / "agent_exec_plan.json"),
        },
        "guardrails": [
            "Does not execute agents or commands.",
            "Every task result must be appended as reviewed evidence, not treated as automatic acceptance.",
            "Human-input tasks stay blocked until a reviewer supplies missing values or approvals.",
            "Experiment runs, repairs, review decisions, and claim signoffs require explicit user commands.",
            "Agent output must cite artifact paths and evidence graph node ids when available.",
        ],
        "policy": "Agent task specs define supervised task contracts only; they do not execute work or claim scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "agent_task_spec.json", spec)
    safe_write_text(project_dir / "workspace" / "AGENT_TASK_SPEC.md", _render_markdown(spec))
    write_json(project_dir / "workspace" / "agent_result_schema.json", _result_schema(spec))
    return spec


def _load_existing_evidence_graph(project_dir: Path) -> dict[str, Any]:
    graph = read_json(project_dir / "workspace" / "evidence_graph.json", default={}) or {}
    if isinstance(graph, dict) and isinstance(graph.get("nodes"), list):
        return graph
    return generate_evidence_graph(project_dir)


def agent_task_spec_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing agent task spec summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "agent_task_spec.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(project_dir / "workspace" / "AGENT_TASK_SPEC.md") if path.exists() else None,
        "result_schema_path": str(project_dir / "workspace" / "agent_result_schema.json")
        if (project_dir / "workspace" / "agent_result_schema.json").exists()
        else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "task_contract_count": int(data.get("task_contract_count", 0) or 0),
        "ready_task_count": int(data.get("ready_task_count", 0) or 0),
        "blocked_task_count": int(data.get("blocked_task_count", 0) or 0),
        "human_input_task_count": int(data.get("human_input_task_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _task_contracts(
    project_dir: Path,
    evidence_graph: dict[str, Any],
    dispatch: dict[str, Any],
    exec_plan: dict[str, Any],
    max_tasks: int,
) -> list[dict[str, Any]]:
    safe_by_task = {str(step.get("task_id")): step for step in exec_plan.get("steps", []) if isinstance(step, dict)}
    blocked_by_task = {str(task.get("task_id")): task for task in exec_plan.get("blocked_tasks", []) if isinstance(task, dict)}
    graph_focus = _graph_focus(evidence_graph)
    tasks: list[dict[str, Any]] = []
    for task in _dispatch_tasks(dispatch)[: max(0, int(max_tasks))]:
        task_id = str(task.get("task_id") or f"T{len(tasks) + 1:03d}")
        safe_step = safe_by_task.get(task_id)
        blocked = blocked_by_task.get(task_id)
        status = "ready_for_supervised_runner" if safe_step else "blocked" if blocked else "requires_review"
        tasks.append(
            {
                "task_spec_id": f"ATS{len(tasks) + 1:03d}",
                "task_id": task_id,
                "agent_id": task.get("agent_id"),
                "title": task.get("title"),
                "source": task.get("source"),
                "priority": task.get("priority"),
                "status": status,
                "command": task.get("command"),
                "command_name": safe_step.get("command_name") if safe_step else _command_name(str(task.get("command") or "")),
                "requires_human_input": bool(task.get("requires_human_input")) or bool(blocked),
                "blocked_reason": blocked.get("reason") if blocked else None,
                "execution_mode": "external_supervised",
                "input_refs": _input_refs(project_dir),
                "evidence_graph_focus": graph_focus,
                "expected_outputs": [
                    "agent_result event appended to workspace/agent_results.jsonl",
                    "artifact paths listed for every file created or updated",
                    "evidence graph node ids referenced when the task touches claims, data, experiments, or runs",
                ],
                "allowed_actions": [
                    "inspect listed artifacts",
                    "propose patches or commands for human review",
                    "write reviewed derived artifacts only through explicit OpenRepro commands",
                ],
                "blocked_actions": [
                    "run experiments without explicit confirmation",
                    "record review decisions or claim signoffs",
                    "fabricate data, metrics, claims, or successful execution evidence",
                    "store secrets or API keys in project files",
                ],
                "details": task.get("details", {}),
            }
        )
    return tasks


def _dispatch_tasks(dispatch: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for agent in dispatch.get("agents", []) if isinstance(dispatch.get("agents"), list) else []:
        if not isinstance(agent, dict):
            continue
        for task in agent.get("tasks", []) if isinstance(agent.get("tasks"), list) else []:
            if isinstance(task, dict):
                tasks.append({**task, "agent_id": task.get("agent_id") or agent.get("agent_id")})
    return tasks


def _graph_focus(evidence_graph: dict[str, Any]) -> dict[str, Any]:
    nodes = evidence_graph.get("nodes", []) if isinstance(evidence_graph.get("nodes"), list) else []
    focus = {
        "claim_node_ids": [],
        "data_node_ids": [],
        "experiment_node_ids": [],
        "run_node_ids": [],
    }
    for node in nodes:
        if not isinstance(node, dict) or not node.get("node_id"):
            continue
        kind = node.get("kind")
        key = f"{kind}_node_ids"
        if key in focus and len(focus[key]) < 12:
            focus[key].append(node["node_id"])
    return focus


def _input_artifacts(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "workspace" / "evidence_graph.json",
        project_dir / "workspace" / "agent_dispatch.json",
        project_dir / "workspace" / "agent_exec_plan.json",
        project_dir / "workspace" / "review_board.json",
        project_dir / "workspace" / "claim_trace.json",
        project_dir / "reports" / "evidence_package.json",
    ]
    return [
        {
            "path": str(path),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        }
        for path in paths
    ]


def _input_refs(project_dir: Path) -> list[str]:
    return [
        str(project_dir / "workspace" / "evidence_graph.json"),
        str(project_dir / "workspace" / "agent_dispatch.json"),
        str(project_dir / "workspace" / "agent_exec_plan.json"),
    ]


def _result_contract(project_dir: Path) -> dict[str, Any]:
    return {
        "event_log": str(project_dir / "workspace" / "agent_results.jsonl"),
        "required_fields": [
            "event",
            "created_at",
            "task_spec_id",
            "task_id",
            "agent_id",
            "status",
            "summary",
            "artifacts_written",
            "commands_run",
            "evidence_graph_node_ids",
            "requires_human_review",
            "policy_acknowledged",
        ],
        "allowed_statuses": ["completed", "blocked", "needs_human_review", "failed"],
        "policy_acknowledgement": "Result events are workflow evidence only and do not prove scientific reproduction.",
    }


def _result_schema(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": spec["schema_version"],
        "type": "object",
        "required": spec["result_contract"]["required_fields"],
        "properties": {
            "event": {"type": "string", "const": "agent_result"},
            "created_at": {"type": "string"},
            "task_spec_id": {"type": "string"},
            "task_id": {"type": "string"},
            "agent_id": {"type": "string"},
            "status": {"type": "string", "enum": spec["result_contract"]["allowed_statuses"]},
            "summary": {"type": "string"},
            "artifacts_written": {"type": "array", "items": {"type": "string"}},
            "commands_run": {"type": "array", "items": {"type": "string"}},
            "evidence_graph_node_ids": {"type": "array", "items": {"type": "string"}},
            "requires_human_review": {"type": "boolean"},
            "policy_acknowledged": {"type": "boolean"},
        },
        "additionalProperties": True,
    }


def _command_name(command: str) -> str:
    tokens = command.split()
    if not tokens:
        return ""
    if tokens[0] == "openrepro" and len(tokens) > 1:
        return tokens[1]
    return tokens[0]


def _render_markdown(spec: dict[str, Any]) -> str:
    task_rows = [
        "| Spec | Agent | Status | Priority | Command | Blocked reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not spec["tasks"]:
        task_rows.append("| none |  | complete |  |  | No open task contracts. |")
    for task in spec["tasks"]:
        task_rows.append(
            "| {spec_id} | {agent} | {status} | {priority} | `{command}` | {reason} |".format(
                spec_id=_cell(task.get("task_spec_id")),
                agent=_cell(task.get("agent_id")),
                status=_cell(task.get("status")),
                priority=_cell(task.get("priority")),
                command=_cell(task.get("command")),
                reason=_cell(task.get("blocked_reason")),
            )
        )
    artifact_rows = [
        "| Artifact | Present | SHA-256 |",
        "| --- | --- | --- |",
    ]
    for artifact in spec["input_artifacts"]:
        artifact_rows.append(
            f"| {_cell(artifact['path'])} | {_cell(artifact['present'])} | {_cell(artifact.get('sha256'))} |"
        )
    guardrails = "\n".join(f"- {item}" for item in spec["guardrails"])
    return f"""# Agent Task Spec

- schema_version: {spec['schema_version']}
- status: {spec['status']}
- task_contract_count: {spec['task_contract_count']}
- ready_task_count: {spec['ready_task_count']}
- blocked_task_count: {spec['blocked_task_count']}
- human_input_task_count: {spec['human_input_task_count']}
- top_command: {spec['top_command']}

## Task Contracts

{chr(10).join(task_rows)}

## Input Artifacts

{chr(10).join(artifact_rows)}

## Result Contract

- event_log: `{spec['result_contract']['event_log']}`
- required_fields: {', '.join(spec['result_contract']['required_fields'])}
- allowed_statuses: {', '.join(spec['result_contract']['allowed_statuses'])}

## Guardrails

{guardrails}

## Policy

{spec['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value).replace("|", "/")
    return str(value).replace("\n", " ").replace("|", "/")
