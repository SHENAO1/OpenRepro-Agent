"""Repair-plan generation from diagnosis evidence."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import build_run_manifest
from .diagnostics import diagnose_project
from .utils import iso_now, read_json, safe_write_text, write_json


def create_repair_plan(project_dir: Path, run_dir: Path | None = None) -> dict[str, Any]:
    """Write workspace/repair_plan.json and workspace/REPAIR_PLAN.md."""
    project_dir = Path(project_dir)
    diagnosis = diagnose_project(project_dir, run_dir)
    issues = diagnosis.get("issues", [])
    actions = []
    for index, issue in enumerate(issues, start=1):
        actions.append(
            {
                "step": index,
                "code": issue.get("code"),
                "source": issue.get("source"),
                "message": issue.get("message"),
                "repair_suggestion": issue.get("repair_suggestion"),
                "automation": "manual_review_required",
            }
        )
    if not actions:
        actions.append(
            {
                "step": 1,
                "code": "healthy",
                "source": "diagnostics",
                "message": "No diagnosis issues found.",
                "repair_suggestion": "Run `openrepro inspect` and continue with the next planned workflow step.",
                "automation": "none",
            }
        )
    plan = {
        "schema_version": "0.4.0",
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "run_dir": diagnosis.get("run_dir"),
        "healthy": diagnosis.get("healthy"),
        "issue_count": len(issues),
        "actions": actions,
        "policy": "Repair plans are advisory only in v0.4.0; no automatic code changes are made.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "repair_plan.json", plan)
    lines = [
        "# Repair Plan",
        "",
        f"- healthy: {plan['healthy']}",
        f"- issue_count: {plan['issue_count']}",
        f"- run_dir: `{plan.get('run_dir')}`",
        "",
        "## Actions",
        "",
    ]
    for action in actions:
        lines.append(
            f"{action['step']}. {action['code']} ({action['source']}): {action['repair_suggestion']}"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "This plan is advisory only. v0.4.0 does not automatically repair experiments or rewrite code.",
        ]
    )
    safe_write_text(workspace / "REPAIR_PLAN.md", "\n".join(lines) + "\n")
    return plan


def _infer_command(run_dir: Path, manifest: dict[str, Any] | None) -> str | None:
    if manifest and manifest.get("command"):
        return str(manifest["command"])
    if (run_dir / "data" / "demo_metrics.json").exists():
        return "run-demo"
    if (run_dir / "data" / "sweep_results.json").exists():
        return "run-sweep"
    if (run_dir / "benchmark_result.json").exists():
        return "benchmark"
    if (run_dir / "benchmark_suite_result.json").exists():
        return "benchmark-suite"
    return None


def _json_lines(data: Any) -> list[str]:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)


def _manifest_diff(run_dir: Path) -> dict[str, Any] | None:
    manifest_path = run_dir / "manifest.json"
    old_manifest = read_json(manifest_path, default=None)
    old_manifest = old_manifest if isinstance(old_manifest, dict) else None
    command = _infer_command(run_dir, old_manifest)
    if command is None:
        return None
    new_manifest = build_run_manifest(run_dir, command)
    before = _json_lines(old_manifest or {})
    after = _json_lines(new_manifest)
    diff = "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=str(manifest_path),
            tofile=f"{manifest_path} (preview)",
        )
    )
    return {
        "file": str(manifest_path),
        "command": command,
        "diff": diff,
        "would_write": True,
    }


def preview_repair_actions(project_dir: Path, run_dir: Path | None = None) -> dict[str, Any]:
    """Write a dry-run repair preview without mutating project or run artifacts."""
    project_dir = Path(project_dir)
    diagnosis = diagnose_project(project_dir, run_dir)
    issues = diagnosis.get("issues", [])
    target = Path(diagnosis["run_dir"]) if diagnosis.get("run_dir") else None
    actions: list[dict[str, Any]] = []
    manifest_preview = _manifest_diff(target) if target is not None and target.exists() else None

    for index, issue in enumerate(issues, start=1):
        code = issue.get("code")
        action: dict[str, Any] = {
            "step": index,
            "code": code,
            "source": issue.get("source"),
            "message": issue.get("message"),
            "mode": "dry_run",
            "will_modify_files": False,
            "preview": issue.get("repair_suggestion"),
        }
        if code in {"manifest_mismatch", "missing_manifest"} and manifest_preview is not None:
            action["preview"] = "Would regenerate manifest.json from files currently present on disk."
            action["diff"] = manifest_preview["diff"]
            action["target_file"] = manifest_preview["file"]
        elif code == "missing_artifact":
            action["preview"] = "Would not fabricate missing artifacts; rerun the producing command or restore the file."
        elif code == "invalid_demo_config":
            action["preview"] = "Would require explicit config edits; no automatic value changes are made in dry-run."
        actions.append(action)

    if not actions:
        actions.append(
            {
                "step": 1,
                "code": "healthy",
                "source": "diagnostics",
                "message": "No diagnosis issues found.",
                "mode": "dry_run",
                "will_modify_files": False,
                "preview": "No repair actions are needed.",
            }
        )

    preview = {
        "schema_version": "0.5.0",
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "run_dir": diagnosis.get("run_dir"),
        "healthy": diagnosis.get("healthy"),
        "action_count": len(actions),
        "actions": actions,
        "policy": "Dry-run only; no project files, run files, or manifests were modified.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "repair_dry_run.json", preview)
    safe_write_text(workspace / "REPAIR_DRY_RUN.md", _render_repair_preview(preview))
    return preview


def _render_repair_preview(preview: dict[str, Any]) -> str:
    lines = [
        "# Repair Dry Run",
        "",
        f"- healthy: {preview['healthy']}",
        f"- action_count: {preview['action_count']}",
        f"- run_dir: `{preview.get('run_dir')}`",
        "",
        "## Actions",
        "",
    ]
    for action in preview["actions"]:
        lines.append(f"{action['step']}. {action['code']} ({action['source']}): {action['preview']}")
        if action.get("diff"):
            lines.extend(["", "```diff", action["diff"].rstrip(), "```", ""])
    lines.extend(["", "## Policy", "", preview["policy"], ""])
    return "\n".join(lines)
