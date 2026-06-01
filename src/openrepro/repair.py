"""Repair-plan generation from diagnosis evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .diagnostics import diagnose_project
from .utils import iso_now, safe_write_text, write_json


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
