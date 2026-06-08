"""Sandboxed execution for approved safe agent tasks."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .agent_exec_plan import SAFE_COMMANDS, generate_agent_exec_plan
from .utils import iso_now, local_timestamp_for_path, read_json, relpath, safe_write_text, write_json

AGENT_SANDBOX_SCHEMA_VERSION = "1.43.0"


def run_agent_sandbox(
    project_dir: Path,
    *,
    role: str | None = None,
    confirm: bool = False,
    approved: bool = False,
    max_steps: int = 1,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    """Run or dry-run approved safe agent execution-plan steps."""
    project_dir = Path(project_dir)
    run_id = local_timestamp_for_path()
    plan = _plan(project_dir)
    selected = _selected_steps(plan, role=role, max_steps=max_steps)
    logs_dir = project_dir / "workspace" / "agent_sandbox" / run_id
    trajectory_path = project_dir / "workspace" / "agent_sandbox_trajectory.jsonl"
    records = []
    _append_event(trajectory_path, _event(run_id, "sandbox_started", {"role": role, "confirm": confirm, "approved": approved}))
    for step in selected:
        record = _run_step(project_dir, logs_dir, run_id, step, confirm=confirm, approved=approved, trajectory_path=trajectory_path)
        records.append(record)
        if record["status"] in {"blocked", "failed"} and not continue_on_error:
            break
    result = _result(project_dir, run_id, role, confirm, approved, max_steps, continue_on_error, selected, records, logs_dir, trajectory_path)
    write_json(project_dir / "workspace" / "agent_sandbox_run.json", result)
    safe_write_text(project_dir / "workspace" / "AGENT_SANDBOX_RUN.md", _render_markdown(result))
    _append_event(trajectory_path, _event(run_id, "sandbox_finished", {"status": result["status"]}))
    return result


def agent_sandbox_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing agent sandbox summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "agent_sandbox_run.json"
    markdown_path = project_dir / "workspace" / "AGENT_SANDBOX_RUN.md"
    trajectory_path = project_dir / "workspace" / "agent_sandbox_trajectory.jsonl"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "trajectory_path": str(trajectory_path) if trajectory_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "selected_step_count": int(data.get("selected_step_count", 0) or 0),
        "passed_step_count": int(data.get("passed_step_count", 0) or 0),
        "blocked_step_count": int(data.get("blocked_step_count", 0) or 0),
        "failed_step_count": int(data.get("failed_step_count", 0) or 0),
    }


def _plan(project_dir: Path) -> dict[str, Any]:
    plan = read_json(Path(project_dir) / "workspace" / "agent_exec_plan.json", default={}) or {}
    if not isinstance(plan, dict) or not plan.get("steps"):
        plan = generate_agent_exec_plan(project_dir, dry_run=True)
    return plan if isinstance(plan, dict) else {}


def _selected_steps(plan: dict[str, Any], *, role: str | None, max_steps: int) -> list[dict[str, Any]]:
    steps = [step for step in plan.get("steps", []) if isinstance(step, dict)]
    if role:
        steps = [step for step in steps if step.get("agent_id") == role]
    return steps[: max(0, max_steps)]


def _run_step(
    project_dir: Path,
    logs_dir: Path,
    run_id: str,
    step: dict[str, Any],
    *,
    confirm: bool,
    approved: bool,
    trajectory_path: Path,
) -> dict[str, Any]:
    command_name = str(step.get("command_name") or _command_name(str(step.get("command") or "")))
    record = {
        "step_id": step.get("step_id"),
        "task_id": step.get("task_id"),
        "agent_id": step.get("agent_id"),
        "command": step.get("command"),
        "command_name": command_name,
        "started_at": iso_now(),
        "finished_at": None,
        "duration_seconds": 0.0,
        "status": "dry_run",
        "message": "Pass --confirm --approve to execute this safe sandbox step.",
        "stdout_path": None,
        "stderr_path": None,
    }
    _append_event(trajectory_path, _event(run_id, "step_started", {"step_id": step.get("step_id"), "command_name": command_name}))
    if command_name not in SAFE_COMMANDS:
        return _finish(record, "blocked", f"Command is not in safe allowlist: {command_name}", trajectory_path, run_id)
    action = _actions().get(command_name)
    if action is None:
        return _finish(record, "blocked", f"No sandbox action registered for command: {command_name}", trajectory_path, run_id)
    if not confirm:
        return _finish(record, "dry_run", "Pass --confirm --approve to execute this safe sandbox step.", trajectory_path, run_id)
    if not approved:
        return _finish(record, "blocked", "Sandbox execution requires --approve.", trajectory_path, run_id)

    stdout = io.StringIO()
    stderr = io.StringIO()
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{record['step_id']}.out"
    stderr_path = logs_dir / f"{record['step_id']}.err"
    started = perf_counter()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            action(project_dir)
    except Exception as exc:  # pragma: no cover - defensive reporting path
        safe_write_text(stdout_path, stdout.getvalue())
        safe_write_text(stderr_path, stderr.getvalue())
        record["stdout_path"] = relpath(stdout_path, project_dir).replace("\\", "/")
        record["stderr_path"] = relpath(stderr_path, project_dir).replace("\\", "/")
        record["duration_seconds"] = round(perf_counter() - started, 6)
        return _finish(record, "failed", str(exc), trajectory_path, run_id)
    safe_write_text(stdout_path, stdout.getvalue())
    safe_write_text(stderr_path, stderr.getvalue())
    record["stdout_path"] = relpath(stdout_path, project_dir).replace("\\", "/")
    record["stderr_path"] = relpath(stderr_path, project_dir).replace("\\", "/")
    record["duration_seconds"] = round(perf_counter() - started, 6)
    return _finish(record, "passed", "Sandbox step completed.", trajectory_path, run_id)


def _finish(record: dict[str, Any], status: str, message: str, trajectory_path: Path, run_id: str) -> dict[str, Any]:
    record["status"] = status
    record["message"] = message
    record["finished_at"] = iso_now()
    _append_event(trajectory_path, _event(run_id, "step_finished", {"step_id": record.get("step_id"), "status": status, "message": message}))
    return record


def _result(
    project_dir: Path,
    run_id: str,
    role: str | None,
    confirm: bool,
    approved: bool,
    max_steps: int,
    continue_on_error: bool,
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
    logs_dir: Path,
    trajectory_path: Path,
) -> dict[str, Any]:
    failed = [record for record in records if record["status"] == "failed"]
    blocked = [record for record in records if record["status"] == "blocked"]
    passed = [record for record in records if record["status"] == "passed"]
    dry_runs = [record for record in records if record["status"] == "dry_run"]
    return {
        "schema_version": AGENT_SANDBOX_SCHEMA_VERSION,
        "created_at": iso_now(),
        "run_id": run_id,
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "role": role,
        "confirmed": confirm,
        "approved": approved,
        "max_steps": max_steps,
        "continue_on_error": continue_on_error,
        "status": "failed" if failed else "blocked" if blocked else "dry_run" if dry_runs and not confirm else "complete",
        "selected_step_count": len(selected),
        "recorded_step_count": len(records),
        "passed_step_count": len(passed),
        "blocked_step_count": len(blocked),
        "failed_step_count": len(failed),
        "dry_run_step_count": len(dry_runs),
        "logs_dir": relpath(logs_dir, project_dir).replace("\\", "/"),
        "trajectory_path": relpath(trajectory_path, project_dir).replace("\\", "/"),
        "steps": records,
        "safe_commands": sorted(SAFE_COMMANDS),
        "guardrails": [
            "Sandbox execution is dry-run unless --confirm and --approve are both passed.",
            "Only commands already classified by the agent execution plan safe allowlist can run.",
            "Experiments, repair apply, human decisions, and claim signoffs remain blocked.",
        ],
        "policy": "Agent sandbox runs approved safe derived-artifact commands only; it does not autonomously reproduce papers.",
    }


def _actions() -> dict[str, Callable[[Path], Any]]:
    from .agent_board import generate_agent_board
    from .agent_dispatch import generate_agent_dispatch
    from .agent_exec_plan import generate_agent_exec_plan
    from .collaboration_pack import generate_collaboration_pack
    from .dashboard import generate_dashboard
    from .delivery_bundle import generate_delivery_bundle
    from .evidence_package import generate_evidence_package
    from .freshness import generate_artifact_freshness
    from .handoff_generator import generate_handoff
    from .multi_agent_plan import generate_multi_agent_plan
    from .multi_agent_plan_validation import validate_multi_agent_plan
    from .readiness_review import generate_readiness_review
    from .readiness_review_validation import validate_readiness_review
    from .refresh import generate_refresh_run
    from .report_generator import generate_report
    from .review_action_plan import generate_review_action_plan
    from .review_site import generate_review_site

    return {
        "report": generate_report,
        "handoff": generate_handoff,
        "evidence-package": generate_evidence_package,
        "review-site": generate_review_site,
        "collaboration-pack": generate_collaboration_pack,
        "refresh": generate_refresh_run,
        "freshness": generate_artifact_freshness,
        "dashboard": generate_dashboard,
        "readiness-review": generate_readiness_review,
        "validate-readiness-review": validate_readiness_review,
        "review-action-plan": generate_review_action_plan,
        "delivery-bundle": generate_delivery_bundle,
        "multi-agent-plan": generate_multi_agent_plan,
        "validate-multi-agent-plan": validate_multi_agent_plan,
        "agent-board": generate_agent_board,
        "agent-dispatch": generate_agent_dispatch,
        "agent-exec-plan": lambda project_dir: generate_agent_exec_plan(project_dir, dry_run=True),
    }


def _command_name(command: str) -> str:
    tokens = command.split()
    if not tokens:
        return ""
    if tokens[0] == "openrepro" and len(tokens) >= 2:
        return tokens[1]
    return tokens[0]


def _append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _event(run_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": AGENT_SANDBOX_SCHEMA_VERSION,
        "created_at": iso_now(),
        "run_id": run_id,
        "event_type": event_type,
        "payload": payload,
    }


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Agent Sandbox Run",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- run_id: {result['run_id']}",
        f"- status: {result['status']}",
        f"- role: {result['role']}",
        f"- confirmed: {result['confirmed']}",
        f"- approved: {result['approved']}",
        f"- selected_step_count: {result['selected_step_count']}",
        f"- passed_step_count: {result['passed_step_count']}",
        f"- blocked_step_count: {result['blocked_step_count']}",
        f"- failed_step_count: {result['failed_step_count']}",
        f"- logs_dir: `{result['logs_dir']}`",
        f"- trajectory_path: `{result['trajectory_path']}`",
        "",
        "## Steps",
        "",
        "| Step | Agent | Command | Status | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in result["steps"]:
        lines.append(f"| {_cell(step.get('step_id'))} | {_cell(step.get('agent_id'))} | `{_cell(step.get('command'))}` | {_cell(step.get('status'))} | {_cell(step.get('message'))} |")
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in result["guardrails"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
