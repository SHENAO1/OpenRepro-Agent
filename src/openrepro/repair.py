"""Repair-plan generation from diagnosis evidence."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import build_run_manifest, write_run_manifest
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


def apply_repair_actions(
    project_dir: Path,
    run_dir: Path | None = None,
    only: str = "manifest",
    confirm: bool = False,
) -> dict[str, Any]:
    """Apply explicitly confirmed low-risk repair actions."""
    if only != "manifest":
        raise ValueError("v0.6.1 repair apply only supports --only manifest.")
    if not confirm:
        raise ValueError("Repair apply requires --confirm.")

    project_dir = Path(project_dir)
    diagnosis = diagnose_project(project_dir, run_dir)
    target = Path(diagnosis["run_dir"]) if diagnosis.get("run_dir") else None
    issues = diagnosis.get("issues", [])
    manifest_issues = [issue for issue in issues if issue.get("code") in {"manifest_mismatch", "missing_manifest"}]
    actions: list[dict[str, Any]] = []

    if target is not None and target.exists() and manifest_issues:
        manifest = read_json(target / "manifest.json", default=None)
        manifest = manifest if isinstance(manifest, dict) else None
        command = _infer_command(target, manifest)
        if command is None:
            actions.append(
                {
                    "step": 1,
                    "code": "manifest_repair_skipped",
                    "target": str(target),
                    "modified": False,
                    "message": "Could not infer run command; manifest was not regenerated.",
                }
            )
        else:
            path = write_run_manifest(target, command)
            actions.append(
                {
                    "step": 1,
                    "code": "manifest_regenerated",
                    "target": str(path),
                    "command": command,
                    "modified": True,
                    "message": "Regenerated manifest.json from files currently present on disk.",
                }
            )
    else:
        actions.append(
            {
                "step": 1,
                "code": "no_manifest_repair_needed",
                "target": str(target) if target else None,
                "modified": False,
                "message": "No manifest mismatch or missing-manifest issue was found.",
            }
        )

    apply_result = {
        "schema_version": "0.6.1",
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "run_dir": str(target) if target else None,
        "only": only,
        "confirmed": confirm,
        "modified_file_count": sum(1 for action in actions if action.get("modified")),
        "actions": actions,
        "policy": "Applied only explicit manifest repairs; no scientific artifacts, configs, or experiment code were generated or modified.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "repair_apply.json", apply_result)
    safe_write_text(workspace / "REPAIR_APPLY.md", _render_repair_apply(apply_result))
    return apply_result


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


def _render_repair_apply(result: dict[str, Any]) -> str:
    lines = [
        "# Repair Apply",
        "",
        f"- run_dir: `{result.get('run_dir')}`",
        f"- only: {result['only']}",
        f"- confirmed: {result['confirmed']}",
        f"- modified_file_count: {result['modified_file_count']}",
        "",
        "## Actions",
        "",
    ]
    for action in result["actions"]:
        lines.append(f"{action['step']}. {action['code']}: {action['message']}")
        if action.get("target"):
            lines.append(f"   target: `{action['target']}`")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
