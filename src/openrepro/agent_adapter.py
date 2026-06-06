"""Externally supervised agent execution adapter specifications."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_exec_plan import generate_agent_exec_plan
from .artifact_manager import sha256_file
from .utils import iso_now, read_json, safe_write_text, write_json

AGENT_ADAPTER_SCHEMA_VERSION = "1.30.0"


def generate_agent_adapter(project_dir: Path, runner: str = "external-supervised", max_steps: int = 20) -> dict[str, Any]:
    """Write a supervised external-agent adapter spec without executing tasks."""
    project_dir = Path(project_dir)
    plan = generate_agent_exec_plan(project_dir, dry_run=True)
    safe_steps = plan.get("steps", []) if isinstance(plan.get("steps"), list) else []
    selected_steps = safe_steps[: max(0, int(max_steps))]
    adapter_steps = [_adapter_step(project_dir, runner, step, index) for index, step in enumerate(selected_steps, start=1)]
    blocked_tasks = plan.get("blocked_tasks", []) if isinstance(plan.get("blocked_tasks"), list) else []
    status = "ready" if adapter_steps and not blocked_tasks else "blocked" if blocked_tasks else "complete"
    adapter = {
        "schema_version": AGENT_ADAPTER_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": plan.get("project_name") or project_dir.name,
        "project_dir": str(project_dir),
        "runner": runner,
        "status": status,
        "max_steps": max_steps,
        "adapter_step_count": len(adapter_steps),
        "blocked_task_count": len(blocked_tasks),
        "source": {
            "agent_exec_plan_status": plan.get("status"),
            "agent_exec_plan_step_count": plan.get("safe_step_count"),
            "agent_exec_plan_blocked_task_count": plan.get("blocked_task_count"),
            "agent_exec_plan_sha256": sha256_file(project_dir / "workspace" / "agent_exec_plan.json")
            if (project_dir / "workspace" / "agent_exec_plan.json").exists()
            else None,
        },
        "steps": adapter_steps,
        "blocked_tasks": blocked_tasks,
        "guardrails": [
            "Adapter generation does not execute agents or commands.",
            "Every adapter step requires external supervision and approval.",
            "Experiment runs, repair apply, human decisions, and claim signoffs stay blocked.",
            "Trajectory logs record planned handoff events only until an external runner appends reviewed results.",
        ],
        "policy": "Agent adapters prepare externally supervised runner handoffs only; they do not execute tasks or claim reproduction success.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "agent_adapter.json", adapter)
    safe_write_text(workspace / "AGENT_ADAPTER.md", _render_markdown(adapter))
    safe_write_text(workspace / "agent_trajectory.jsonl", _trajectory_lines(adapter))
    return adapter


def validate_agent_adapter(project_dir: Path) -> dict[str, Any]:
    """Validate the supervised agent adapter spec."""
    project_dir = Path(project_dir)
    adapter_path = project_dir / "workspace" / "agent_adapter.json"
    adapter = read_json(adapter_path, default=None)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    if not isinstance(adapter, dict):
        result = _validation_result(project_dir, False, [f"Adapter not found or invalid: {adapter_path}"], [], [])
        _write_validation(project_dir, result)
        return result

    for step in adapter.get("steps", []) if isinstance(adapter.get("steps"), list) else []:
        step_id = step.get("adapter_step_id")
        approval_required = step.get("approval_required") is True
        external_mode = step.get("execution_mode") == "external_supervised"
        command = str(step.get("command") or "")
        forbidden = _command_forbidden(command)
        passed = approval_required and external_mode and not forbidden and not step.get("executed_at")
        if not passed:
            errors.append(f"Adapter step is not safely supervised: {step_id}")
        checks.append(
            {
                "name": f"adapter_step:{step_id}",
                "passed": passed,
                "approval_required": approval_required,
                "execution_mode": step.get("execution_mode"),
                "forbidden": forbidden,
            }
        )
    if adapter.get("runner") in {None, ""}:
        errors.append("Adapter runner is missing.")
    if adapter.get("blocked_tasks"):
        warnings.append("Adapter contains blocked tasks that require human resolution before supervised execution.")
    result = _validation_result(project_dir, not errors, errors, warnings, checks)
    _write_validation(project_dir, result)
    return result


def agent_adapter_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing adapter summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "agent_adapter.json"
    validation_path = project_dir / "workspace" / "agent_adapter_validation.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    validation = read_json(validation_path, default={}) or {}
    validation = validation if isinstance(validation, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(project_dir / "workspace" / "AGENT_ADAPTER.md") if path.exists() else None,
        "trajectory_path": str(project_dir / "workspace" / "agent_trajectory.jsonl")
        if (project_dir / "workspace" / "agent_trajectory.jsonl").exists()
        else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "adapter_step_count": int(data.get("adapter_step_count", 0) or 0),
        "blocked_task_count": int(data.get("blocked_task_count", 0) or 0),
        "validation_present": validation_path.exists(),
        "validation_valid": validation.get("valid") if validation else None,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _adapter_step(project_dir: Path, runner: str, step: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "adapter_step_id": f"A{index:03d}",
        "task_id": step.get("task_id"),
        "agent_id": step.get("agent_id"),
        "source_step_id": step.get("step_id"),
        "runner": runner,
        "cwd": str(project_dir),
        "command": step.get("command"),
        "command_name": step.get("command_name"),
        "approval_required": True,
        "execution_mode": "external_supervised",
        "status": "ready_for_supervised_runner",
        "expected_result_event": "external_runner_result",
        "notes": "External runner must append reviewed results to workspace/agent_trajectory.jsonl.",
    }


def _command_forbidden(command: str) -> bool:
    tokens = command.split()
    if not tokens:
        return True
    command_name = tokens[1] if tokens[0] == "openrepro" and len(tokens) > 1 else tokens[0]
    return command_name in {"run-experiment", "rerun-experiment", "repair", "claim-signoff", "review-decision"}


def _validation_result(
    project_dir: Path,
    valid: bool,
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": AGENT_ADAPTER_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "valid": valid,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "policy": "Adapter validation checks supervised handoff guardrails only.",
    }


def _write_validation(project_dir: Path, result: dict[str, Any]) -> None:
    write_json(project_dir / "workspace" / "agent_adapter_validation.json", result)
    safe_write_text(project_dir / "workspace" / "AGENT_ADAPTER_VALIDATION.md", _render_validation_markdown(result))


def _trajectory_lines(adapter: dict[str, Any]) -> str:
    events = [
        {
            "event": "adapter_generated",
            "created_at": adapter["created_at"],
            "runner": adapter["runner"],
            "adapter_step_count": adapter["adapter_step_count"],
            "blocked_task_count": adapter["blocked_task_count"],
        }
    ]
    for step in adapter["steps"]:
        events.append(
            {
                "event": "planned_external_step",
                "created_at": adapter["created_at"],
                "adapter_step_id": step["adapter_step_id"],
                "task_id": step.get("task_id"),
                "command": step.get("command"),
                "approval_required": True,
            }
        )
    return "\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events) + "\n"


def _render_markdown(adapter: dict[str, Any]) -> str:
    rows = [
        "| Step | Agent | Task | Runner | Command | Approval |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not adapter["steps"]:
        rows.append("| none |  |  |  |  | No supervised adapter steps. |")
    for step in adapter["steps"]:
        rows.append(
            "| {step_id} | {agent} | {task} | {runner} | `{command}` | {approval} |".format(
                step_id=_cell(step.get("adapter_step_id")),
                agent=_cell(step.get("agent_id")),
                task=_cell(step.get("task_id")),
                runner=_cell(step.get("runner")),
                command=_cell(step.get("command")),
                approval=_cell(step.get("approval_required")),
            )
        )
    blocked_rows = [
        "| Task | Agent | Command | Reason |",
        "| --- | --- | --- | --- |",
    ]
    if not adapter["blocked_tasks"]:
        blocked_rows.append("| none |  |  | No blocked tasks. |")
    for task in adapter["blocked_tasks"]:
        blocked_rows.append(
            "| {task} | {agent} | `{command}` | {reason} |".format(
                task=_cell(task.get("task_id")),
                agent=_cell(task.get("agent_id")),
                command=_cell(task.get("command")),
                reason=_cell(task.get("reason")),
            )
        )
    guardrails = "\n".join(f"- {item}" for item in adapter["guardrails"])
    return f"""# Agent Adapter

- schema_version: {adapter['schema_version']}
- created_at: {adapter['created_at']}
- project_name: {adapter['project_name']}
- runner: {adapter['runner']}
- status: {adapter['status']}
- adapter_step_count: {adapter['adapter_step_count']}
- blocked_task_count: {adapter['blocked_task_count']}

## Supervised Steps

{chr(10).join(rows)}

## Blocked Tasks

{chr(10).join(blocked_rows)}

## Guardrails

{guardrails}

## Policy

{adapter['policy']}
"""


def _render_validation_markdown(result: dict[str, Any]) -> str:
    rows = [
        "| Check | Passed |",
        "| --- | --- |",
    ]
    for check in result.get("checks", []):
        rows.append(f"| {check.get('name')} | {check.get('passed')} |")
    if not result.get("checks"):
        rows.append("| none |  |")
    lines = [
        "# Agent Adapter Validation",
        "",
        f"- valid: {result['valid']}",
        f"- errors: {result['error_count']}",
        f"- warnings: {result['warning_count']}",
        "",
        "## Checks",
        "",
        *rows,
    ]
    if result.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in result["errors"])
    if result.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in result["warnings"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return "" if value is None else str(value).replace("|", "\\|")
