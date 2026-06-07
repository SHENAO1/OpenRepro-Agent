"""Goal-oriented workflow presets built from the registered workflow DAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import iso_now, read_json, safe_write_text, write_json
from .workflow_registry import build_workflow_state

WORKFLOW_PRESET_SCHEMA_VERSION = "1.34.0"

PRESETS: dict[str, dict[str, Any]] = {
    "data": {
        "title": "Data and environment readiness",
        "description": "Validate data, profile registered files, and refresh the reproducibility lock.",
        "steps": ("data_validation", "data_profile", "repro_lock", "repro_lock_validation"),
    },
    "review": {
        "title": "Reviewer evidence pack",
        "description": "Refresh claim, protocol, run, and reviewer-facing evidence navigation artifacts.",
        "steps": (
            "quality_gates",
            "run_index",
            "lineage",
            "claim_trace",
            "claim_trace_validation",
            "scorecard",
            "gaps",
            "review_board",
            "protocol",
            "protocol_coverage",
            "protocol_plan",
            "protocol_preflight",
            "evidence_binder",
            "evidence_binder_validation",
            "claim_signoffs",
            "claim_signoff_validation",
            "claim_evidence_report",
            "claim_evidence_report_validation",
            "reviewer_packet",
            "review_site",
            "paper_lineage",
            "evidence_explorer",
            "evidence_query",
        ),
    },
    "delivery": {
        "title": "Final handoff delivery",
        "description": "Refresh final handoff, freshness, dashboard, readiness, bundle, and evidence navigation artifacts.",
        "steps": (
            "report",
            "handoff",
            "evidence_package",
            "review_site",
            "collaboration_pack",
            "freshness",
            "dashboard",
            "readiness_review",
            "readiness_review_validation",
            "review_action_plan",
            "delivery_bundle",
            "paper_lineage",
            "evidence_explorer",
            "evidence_query",
        ),
    },
    "agent": {
        "title": "Supervised agent handoff",
        "description": "Prepare guarded multi-agent planning, board, dispatch, dry-run, and external adapter artifacts.",
        "steps": (
            "multi_agent_plan",
            "multi_agent_validation",
            "agent_board",
            "agent_dispatch",
            "agent_exec_plan",
            "agent_adapter",
            "agent_adapter_validation",
        ),
    },
    "full": {
        "title": "Full registered workflow",
        "description": "Show every registered workflow step in DAG order, including unsafe human or execution steps.",
        "steps": None,
    },
}


def generate_workflow_preset(
    project_dir: Path,
    *,
    preset: str = "delivery",
    runnable_only: bool = False,
) -> dict[str, Any]:
    """Write a goal-oriented workflow preset plan."""
    project_dir = Path(project_dir)
    preset_id = _normalize_preset(preset)
    preset_meta = PRESETS[preset_id]
    state = build_workflow_state(project_dir)
    selected = _selected_steps(state, preset_id, runnable_only=runnable_only)
    counts = _status_counts(selected)
    next_step = _next_step(selected)
    result = {
        "schema_version": WORKFLOW_PRESET_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "preset": preset_id,
        "title": preset_meta["title"],
        "description": preset_meta["description"],
        "runnable_only": runnable_only,
        "status": _status(selected, counts),
        "selected_step_count": len(selected),
        "complete_step_count": counts.get("complete", 0),
        "pending_step_count": counts.get("pending", 0),
        "blocked_step_count": counts.get("blocked", 0),
        "stale_step_count": counts.get("stale", 0),
        "unsafe_step_count": sum(1 for step in selected if not step.get("safe")),
        "runnable_step_count": sum(1 for step in selected if step.get("runnable")),
        "next_step": next_step,
        "top_command": _top_command(project_dir, next_step),
        "steps": selected,
        "available_presets": sorted(PRESETS),
        "guardrails": [
            "Workflow presets are planning views over the registered DAG.",
            "They do not execute commands by themselves.",
            "Unsafe source input, human decision, repair apply, and experiment execution steps remain explicit commands.",
        ],
        "policy": "Workflow presets organize project work for operators; they do not prove scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "workflow_preset.json", result)
    safe_write_text(project_dir / "workspace" / "WORKFLOW_PRESET.md", _render_markdown(result))
    return result


def workflow_preset_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing workflow preset summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "workflow_preset.json"
    markdown_path = project_dir / "workspace" / "WORKFLOW_PRESET.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "preset": data.get("preset"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "selected_step_count": int(data.get("selected_step_count", 0) or 0),
        "complete_step_count": int(data.get("complete_step_count", 0) or 0),
        "blocked_step_count": int(data.get("blocked_step_count", 0) or 0),
        "runnable_step_count": int(data.get("runnable_step_count", 0) or 0),
        "top_command": data.get("top_command"),
    }


def _normalize_preset(preset: str) -> str:
    value = (preset or "delivery").strip().lower()
    if value not in PRESETS:
        allowed = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown workflow preset: {preset}. Expected one of: {allowed}")
    return value


def _selected_steps(state: dict[str, Any], preset: str, *, runnable_only: bool) -> list[dict[str, Any]]:
    selected_ids = PRESETS[preset]["steps"]
    steps = state.get("steps", [])
    selected = [
        _project_step(step)
        for step in steps
        if selected_ids is None or step.get("step_id") in selected_ids
    ]
    if runnable_only:
        selected = [step for step in selected if step.get("runnable")]
    return selected


def _project_step(step: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "step_id",
        "title",
        "stage",
        "description",
        "command",
        "status",
        "safe",
        "execution",
        "dependencies",
        "missing_dependencies",
        "outputs",
        "missing_outputs",
        "runnable",
    ]
    return {key: step.get(key) for key in keys}


def _status_counts(steps: list[dict[str, Any]]) -> dict[str, int]:
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


def _status(steps: list[dict[str, Any]], counts: dict[str, int]) -> str:
    if not steps:
        return "empty"
    if counts.get("blocked", 0):
        return "blocked"
    if counts.get("pending", 0) or counts.get("stale", 0):
        return "needs_work"
    return "complete"


def _top_command(project_dir: Path, next_step: dict[str, Any] | None) -> str | None:
    if not next_step:
        return None
    if next_step.get("safe"):
        return f"openrepro workflow run {project_dir} --step {next_step.get('step_id')} --confirm"
    return str(next_step.get("command") or "")


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Workflow Preset",
        "",
        f"- preset: {result['preset']}",
        f"- title: {result['title']}",
        f"- status: {result['status']}",
        f"- selected_step_count: {result['selected_step_count']}",
        f"- complete_step_count: {result['complete_step_count']}",
        f"- pending_step_count: {result['pending_step_count']}",
        f"- blocked_step_count: {result['blocked_step_count']}",
        f"- stale_step_count: {result['stale_step_count']}",
        f"- runnable_step_count: {result['runnable_step_count']}",
        f"- top_command: {result['top_command']}",
        "",
        result["description"],
        "",
        "## Steps",
        "",
        "| Step | Stage | Status | Safe | Runnable | Command |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step in result["steps"]:
        lines.append(
            "| {step_id} | {stage} | {status} | {safe} | {runnable} | `{command}` |".format(
                step_id=_cell(step.get("step_id")),
                stage=_cell(step.get("stage")),
                status=_cell(step.get("status")),
                safe=_cell(step.get("safe")),
                runnable=_cell(step.get("runnable")),
                command=_cell(step.get("command")),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in result["guardrails"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
