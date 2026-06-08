"""Workflow execution sessions with resumable event logs."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .artifact_manager import sha256_file
from .utils import iso_now, local_timestamp_for_path, relpath, safe_write_text, write_json
from .workflow_preset import generate_workflow_preset
from .workflow_registry import build_workflow_state, generate_workflow_state
from .workflow_registry import _workflow_actions

WORKFLOW_EXECUTOR_SCHEMA_VERSION = "1.40.0"


def execute_workflow(
    project_dir: Path,
    *,
    preset: str = "delivery",
    step_id: str | None = None,
    confirm: bool = False,
    retry_count: int = 0,
    max_steps: int | None = None,
    continue_on_error: bool = False,
    export_zip: bool = False,
) -> dict[str, Any]:
    """Execute or dry-run safe workflow steps with durable events and logs."""
    project_dir = Path(project_dir)
    execution_id = local_timestamp_for_path()
    workspace = project_dir / "workspace"
    logs_dir = workspace / "workflow_logs" / execution_id
    events_path = workspace / "workflow_events.jsonl"
    selected = _selected_steps(project_dir, preset=preset, step_id=step_id, max_steps=max_steps)
    actions = _workflow_actions(export_zip=export_zip)
    records: list[dict[str, Any]] = []
    _append_event(events_path, _event(execution_id, "execution_started", {"preset": preset, "step_id": step_id, "confirm": confirm}))

    for step in selected:
        record = _execute_step(
            project_dir,
            logs_dir,
            execution_id,
            step,
            actions.get(step["step_id"]),
            confirm=confirm,
            retry_count=retry_count,
            export_zip=export_zip,
            events_path=events_path,
        )
        records.append(record)
        if record["status"] in {"failed", "blocked"} and not continue_on_error:
            break
        if record["status"] == "passed":
            generate_workflow_state(project_dir)

    result = _execution_result(
        project_dir,
        execution_id,
        preset=preset,
        step_id=step_id,
        confirm=confirm,
        retry_count=retry_count,
        max_steps=max_steps,
        continue_on_error=continue_on_error,
        export_zip=export_zip,
        selected=selected,
        records=records,
        events_path=events_path,
        logs_dir=logs_dir,
    )
    write_json(workspace / "workflow_execution.json", result)
    safe_write_text(workspace / "WORKFLOW_EXECUTION.md", _render_markdown(result))
    _append_event(events_path, _event(execution_id, "execution_finished", {"status": result["status"]}))
    return result


def workflow_execution_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing workflow execution summary without mutating files."""
    from .utils import read_json

    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "workflow_execution.json"
    markdown_path = project_dir / "workspace" / "WORKFLOW_EXECUTION.md"
    events_path = project_dir / "workspace" / "workflow_events.jsonl"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "events_path": str(events_path) if events_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "selected_step_count": int(data.get("selected_step_count", 0) or 0),
        "passed_step_count": int(data.get("passed_step_count", 0) or 0),
        "blocked_step_count": int(data.get("blocked_step_count", 0) or 0),
        "failed_step_count": int(data.get("failed_step_count", 0) or 0),
        "top_failed_step": data.get("top_failed_step"),
        "top_blocked_step": data.get("top_blocked_step"),
    }


def _selected_steps(project_dir: Path, *, preset: str, step_id: str | None, max_steps: int | None) -> list[dict[str, Any]]:
    if step_id:
        state = build_workflow_state(project_dir)
        steps = [step for step in state["steps"] if step.get("step_id") == step_id]
        if not steps:
            raise ValueError(f"Unknown workflow step: {step_id}")
    else:
        plan = generate_workflow_preset(project_dir, preset=preset, runnable_only=False)
        steps = list(plan.get("steps", []))
    if max_steps is not None and max_steps >= 0:
        steps = steps[:max_steps]
    return steps


