"""Declarative OpenRepro pipeline spec export, planning, and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import iso_now, read_json, read_yaml, safe_write_text, write_json, write_yaml
from .workflow_preset import PRESETS
from .workflow_registry import build_workflow_state, workflow_step_map

PIPELINE_SPEC_SCHEMA_VERSION = "1.37.0"


def export_pipeline_spec(project_dir: Path, *, preset: str = "delivery", overwrite: bool = False) -> dict[str, Any]:
    """Export openrepro.pipeline.yaml from the registered workflow DAG."""
    project_dir = Path(project_dir)
    spec_path = project_dir / "openrepro.pipeline.yaml"
    if spec_path.exists() and not overwrite:
        spec = read_yaml(spec_path, default={}) or {}
        return spec if isinstance(spec, dict) else {}
    preset_id = _normalize_preset(preset)
    step_map = workflow_step_map()
    selected_ids = PRESETS[preset_id]["steps"]
    step_ids = [step.step_id for step in step_map.values() if selected_ids is None or step.step_id in selected_ids]
    spec = {
        "schema_version": PIPELINE_SPEC_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "preset": preset_id,
        "description": PRESETS[preset_id]["description"],
        "steps": [
            {
                "step_id": step_id,
                "title": step_map[step_id].title,
                "stage": step_map[step_id].stage,
                "command": step_map[step_id].command,
                "safe": step_map[step_id].safe,
                "execution": step_map[step_id].execution,
                "dependencies": list(step_map[step_id].dependencies),
                "outputs": list(step_map[step_id].outputs),
            }
            for step_id in step_ids
        ],
        "guardrails": [
            "Pipeline specs are declarations over registered OpenRepro workflow steps.",
            "They do not execute commands.",
            "Unsafe source input, human decision, repair apply, and experiment execution steps remain explicit commands.",
        ],
        "policy": "Pipeline specs organize workflow execution intent only; they do not prove scientific reproduction.",
    }
    write_yaml(spec_path, spec)
    return spec


def plan_pipeline(project_dir: Path) -> dict[str, Any]:
    """Write a plan by comparing openrepro.pipeline.yaml with current workflow state."""
    project_dir = Path(project_dir)
    spec = _spec(project_dir)
    state = build_workflow_state(project_dir)
    state_by_id = {step["step_id"]: step for step in state.get("steps", [])}
    planned_steps = []
    for spec_step in spec.get("steps", []):
        current = state_by_id.get(spec_step.get("step_id"))
        if current is None:
            planned_steps.append(
                {
                    "step_id": spec_step.get("step_id"),
                    "title": spec_step.get("title"),
                    "status": "unknown",
                    "safe": spec_step.get("safe"),
                    "runnable": False,
                    "command": spec_step.get("command"),
                    "missing_dependencies": [],
                    "missing_outputs": spec_step.get("outputs", []),
                }
            )
            continue
        planned_steps.append({**current, "spec_command": spec_step.get("command")})
    counts = _counts(planned_steps)
    next_step = _next_step(planned_steps)
    plan = {
        "schema_version": PIPELINE_SPEC_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "preset": spec.get("preset"),
        "status": "complete" if planned_steps and counts.get("complete", 0) == len(planned_steps) else "needs_work",
        "step_count": len(planned_steps),
        "complete_step_count": counts.get("complete", 0),
        "pending_step_count": counts.get("pending", 0),
        "blocked_step_count": counts.get("blocked", 0),
        "stale_step_count": counts.get("stale", 0),
        "runnable_step_count": sum(1 for step in planned_steps if step.get("runnable")),
        "next_step": next_step,
        "top_command": _top_command(project_dir, next_step),
        "steps": planned_steps,
        "policy": spec.get("policy") or "Pipeline specs organize workflow execution intent only.",
    }
    write_json(project_dir / "workspace" / "pipeline_plan.json", plan)
    safe_write_text(project_dir / "workspace" / "PIPELINE_PLAN.md", _render_plan_markdown(plan))
    return plan


def validate_pipeline_spec(project_dir: Path) -> dict[str, Any]:
    """Validate openrepro.pipeline.yaml against the registered workflow DAG."""
    project_dir = Path(project_dir)
    spec = _spec(project_dir)
    step_map = workflow_step_map()
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for step in spec.get("steps", []):
        step_id = str(step.get("step_id") or "")
        if not step_id:
            errors.append("Pipeline step is missing step_id.")
            continue
        if step_id in seen:
            errors.append(f"Duplicate pipeline step: {step_id}")
        seen.add(step_id)
        registered = step_map.get(step_id)
        if registered is None:
            errors.append(f"Unknown registered workflow step: {step_id}")
            continue
        if bool(step.get("safe")) != registered.safe:
            warnings.append(f"Safe flag differs for {step_id}.")
        missing_dependencies = [dependency for dependency in registered.dependencies if dependency not in seen and dependency in _spec_step_ids(spec)]
        if missing_dependencies:
            warnings.append(f"Step {step_id} appears before declared dependencies: {', '.join(missing_dependencies)}")
    result = {
        "schema_version": PIPELINE_SPEC_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "step_count": len(spec.get("steps", [])) if isinstance(spec.get("steps"), list) else 0,
        "policy": spec.get("policy") or "Pipeline specs organize workflow execution intent only.",
    }
    write_json(project_dir / "workspace" / "pipeline_validation.json", result)
    safe_write_text(project_dir / "workspace" / "PIPELINE_VALIDATION.md", _render_validation_markdown(result))
    return result


def refresh_pipeline_spec(project_dir: Path) -> dict[str, Any]:
    """Ensure a pipeline spec exists, then write plan and validation artifacts."""
    export_pipeline_spec(project_dir, overwrite=False)
    plan = plan_pipeline(project_dir)
    validation = validate_pipeline_spec(project_dir)
    return {
        "schema_version": PIPELINE_SPEC_SCHEMA_VERSION,
        "project_dir": str(Path(project_dir)),
        "status": "passed" if validation["valid"] else "failed",
        "step_count": plan["step_count"],
        "runnable_step_count": plan["runnable_step_count"],
        "error_count": validation["error_count"],
        "warning_count": validation["warning_count"],
        "top_command": plan["top_command"],
    }


def pipeline_spec_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing pipeline spec summary without mutating files."""
    project_dir = Path(project_dir)
    spec_path = project_dir / "openrepro.pipeline.yaml"
    plan_path = project_dir / "workspace" / "pipeline_plan.json"
    validation_path = project_dir / "workspace" / "pipeline_validation.json"
    plan = read_json(plan_path, default={}) or {}
    validation = read_json(validation_path, default={}) or {}
    plan = plan if isinstance(plan, dict) else {}
    validation = validation if isinstance(validation, dict) else {}
    return {
        "present": spec_path.exists(),
        "path": str(spec_path) if spec_path.exists() else None,
        "plan_path": str(plan_path) if plan_path.exists() else None,
        "validation_path": str(validation_path) if validation_path.exists() else None,
        "schema_version": plan.get("schema_version") or validation.get("schema_version"),
        "status": plan.get("status", "present" if spec_path.exists() else "missing"),
        "valid": validation.get("valid"),
        "step_count": int(plan.get("step_count", 0) or validation.get("step_count", 0) or 0),
        "runnable_step_count": int(plan.get("runnable_step_count", 0) or 0),
        "top_command": plan.get("top_command"),
    }


