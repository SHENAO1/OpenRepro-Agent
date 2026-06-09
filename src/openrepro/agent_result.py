"""Agent result intake and validation for supervised task contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

AGENT_RESULT_SCHEMA_VERSION = "1.59.0"
FORBIDDEN_COMMANDS = {
    "claim-signoff",
    "configure-provider",
    "repair",
    "rerun-experiment",
    "review-decision",
    "run-experiment",
}
FORBIDDEN_ARTIFACT_PARTS = {".git", ".venv", "__pycache__"}
FORBIDDEN_ARTIFACT_FILES = {
    "project_config.yaml",
    "workspace/review_decisions.json",
    "workspace/claim_signoffs.json",
    "workspace/agent_result_validation.json",
}


def ingest_agent_result(project_dir: Path, result_file: Path, replace: bool = False) -> dict[str, Any]:
    """Ingest one or more externally produced agent result events."""
    project_dir = Path(project_dir)
    result_file = Path(result_file)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    if not result_file.exists() or not result_file.is_file():
        raise FileNotFoundError(f"Agent result file not found: {result_file}")

    payload = read_json(result_file, default=None)
    raw_events = payload if isinstance(payload, list) else payload.get("results", []) if isinstance(payload, dict) and isinstance(payload.get("results"), list) else [payload]
    if not raw_events or not all(isinstance(event, dict) for event in raw_events):
        raise ValueError("Agent result input must be a JSON object, a list of objects, or an object with a results list.")

    workspace = project_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    existing = [] if replace else _read_jsonl(workspace / "agent_results.jsonl")
    source_sha256 = sha256_file(result_file)
    ingested_events: list[dict[str, Any]] = []
    for index, event in enumerate(raw_events, start=1):
        normalized = dict(event)
        normalized.setdefault("event", "agent_result")
        normalized.setdefault("created_at", iso_now())
        normalized["ingested_at"] = iso_now()
        normalized["ingest_source"] = str(result_file)
        normalized["ingest_source_sha256"] = source_sha256
        normalized["ingest_id"] = f"AR{len(existing) + len(ingested_events) + 1:04d}"
        ingested_events.append(normalized)

    all_events = existing + ingested_events
    _write_jsonl(workspace / "agent_results.jsonl", all_events)
    _write_agent_results(project_dir, all_events, status="needs_validation", validation=None)
    validation = validate_agent_results(project_dir)
    return {
        "schema_version": AGENT_RESULT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": validation["status"],
        "replace": replace,
        "source_file": str(result_file),
        "source_sha256": source_sha256,
        "new_result_count": len(ingested_events),
        "result_count": len(all_events),
        "validation_status": validation["status"],
        "issue_count": validation["issue_count"],
        "warning_count": validation["warning_count"],
        "top_command": validation["top_command"],
        "jsonl_path": str(workspace / "agent_results.jsonl"),
        "json_path": str(workspace / "agent_results.json"),
        "validation_path": str(workspace / "agent_result_validation.json"),
        "review_path": str(workspace / "AGENT_RESULT_REVIEW.md"),
        "policy": "Ingested agent results are imported workflow evidence only and require validation and human review before trust.",
    }


def validate_agent_results(project_dir: Path) -> dict[str, Any]:
    """Validate imported agent result events against task specs and guardrails."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    workspace = project_dir / "workspace"
    jsonl_path = workspace / "agent_results.jsonl"
    events = _read_jsonl(jsonl_path)
    task_spec = read_json(workspace / "agent_task_spec.json", default={}) or {}
    task_spec = task_spec if isinstance(task_spec, dict) else {}
    result_schema = read_json(workspace / "agent_result_schema.json", default={}) or {}
    result_schema = result_schema if isinstance(result_schema, dict) else {}
    evidence_graph = read_json(workspace / "evidence_graph.json", default={}) or {}
    evidence_graph = evidence_graph if isinstance(evidence_graph, dict) else {}

    task_index = {
        (str(task.get("task_spec_id")), str(task.get("task_id"))): task
        for task in task_spec.get("tasks", [])
        if isinstance(task, dict)
    }
    task_ids = {str(task.get("task_id")) for task in task_spec.get("tasks", []) if isinstance(task, dict)}
    task_spec_ids = {str(task.get("task_spec_id")) for task in task_spec.get("tasks", []) if isinstance(task, dict)}
    graph_node_ids = {str(node.get("node_id")) for node in evidence_graph.get("nodes", []) if isinstance(node, dict) and node.get("node_id")}
    required = result_schema.get("required") if isinstance(result_schema.get("required"), list) else _default_required_fields()
    allowed_statuses = _allowed_statuses(result_schema)

    result_records: list[dict[str, Any]] = []
    all_issues: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        record = _validate_event(
            project_dir=project_dir,
            event=event,
            index=index,
            required=required,
            allowed_statuses=allowed_statuses,
            task_index=task_index,
            task_ids=task_ids,
            task_spec_ids=task_spec_ids,
            graph_node_ids=graph_node_ids,
            task_spec_present=bool(task_spec),
        )
        result_records.append(record)
        all_issues.extend(record["issues"])
        all_warnings.extend(record["warnings"])

    if not task_spec:
        all_issues.append(_issue("task_spec_missing", "workspace/agent_task_spec.json is missing or invalid.", None))
    if not result_schema:
        all_warnings.append(_issue("result_schema_missing", "workspace/agent_result_schema.json is missing; built-in defaults were used.", None))

    needs_human_review = [
        record
        for record in result_records
        if record["requires_human_review"] or record["status"] in {"blocked", "failed", "needs_human_review"}
    ]
    status = _validation_status(events, all_issues, needs_human_review)
    validation = {
        "schema_version": AGENT_RESULT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "valid": not all_issues,
        "result_count": len(events),
        "valid_result_count": sum(1 for record in result_records if record["valid"]),
        "invalid_result_count": sum(1 for record in result_records if not record["valid"]),
        "needs_human_review_count": len(needs_human_review),
        "completed_count": sum(1 for record in result_records if record["status"] == "completed"),
        "blocked_count": sum(1 for record in result_records if record["status"] == "blocked"),
        "failed_count": sum(1 for record in result_records if record["status"] == "failed"),
        "issue_count": len(all_issues),
        "warning_count": len(all_warnings),
        "issues": all_issues,
        "warnings": all_warnings,
        "results": result_records,
        "source": {
            "agent_results_jsonl": str(jsonl_path),
            "agent_results_jsonl_present": jsonl_path.exists(),
            "agent_results_jsonl_sha256": sha256_file(jsonl_path) if jsonl_path.exists() else None,
            "agent_task_spec_present": bool(task_spec),
            "agent_task_spec_sha256": sha256_file(workspace / "agent_task_spec.json") if (workspace / "agent_task_spec.json").exists() else None,
            "agent_result_schema_present": bool(result_schema),
            "agent_result_schema_sha256": sha256_file(workspace / "agent_result_schema.json") if (workspace / "agent_result_schema.json").exists() else None,
            "evidence_graph_present": bool(evidence_graph),
            "evidence_graph_sha256": sha256_file(workspace / "evidence_graph.json") if (workspace / "evidence_graph.json").exists() else None,
        },
        "top_command": _top_command(project_dir, status, bool(task_spec), len(events)),
        "policy": "Agent result validation checks imported supervised-agent output as workflow evidence only; it does not accept scientific claims automatically.",
    }
    write_json(workspace / "agent_result_validation.json", validation)
    _write_agent_results(project_dir, events, status=status, validation=validation)
    safe_write_text(workspace / "AGENT_RESULT_REVIEW.md", _render_markdown(validation))
    return validation