def _execute_step(
    project_dir: Path,
    logs_dir: Path,
    execution_id: str,
    step: dict[str, Any],
    action: Callable[[Path], Any] | None,
    *,
    confirm: bool,
    retry_count: int,
    export_zip: bool,
    events_path: Path,
) -> dict[str, Any]:
    current = _current_step(project_dir, step)
    step_id = str(current["step_id"])
    started_at = iso_now()
    before_outputs = _output_records(project_dir, current.get("outputs", []))
    base = {
        "step_id": step_id,
        "title": current.get("title"),
        "command": current.get("command"),
        "safe": current.get("safe"),
        "execution": current.get("execution"),
        "started_at": started_at,
        "finished_at": started_at,
        "duration_seconds": 0.0,
        "attempt_count": 0,
        "export_zip": export_zip,
        "before_outputs": before_outputs,
        "after_outputs": before_outputs,
        "changed_outputs": [],
        "stdout_path": None,
        "stderr_path": None,
    }
    _append_event(events_path, _event(execution_id, "step_started", {"step_id": step_id, "status": current.get("status")}))

    if current.get("status") == "complete":
        return _finished(base, "skipped", "Step outputs are already present.", events_path, execution_id)
    if current.get("missing_dependencies"):
        return _finished(base, "blocked", "Missing dependencies: " + ", ".join(current["missing_dependencies"]), events_path, execution_id)
    if not current.get("safe"):
        return _finished(base, "blocked", "Step is not safe for workflow-managed execution.", events_path, execution_id)
    if action is None:
        return _finished(base, "blocked", "No workflow-managed action is registered for this step.", events_path, execution_id)
    if not confirm:
        return _finished(base, "dry_run", "Pass --confirm to execute this safe derived step.", events_path, execution_id)

    attempts = max(1, retry_count + 1)
    errors: list[str] = []
    started = perf_counter()
    for attempt in range(1, attempts + 1):
        stdout = io.StringIO()
        stderr = io.StringIO()
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{step_id}_{attempt}.out"
        stderr_path = logs_dir / f"{step_id}_{attempt}.err"
        _append_event(events_path, _event(execution_id, "step_attempt_started", {"step_id": step_id, "attempt": attempt}))
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                action(project_dir)
        except Exception as exc:  # pragma: no cover - defensive reporting path
            errors.append(str(exc))
            safe_write_text(stdout_path, stdout.getvalue())
            safe_write_text(stderr_path, stderr.getvalue())
            _append_event(events_path, _event(execution_id, "step_attempt_failed", {"step_id": step_id, "attempt": attempt, "error": str(exc)}))
        else:
            safe_write_text(stdout_path, stdout.getvalue())
            safe_write_text(stderr_path, stderr.getvalue())
            base["attempt_count"] = attempt
            base["stdout_path"] = relpath(stdout_path, project_dir).replace("\\", "/")
            base["stderr_path"] = relpath(stderr_path, project_dir).replace("\\", "/")
            after_outputs = _output_records(project_dir, current.get("outputs", []))
            base["after_outputs"] = after_outputs
            base["changed_outputs"] = _changed_outputs(before_outputs, after_outputs)
            base["duration_seconds"] = round(perf_counter() - started, 6)
            return _finished(base, "passed", "Step completed.", events_path, execution_id)
    base["attempt_count"] = attempts
    base["duration_seconds"] = round(perf_counter() - started, 6)
    if errors:
        base["error"] = errors[-1]
    return _finished(base, "failed", errors[-1] if errors else "Step failed.", events_path, execution_id)


def _current_step(project_dir: Path, step: dict[str, Any]) -> dict[str, Any]:
    step_id = str(step.get("step_id"))
    state = build_workflow_state(project_dir)
    for current in state["steps"]:
        if current.get("step_id") == step_id:
            return current
    return step


def _finished(
    record: dict[str, Any],
    status: str,
    message: str,
    events_path: Path,
    execution_id: str,
) -> dict[str, Any]:
    record["status"] = status
    record["message"] = message
    record["finished_at"] = iso_now()
    _append_event(events_path, _event(execution_id, "step_finished", {"step_id": record["step_id"], "status": status, "message": message}))
    return record


