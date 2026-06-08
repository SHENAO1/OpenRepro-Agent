"""Local GitHub PR comment summary generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .asset_build import asset_build_summary
from .artifact_manager import sha256_file
from .ci_integration import ci_summary
from .dashboard import dashboard_summary
from .evidence_fingerprint import evidence_package_status
from .local_ui import local_ui_summary
from .plugin_registry import plugin_registry_summary
from .promotion import promotion_summary
from .security_policy import security_summary
from .utils import iso_now, read_json, safe_write_text, write_json

GITHUB_PR_SUMMARY_SCHEMA_VERSION = "1.49.0"


def generate_github_pr_summary(
    project_dir: Path,
    *,
    pr_number: int | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
    repo_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate a local Markdown comment body for a GitHub PR."""
    project_dir = Path(project_dir)
    repo_dir = Path(repo_dir) if repo_dir else Path.cwd()
    ci = ci_summary(project_dir)
    ci_validation = _json_summary(project_dir / "workspace" / "ci_validation.json")
    local_ui = local_ui_summary(project_dir)
    asset_build = asset_build_summary(project_dir)
    plugins = plugin_registry_summary(project_dir)
    promotion = promotion_summary(project_dir)
    security = security_summary(project_dir)
    dashboard = dashboard_summary(project_dir)
    freshness = evidence_package_status(project_dir)
    git = _git_context(repo_dir, base_ref=base_ref, head_ref=head_ref)
    checks = _checks(ci, ci_validation, local_ui, asset_build, plugins, promotion, security, freshness)
    failed = [check for check in checks if check["required"] and not check["passed"]]
    warnings = [check for check in checks if not check["required"] and not check["passed"]]
    result = {
        "schema_version": GITHUB_PR_SUMMARY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "pr_number": pr_number,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "status": "blocked" if failed else "ready",
        "check_count": len(checks),
        "failed_check_count": len(failed),
        "warning_count": len(warnings),
        "checks": checks,
        "git": git,
        "summaries": {
            "ci": ci,
            "ci_validation": ci_validation,
            "local_ui": local_ui,
            "asset_build": asset_build,
            "plugins": plugins,
            "promotion": promotion,
            "security": security,
            "dashboard": dashboard,
            "evidence_freshness": freshness,
        },
        "guardrails": [
            "This artifact is a local PR comment draft only.",
            "It does not call GitHub APIs or inspect remote GitHub Actions results.",
            "It reports local workflow artifacts and local git metadata when available.",
        ],
        "policy": "GitHub PR summaries organize local engineering evidence for review; they do not prove remote CI success or scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "github_pr_summary.json", result)
    safe_write_text(project_dir / "workspace" / "GITHUB_PR_SUMMARY.md", _render_summary_markdown(result))
    safe_write_text(project_dir / "reports" / "pr_comment.md", _render_comment_markdown(result))
    return result


def github_pr_summary_status(project_dir: Path) -> dict[str, Any]:
    """Return existing GitHub PR summary status without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "github_pr_summary.json"
    markdown_path = project_dir / "workspace" / "GITHUB_PR_SUMMARY.md"
    comment_path = project_dir / "reports" / "pr_comment.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "comment_path": str(comment_path) if comment_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "check_count": int(data.get("check_count", 0) or 0),
        "failed_check_count": int(data.get("failed_check_count", 0) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "pr_number": data.get("pr_number"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _json_summary(path: Path) -> dict[str, Any]:
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "valid": data.get("valid"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _checks(
    ci: dict[str, Any],
    ci_validation: dict[str, Any],
    local_ui: dict[str, Any],
    asset_build: dict[str, Any],
    plugins: dict[str, Any],
    promotion: dict[str, Any],
    security: dict[str, Any],
    freshness: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _check("ci_workflow_present", bool(ci.get("present")), "Local CI workflow scaffold is present."),
        _check("ci_validation_passed", ci_validation.get("status") == "passed", "Local CI scaffold validation passed."),
        _check("local_ui_present", bool(local_ui.get("present")), "Local UI artifact is present."),
        _check("evidence_package_current", freshness.get("status") == "current", "Evidence package is current.", required=False),
        _check("asset_build_not_blocked", asset_build.get("status") not in {"blocked", "failed"}, "Asset build plan is not blocked.", required=False),
        _check("plugin_validation_not_failed", plugins.get("validation_status") != "failed", "Plugin validation is not failed.", required=False),
        _check("promotion_recorded", promotion.get("latest_state") in {"validated", "accepted", "released"}, "Promotion registry has a reviewed state.", required=False),
        _check("security_audit_not_failed", security.get("status") != "failed", "Security audit is not failed.", required=False),
    ]


def _check(name: str, passed: bool, message: str, *, required: bool = True) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "required": required, "message": message}


def _git_context(repo_dir: Path, *, base_ref: str | None, head_ref: str | None) -> dict[str, Any]:
    branch = _git(repo_dir, "branch", "--show-current")
    commit = _git(repo_dir, "rev-parse", "--short", "HEAD")
    status = _git(repo_dir, "status", "--short")
    diff_stat = None
    if base_ref and head_ref:
        diff_stat = _git(repo_dir, "diff", "--stat", f"{base_ref}...{head_ref}", timeout=10)
    return {
        "repo_dir": str(repo_dir),
        "branch": branch,
        "commit": commit,
        "dirty": bool(status),
        "status_short": status,
        "diff_stat": diff_stat,
    }


def _git(repo_dir: Path, *args: str, timeout: int = 5) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _render_summary_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# GitHub PR Summary",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- pr_number: {result['pr_number']}",
        f"- branch: {result['git'].get('branch')}",
        f"- commit: {result['git'].get('commit')}",
        f"- failed_check_count: {result['failed_check_count']}",
        f"- warning_count: {result['warning_count']}",
        "",
        "| Check | Required | Passed | Message |",
        "| --- | --- | --- | --- |",
    ]
    for check in result["checks"]:
        lines.append(f"| {_cell(check['name'])} | {_cell(check['required'])} | {_cell(check['passed'])} | {_cell(check['message'])} |")
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in result["guardrails"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _render_comment_markdown(result: dict[str, Any]) -> str:
    checks = "\n".join(
        f"- [{'x' if check['passed'] else ' '}] {_cell(check['name'])}: {_cell(check['message'])}"
        for check in result["checks"]
    )
    pr_label = f"PR #{result['pr_number']}" if result.get("pr_number") else "PR"
    return "\n".join(
        [
            f"## OpenRepro Local Review Summary ({pr_label})",
            "",
            f"Status: **{result['status']}**",
            "",
            f"- Project: `{result['project_name']}`",
            f"- Branch: `{result['git'].get('branch')}`",
            f"- Commit: `{result['git'].get('commit')}`",
            f"- Failed required checks: {result['failed_check_count']}",
            f"- Warnings: {result['warning_count']}",
            "",
            "### Checks",
            "",
            checks,
            "",
            "### Guardrails",
            "",
            "- Local summary only; no GitHub API calls were made.",
            "- Remote CI success is not inferred from this artifact.",
            "- Scientific reproduction is not asserted by this comment.",
            "",
        ]
    )


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