def agent_result_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing agent result intake summary without mutating files."""
    project_dir = Path(project_dir)
    workspace = project_dir / "workspace"
    aggregate_path = workspace / "agent_results.json"
    jsonl_path = workspace / "agent_results.jsonl"
    validation_path = workspace / "agent_result_validation.json"
    review_path = workspace / "AGENT_RESULT_REVIEW.md"
    aggregate = read_json(aggregate_path, default={}) or {}
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    validation = read_json(validation_path, default={}) or {}
    validation = validation if isinstance(validation, dict) else {}
    result_count = int(validation.get("result_count", aggregate.get("result_count", 0)) or 0)
    return {
        "present": aggregate_path.exists() or jsonl_path.exists() or validation_path.exists(),
        "path": str(aggregate_path) if aggregate_path.exists() else None,
        "jsonl_path": str(jsonl_path) if jsonl_path.exists() else None,
        "validation_path": str(validation_path) if validation_path.exists() else None,
        "review_path": str(review_path) if review_path.exists() else None,
        "schema_version": validation.get("schema_version") or aggregate.get("schema_version"),
        "status": validation.get("status", aggregate.get("status", "missing")),
        "valid": validation.get("valid"),
        "result_count": result_count,
        "valid_result_count": int(validation.get("valid_result_count", 0) or 0),
        "invalid_result_count": int(validation.get("invalid_result_count", 0) or 0),
        "needs_human_review_count": int(validation.get("needs_human_review_count", 0) or 0),
        "issue_count": int(validation.get("issue_count", 0) or 0),
        "warning_count": int(validation.get("warning_count", 0) or 0),
        "top_command": validation.get("top_command"),
        "sha256": sha256_file(aggregate_path) if aggregate_path.exists() else None,
        "validation_sha256": sha256_file(validation_path) if validation_path.exists() else None,
    }


def _validate_event(
    *,
    project_dir: Path,
    event: dict[str, Any],
    index: int,
    required: list[str],
    allowed_statuses: set[str],
    task_index: dict[tuple[str, str], dict[str, Any]],
    task_ids: set[str],
    task_spec_ids: set[str],
    graph_node_ids: set[str],
    task_spec_present: bool,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    event_id = str(event.get("ingest_id") or event.get("task_spec_id") or f"event:{index}")
    for field in required:
        if field not in event:
            issues.append(_issue("missing_required_field", f"Missing required field: {field}", event_id))

    if event.get("event") != "agent_result":
        issues.append(_issue("invalid_event", "event must be agent_result.", event_id))
    status = str(event.get("status") or "")
    if status not in allowed_statuses:
        issues.append(_issue("invalid_status", f"status must be one of: {sorted(allowed_statuses)}", event_id))
    if not isinstance(event.get("summary"), str) or not str(event.get("summary")).strip():
        issues.append(_issue("empty_summary", "summary must be a non-empty string.", event_id))
    if event.get("policy_acknowledged") is not True:
        issues.append(_issue("policy_not_acknowledged", "policy_acknowledged must be true.", event_id))
    if not isinstance(event.get("requires_human_review"), bool):
        issues.append(_issue("invalid_requires_human_review", "requires_human_review must be a boolean.", event_id))

    task_spec_id = str(event.get("task_spec_id") or "")
    task_id = str(event.get("task_id") or "")
    if task_spec_present:
        if (task_spec_id, task_id) not in task_index:
            if task_spec_id not in task_spec_ids:
                issues.append(_issue("unknown_task_spec_id", f"Unknown task_spec_id: {task_spec_id}", event_id))
            if task_id not in task_ids:
                issues.append(_issue("unknown_task_id", f"Unknown task_id: {task_id}", event_id))

    artifact_infos = _validate_string_list(event, "artifacts_written", issues, event_id)
    command_infos = _validate_string_list(event, "commands_run", issues, event_id)
    evidence_node_ids = _validate_string_list(event, "evidence_graph_node_ids", issues, event_id)
    if not evidence_node_ids:
        warnings.append(_issue("missing_evidence_graph_refs", "No evidence graph node ids were cited.", event_id))
    for node_id in evidence_node_ids:
        if graph_node_ids and node_id not in graph_node_ids:
            issues.append(_issue("unknown_evidence_graph_node", f"Unknown evidence graph node id: {node_id}", event_id))

    artifact_records = []
    for artifact in artifact_infos:
        record = _artifact_record(project_dir, artifact)
        artifact_records.append(record)
        if not record["inside_project"]:
            issues.append(_issue("artifact_outside_project", f"Artifact path is outside the project: {artifact}", event_id))
        if record["forbidden"]:
            issues.append(_issue("forbidden_artifact_path", f"Artifact path is forbidden: {artifact}", event_id))
        if not record["exists"]:
            warnings.append(_issue("artifact_missing", f"Artifact path does not exist yet: {artifact}", event_id))

    command_records = []
    for command in command_infos:
        record = _command_record(command)
        command_records.append(record)
        if record["forbidden"]:
            issues.append(_issue("forbidden_command", f"Command is not allowed in agent result evidence: {command}", event_id))
        if record["unknown_shell_command"]:
            warnings.append(_issue("untracked_command", f"Command is not an openrepro command: {command}", event_id))
    if status == "completed" and not command_infos:
        warnings.append(_issue("completed_without_commands", "Completed result did not record commands_run.", event_id))

    valid = not issues
    return {
        "event_index": index,
        "event_id": event_id,
        "task_spec_id": task_spec_id,
        "task_id": task_id,
        "agent_id": event.get("agent_id"),
        "status": status or "missing",
        "summary": event.get("summary"),
        "requires_human_review": bool(event.get("requires_human_review")),
        "valid": valid,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
        "artifact_checks": artifact_records,
        "command_checks": command_records,
        "evidence_graph_node_ids": evidence_node_ids,
        "ingest_source": event.get("ingest_source"),
        "ingest_source_sha256": event.get("ingest_source_sha256"),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if isinstance(data, dict):
                events.append(data)
    return events


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _write_agent_results(project_dir: Path, events: list[dict[str, Any]], status: str, validation: dict[str, Any] | None) -> None:
    payload = {
        "schema_version": AGENT_RESULT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "result_count": len(events),
        "results": events,
        "latest_validation": {
            "status": validation.get("status"),
            "valid": validation.get("valid"),
            "issue_count": validation.get("issue_count"),
            "warning_count": validation.get("warning_count"),
            "needs_human_review_count": validation.get("needs_human_review_count"),
            "top_command": validation.get("top_command"),
        }
        if validation
        else None,
        "policy": "Agent results are imported workflow evidence only and do not prove scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "agent_results.json", payload)


def _validate_string_list(event: dict[str, Any], field: str, issues: list[dict[str, Any]], event_id: str) -> list[str]:
    value = event.get(field)
    if not isinstance(value, list):
        issues.append(_issue("invalid_list_field", f"{field} must be a list of strings.", event_id))
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            issues.append(_issue("invalid_list_item", f"{field} contains a non-string item.", event_id))
            continue
        result.append(item)
    return result


def _artifact_record(project_dir: Path, value: str) -> dict[str, Any]:
    raw_path = Path(value)
    path = raw_path if raw_path.is_absolute() else project_dir / raw_path
    resolved_project = project_dir.resolve()
    resolved_path = path.resolve(strict=False)
    inside = _is_relative_to(resolved_path, resolved_project)
    relative = relpath(resolved_path, resolved_project) if inside else str(resolved_path)
    normalized = relative.replace("\\", "/")
    parts = set(Path(normalized).parts)
    forbidden = bool(parts & FORBIDDEN_ARTIFACT_PARTS) or normalized in FORBIDDEN_ARTIFACT_FILES
    return {
        "path": value,
        "resolved_path": str(resolved_path),
        "relative_path": normalized,
        "inside_project": inside,
        "exists": resolved_path.exists(),
        "sha256": sha256_file(resolved_path) if resolved_path.exists() and resolved_path.is_file() else None,
        "forbidden": forbidden,
    }


def _command_record(command: str) -> dict[str, Any]:
    tokens = command.split()
    command_name = ""
    if tokens:
        command_name = tokens[1] if tokens[0] == "openrepro" and len(tokens) > 1 else tokens[0]
    return {
        "command": command,
        "command_name": command_name,
        "forbidden": command_name in FORBIDDEN_COMMANDS,
        "unknown_shell_command": bool(tokens and tokens[0] != "openrepro"),
    }


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _allowed_statuses(schema: dict[str, Any]) -> set[str]:
    status = schema.get("properties", {}).get("status", {}) if isinstance(schema.get("properties"), dict) else {}
    values = status.get("enum") if isinstance(status, dict) else None
    if isinstance(values, list) and all(isinstance(item, str) for item in values):
        return set(values)
    return {"completed", "blocked", "needs_human_review", "failed"}


def _default_required_fields() -> list[str]:
    return [
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
    ]


def _validation_status(events: list[dict[str, Any]], issues: list[dict[str, Any]], needs_human_review: list[dict[str, Any]]) -> str:
    if not events:
        return "no_results"
    if issues:
        return "invalid"
    if needs_human_review:
        return "needs_human_review"
    return "validated"


def _top_command(project_dir: Path, status: str, task_spec_present: bool, result_count: int) -> str | None:
    if not task_spec_present:
        return f"openrepro agent-task-spec {project_dir}"
    if result_count == 0:
        return None
    if status == "invalid":
        return f"openrepro agent-result validate {project_dir}"
    if status == "needs_human_review":
        return f"openrepro review-board {project_dir}"
    return None


def _issue(code: str, message: str, event_id: str | None) -> dict[str, Any]:
    return {"code": code, "message": message, "event_id": event_id}


def _render_markdown(validation: dict[str, Any]) -> str:
    result_rows = [
        "| Event | Task | Agent | Status | Valid | Issues | Warnings | Human review |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not validation["results"]:
        result_rows.append("| none |  |  | no_results | True | 0 | 0 | False |")
    for result in validation["results"]:
        result_rows.append(
            "| {event} | {task} | {agent} | {status} | {valid} | {issues} | {warnings} | {review} |".format(
                event=_cell(result.get("event_id")),
                task=_cell(result.get("task_id")),
                agent=_cell(result.get("agent_id")),
                status=_cell(result.get("status")),
                valid=_cell(result.get("valid")),
                issues=_cell(result.get("issue_count")),
                warnings=_cell(result.get("warning_count")),
                review=_cell(result.get("requires_human_review")),
            )
        )
    issue_rows = ["| Code | Event | Message |", "| --- | --- | --- |"]
    if not validation["issues"]:
        issue_rows.append("| none |  | No validation issues. |")
    for issue in validation["issues"]:
        issue_rows.append(f"| {_cell(issue.get('code'))} | {_cell(issue.get('event_id'))} | {_cell(issue.get('message'))} |")
    warning_rows = ["| Code | Event | Message |", "| --- | --- | --- |"]
    if not validation["warnings"]:
        warning_rows.append("| none |  | No validation warnings. |")
    for warning in validation["warnings"]:
        warning_rows.append(f"| {_cell(warning.get('code'))} | {_cell(warning.get('event_id'))} | {_cell(warning.get('message'))} |")
    return f"""# Agent Result Review

- schema_version: {validation['schema_version']}
- status: {validation['status']}
- valid: {validation['valid']}
- result_count: {validation['result_count']}
- valid_result_count: {validation['valid_result_count']}
- invalid_result_count: {validation['invalid_result_count']}
- needs_human_review_count: {validation['needs_human_review_count']}
- issue_count: {validation['issue_count']}
- warning_count: {validation['warning_count']}
- top_command: {validation['top_command']}

## Results

{chr(10).join(result_rows)}

## Issues

{chr(10).join(issue_rows)}

## Warnings

{chr(10).join(warning_rows)}

## Policy

{validation['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value).replace("|", "/")
    return str(value).replace("\n", " ").replace("|", "/")