def _spec(project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    spec = read_yaml(project_dir / "openrepro.pipeline.yaml", default={}) or {}
    if not isinstance(spec, dict) or not spec:
        spec = export_pipeline_spec(project_dir)
    if not isinstance(spec.get("steps"), list):
        spec["steps"] = []
    return spec


def _normalize_preset(preset: str) -> str:
    value = (preset or "delivery").strip().lower()
    if value not in PRESETS:
        allowed = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown pipeline preset: {preset}. Expected one of: {allowed}")
    return value


def _spec_step_ids(spec: dict[str, Any]) -> set[str]:
    return {str(step.get("step_id")) for step in spec.get("steps", []) if isinstance(step, dict)}


def _counts(steps: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in steps:
        status = str(step.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _next_step(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    for step in steps:
        if step.get("status") != "complete" and not step.get("missing_dependencies"):
            return step
    return None


def _top_command(project_dir: Path, next_step: dict[str, Any] | None) -> str | None:
    if not next_step:
        return None
    if next_step.get("safe"):
        return f"openrepro workflow run {project_dir} --step {next_step.get('step_id')} --confirm"
    command = str(next_step.get("command") or "")
    return command.replace("<project>", str(project_dir))


def _render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Pipeline Plan",
        "",
        f"- schema_version: {plan['schema_version']}",
        f"- status: {plan['status']}",
        f"- step_count: {plan['step_count']}",
        f"- complete_step_count: {plan['complete_step_count']}",
        f"- runnable_step_count: {plan['runnable_step_count']}",
        f"- top_command: {plan['top_command']}",
        "",
        "| Step | Status | Safe | Runnable | Command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in plan["steps"]:
        lines.append(
            "| {step_id} | {status} | {safe} | {runnable} | `{command}` |".format(
                step_id=_cell(step.get("step_id")),
                status=_cell(step.get("status")),
                safe=_cell(step.get("safe")),
                runnable=_cell(step.get("runnable")),
                command=_cell(step.get("command")),
            )
        )
    lines.extend(["", "## Policy", "", plan["policy"], ""])
    return "\n".join(lines)


def _render_validation_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Pipeline Validation",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- valid: {result['valid']}",
        f"- step_count: {result['step_count']}",
        f"- error_count: {result['error_count']}",
        f"- warning_count: {result['warning_count']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {_cell(item)}" for item in result["errors"] or ["None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {_cell(item)}" for item in result["warnings"] or ["None"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
