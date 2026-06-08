"""Asset-centric incremental build planning."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from .asset_catalog import generate_asset_catalog
from .artifact_manager import sha256_file
from .utils import iso_now, read_json, relpath, safe_write_text, write_json
from .workflow_executor import execute_workflow
from .workflow_registry import build_workflow_state

ASSET_BUILD_SCHEMA_VERSION = "1.46.0"


def plan_asset_build(
    project_dir: Path,
    *,
    target: str = "all",
    refresh_catalog: bool = False,
) -> dict[str, Any]:
    """Plan safe incremental materialization from workflow outputs."""
    project_dir = Path(project_dir)
    catalog = generate_asset_catalog(project_dir) if refresh_catalog else _catalog(project_dir)
    state = build_workflow_state(project_dir)
    normalized_target = _normalize_target(target)
    records = [
        _build_record(project_dir, step, catalog, normalized_target)
        for step in state.get("steps", [])
        if _matches_target(step, normalized_target)
    ]
    materializable = [record for record in records if record["action"] == "materialize"]
    blocked = [record for record in records if record["action"] in {"blocked", "skip_unsafe"}]
    plan = {
        "schema_version": ASSET_BUILD_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "target": normalized_target,
        "status": _plan_status(records, materializable, blocked),
        "step_count": len(records),
        "materialize_step_count": len(materializable),
        "blocked_step_count": len(blocked),
        "complete_step_count": sum(1 for record in records if record["action"] == "skip_complete"),
        "safe_step_count": sum(1 for record in records if record["safe"]),
        "asset_count": int(catalog.get("asset_count", 0) or 0),
        "top_step_id": materializable[0]["step_id"] if materializable else blocked[0]["step_id"] if blocked else None,
        "top_command": materializable[0]["materialize_command"] if materializable else blocked[0]["source_command"] if blocked else None,
        "steps": records,
        "guardrails": [
            "Only workflow steps marked safe and runnable are materialization candidates.",
            "Unsafe source input, human decisions, repairs, and experiment execution remain blocked.",
            "Planning reads workflow state and asset catalog metadata; it does not execute commands.",
        ],
        "policy": "Asset build plans organize engineering artifact materialization only; they do not verify scientific correctness.",
    }
    write_json(project_dir / "workspace" / "asset_build_plan.json", plan)
    safe_write_text(project_dir / "workspace" / "ASSET_BUILD_PLAN.md", _render_plan_markdown(plan))
    return plan


def asset_build_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing asset build plan summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "asset_build_plan.json"
    markdown_path = project_dir / "workspace" / "ASSET_BUILD_PLAN.md"
    materialization_path = project_dir / "workspace" / "asset_materialization.json"
    materialization_markdown = project_dir / "workspace" / "ASSET_MATERIALIZATION.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    materialization = read_json(materialization_path, default={}) or {}
    materialization = materialization if isinstance(materialization, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "materialization_path": str(materialization_path) if materialization_path.exists() else None,
        "materialization_markdown_path": str(materialization_markdown) if materialization_markdown.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "target": data.get("target"),
        "step_count": int(data.get("step_count", 0) or 0),
        "materialize_step_count": int(data.get("materialize_step_count", 0) or 0),
        "blocked_step_count": int(data.get("blocked_step_count", 0) or 0),
        "top_step_id": data.get("top_step_id"),
        "top_command": data.get("top_command"),
        "last_materialization_status": materialization.get("status"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def materialize_assets(
    project_dir: Path,
    *,
    target: str = "all",
    step_id: str | None = None,
    confirm: bool = False,
    max_steps: int | None = None,
    export_zip: bool = False,
) -> dict[str, Any]:
    """Materialize safe incremental build steps through the workflow executor."""
    project_dir = Path(project_dir)
    plan = plan_asset_build(project_dir, target=step_id or target)
    candidates = [step for step in plan["steps"] if step["action"] == "materialize"]
    if max_steps is not None:
        candidates = candidates[: max(0, max_steps)]
    executions = []
    if confirm:
        for candidate in candidates:
            execution = execute_workflow(project_dir, step_id=candidate["step_id"], confirm=True, export_zip=export_zip)
            executions.append(
                {
                    "step_id": candidate["step_id"],
                    "status": execution.get("status"),
                    "passed_step_count": execution.get("passed_step_count"),
                    "blocked_step_count": execution.get("blocked_step_count"),
                    "failed_step_count": execution.get("failed_step_count"),
                    "execution_id": execution.get("execution_id"),
                    "logs_dir": execution.get("logs_dir"),
                }
            )
    result = {
        "schema_version": ASSET_BUILD_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "target": step_id or target,
        "confirmed": confirm,
        "export_zip": export_zip,
        "selected_step_count": len(candidates),
        "executed_step_count": len(executions),
        "status": _materialization_status(confirm, candidates, executions, plan),
        "plan_path": str(project_dir / "workspace" / "asset_build_plan.json"),
        "steps": candidates,
        "executions": executions,
        "guardrails": [
            "Dry-run materialization writes a plan but executes nothing.",
            "Confirmed materialization delegates execution to the guarded workflow executor.",
            "Unsafe workflow steps never become materialization candidates.",
        ],
        "policy": "Asset materialization executes safe derived artifact steps only; it does not run experiments or prove scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "asset_materialization.json", result)
    safe_write_text(project_dir / "workspace" / "ASSET_MATERIALIZATION.md", _render_materialization_markdown(result))
    if confirm and executions:
        plan_asset_build(project_dir, target=step_id or target)
    return result


def _catalog(project_dir: Path) -> dict[str, Any]:
    data = read_json(Path(project_dir) / "workspace" / "asset_catalog.json", default={}) or {}
    return data if isinstance(data, dict) else {}


def _normalize_target(target: str) -> str:
    value = (target or "all").strip()
    return value or "all"


def _matches_target(step: dict[str, Any], target: str) -> bool:
    if target == "all":
        return True
    needle = target.lower()
    values = [
        str(step.get("step_id") or ""),
        str(step.get("stage") or ""),
        str(step.get("title") or ""),
        *[str(item) for item in step.get("outputs", [])],
    ]
    return any(needle in value.lower() for value in values)


def _build_record(project_dir: Path, step: dict[str, Any], catalog: dict[str, Any], target: str) -> dict[str, Any]:
    output_records = [_output_record(project_dir, pattern) for pattern in step.get("outputs", [])]
    action, reason = _action_for_step(step)
    step_id = str(step.get("step_id") or "")
    materialize_command = f"openrepro workflow execute {project_dir} --step {step_id} --confirm"
    return {
        "step_id": step_id,
        "title": step.get("title"),
        "stage": step.get("stage"),
        "target": target,
        "status": step.get("status"),
        "safe": bool(step.get("safe")),
        "runnable": bool(step.get("runnable")),
        "action": action,
        "reason": reason,
        "source_command": step.get("command"),
        "materialize_command": materialize_command if action == "materialize" else None,
        "missing_dependencies": step.get("missing_dependencies", []),
        "outputs": output_records,
        "missing_output_count": sum(1 for item in output_records if not item["present"]),
        "linked_assets": _linked_assets(catalog, step.get("outputs", [])),
    }


def _action_for_step(step: dict[str, Any]) -> tuple[str, str]:
    if step.get("status") == "complete":
        return "skip_complete", "Declared outputs are already present."
    if not step.get("safe"):
        return "skip_unsafe", "Workflow step is not safe for automated materialization."
    if step.get("missing_dependencies"):
        return "blocked", "Required dependency outputs are missing or stale."
    if step.get("runnable"):
        return "materialize", "Safe derived step has missing outputs and can be materialized."
    return "blocked", "Step is not currently runnable."


def _output_record(project_dir: Path, pattern: str) -> dict[str, Any]:
    matches = _matched_paths(project_dir, pattern)
    return {
        "pattern": pattern,
        "present": bool(matches),
        "paths": [relpath(path, project_dir).replace("\\", "/") for path in matches],
        "sha256": sha256_file(matches[0]) if len(matches) == 1 and matches[0].is_file() else None,
    }


def _matched_paths(project_dir: Path, pattern: str) -> list[Path]:
    if any(char in pattern for char in "*?["):
        return sorted((path for path in project_dir.glob(pattern) if path.exists()), key=lambda item: item.as_posix())
    path = project_dir / pattern
    return [path] if path.exists() else []


def _linked_assets(catalog: dict[str, Any], patterns: list[str]) -> list[dict[str, Any]]:
    assets = catalog.get("assets", []) if isinstance(catalog.get("assets"), list) else []
    linked = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        path = str(asset.get("path") or "")
        if any(fnmatch.fnmatch(path, pattern) or path == pattern for pattern in patterns):
            linked.append(
                {
                    "asset_id": asset.get("asset_id"),
                    "kind": asset.get("kind"),
                    "path": path,
                    "status": asset.get("status"),
                    "sha256": asset.get("sha256"),
                }
            )
    return linked[:25]


def _plan_status(records: list[dict[str, Any]], materializable: list[dict[str, Any]], blocked: list[dict[str, Any]]) -> str:
    if not records:
        return "empty"
    if materializable:
        return "ready"
    if blocked:
        return "blocked"
    return "up_to_date"


def _materialization_status(
    confirm: bool,
    candidates: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    plan: dict[str, Any],
) -> str:
    if not candidates:
        return "up_to_date" if plan.get("status") == "up_to_date" else "blocked"
    if not confirm:
        return "dry_run"
    if any(item.get("failed_step_count", 0) for item in executions):
        return "failed"
    if any(item.get("blocked_step_count", 0) for item in executions):
        return "blocked"
    return "complete"


def _render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Asset Build Plan",
        "",
        f"- schema_version: {plan['schema_version']}",
        f"- status: {plan['status']}",
        f"- target: {plan['target']}",
        f"- step_count: {plan['step_count']}",
        f"- materialize_step_count: {plan['materialize_step_count']}",
        f"- blocked_step_count: {plan['blocked_step_count']}",
        f"- top_command: `{plan.get('top_command') or ''}`",
        "",
        "| Step | Stage | Status | Action | Missing outputs | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step in plan["steps"]:
        lines.append(
            "| {step_id} | {stage} | {status} | {action} | {missing} | {reason} |".format(
                step_id=_cell(step.get("step_id")),
                stage=_cell(step.get("stage")),
                status=_cell(step.get("status")),
                action=_cell(step.get("action")),
                missing=_cell(step.get("missing_output_count")),
                reason=_cell(step.get("reason")),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in plan["guardrails"])
    lines.extend(["", "## Policy", "", plan["policy"], ""])
    return "\n".join(lines)


def _render_materialization_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Asset Materialization",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- confirmed: {result['confirmed']}",
        f"- selected_step_count: {result['selected_step_count']}",
        f"- executed_step_count: {result['executed_step_count']}",
        "",
        "| Step | Action | Command |",
        "| --- | --- | --- |",
    ]
    for step in result["steps"]:
        lines.append(f"| {_cell(step.get('step_id'))} | {_cell(step.get('action'))} | `{_cell(step.get('materialize_command'))}` |")
    lines.extend(["", "## Executions", "", "| Step | Status | Execution |", "| --- | --- | --- |"])
    for execution in result["executions"]:
        lines.append(f"| {_cell(execution.get('step_id'))} | {_cell(execution.get('status'))} | {_cell(execution.get('execution_id'))} |")
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in result["guardrails"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