def _execution_result(
    project_dir: Path,
    execution_id: str,
    *,
    preset: str,
    step_id: str | None,
    confirm: bool,
    retry_count: int,
    max_steps: int | None,
    continue_on_error: bool,
    export_zip: bool,
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
    events_path: Path,
    logs_dir: Path,
) -> dict[str, Any]:
    failed = [record for record in records if record["status"] == "failed"]
    blocked = [record for record in records if record["status"] == "blocked"]
    passed = [record for record in records if record["status"] == "passed"]
    dry_runs = [record for record in records if record["status"] == "dry_run"]
    skipped = [record for record in records if record["status"] == "skipped"]
    return {
        "schema_version": WORKFLOW_EXECUTOR_SCHEMA_VERSION,
        "created_at": iso_now(),
        "execution_id": execution_id,
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "preset": preset,
        "step_id": step_id,
        "confirmed": confirm,
        "retry_count": retry_count,
        "max_steps": max_steps,
        "continue_on_error": continue_on_error,
        "export_zip": export_zip,
        "status": "failed" if failed else "blocked" if blocked else "dry_run" if dry_runs and not confirm else "complete",
        "selected_step_count": len(selected),
        "recorded_step_count": len(records),
        "passed_step_count": len(passed),
        "blocked_step_count": len(blocked),
        "failed_step_count": len(failed),
        "dry_run_step_count": len(dry_runs),
        "skipped_step_count": len(skipped),
        "top_failed_step": failed[0]["step_id"] if failed else None,
        "top_blocked_step": blocked[0]["step_id"] if blocked else None,
        "events_path": relpath(events_path, project_dir).replace("\\", "/"),
        "logs_dir": relpath(logs_dir, project_dir).replace("\\", "/"),
        "steps": records,
        "guardrails": [
            "Only safe derived workflow steps execute through the workflow executor.",
            "Unsafe source input, human decisions, repair apply, and experiment execution remain explicit commands.",
            "Each execution writes durable JSON, Markdown, JSONL events, step logs, and declared output hashes.",
        ],
        "policy": "Workflow execution automates project artifact refreshes only; it does not prove scientific reproduction.",
    }


def _output_records(project_dir: Path, patterns: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for pattern in patterns:
        matched = _matched_paths(project_dir, pattern)
        if not matched:
            records.append({"pattern": pattern, "path": None, "present": False, "size_bytes": None, "sha256": None})
        for path in matched:
            records.append(
                {
                    "pattern": pattern,
                    "path": relpath(path, project_dir).replace("\\", "/"),
                    "present": path.exists() and path.is_file(),
                    "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
                    "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
                }
            )
    return records


def _matched_paths(project_dir: Path, pattern: str) -> list[Path]:
    if any(char in pattern for char in "*?["):
        return sorted((path for path in project_dir.glob(pattern) if path.is_file()), key=lambda item: item.as_posix())
    path = project_dir / pattern
    return [path] if path.exists() else []


def _changed_outputs(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    before_by_path = {str(item.get("path") or item.get("pattern")): item for item in before}
    changed = []
    for item in after:
        key = str(item.get("path") or item.get("pattern"))
        previous = before_by_path.get(key, {})
        if previous.get("sha256") != item.get("sha256") or previous.get("present") != item.get("present"):
            changed.append(item)
    return changed


def _append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _event(execution_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": WORKFLOW_EXECUTOR_SCHEMA_VERSION,
        "created_at": iso_now(),
        "execution_id": execution_id,
        "event_type": event_type,
        "payload": payload,
    }


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Workflow Execution",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- execution_id: {result['execution_id']}",
        f"- status: {result['status']}",
        f"- preset: {result['preset']}",
        f"- step_id: {result['step_id']}",
        f"- confirmed: {result['confirmed']}",
        f"- selected_step_count: {result['selected_step_count']}",
        f"- passed_step_count: {result['passed_step_count']}",
        f"- blocked_step_count: {result['blocked_step_count']}",
        f"- failed_step_count: {result['failed_step_count']}",
        f"- events_path: `{result['events_path']}`",
        f"- logs_dir: `{result['logs_dir']}`",
        "",
        "## Steps",
        "",
        "| Step | Status | Attempts | Seconds | Changed outputs | Message |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step in result["steps"]:
        lines.append(
            "| {step_id} | {status} | {attempts} | {seconds} | {changed} | {message} |".format(
                step_id=_cell(step.get("step_id")),
                status=_cell(step.get("status")),
                attempts=_cell(step.get("attempt_count")),
                seconds=_cell(step.get("duration_seconds")),
                changed=_cell(len(step.get("changed_outputs", []))),
                message=_cell(step.get("message")),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in result["guardrails"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
