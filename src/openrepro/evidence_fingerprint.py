"""Evidence package source fingerprint helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .artifact_manager import sha256_file

EVIDENCE_FINGERPRINT_SCHEMA_VERSION = "1.0.1"

EXCLUDED_REPORT_PREFIXES = {
    "evidence_package.json",
    "evidence_package.md",
    "evidence_package.zip",
    "review_site_manifest.json",
    "review_site.zip",
    "dashboard_manifest.json",
    "dashboard.zip",
    "agent_board_manifest.json",
    "agent_board.zip",
    "evidence_explorer_manifest.json",
    "evidence_explorer.zip",
    "readiness_review.json",
    "READINESS_REVIEW.md",
    "readiness_review.zip",
    "readiness_review_validation.json",
    "READINESS_REVIEW_VALIDATION.md",
    "delivery_bundle.json",
    "DELIVERY_BUNDLE.md",
    "delivery_bundle.zip",
}
EXCLUDED_REPORT_DIRS = {"review_site", "dashboard", "agent_board", "evidence_explorer"}
EXCLUDED_PROJECT_RELATIVE_PATHS = {
    "handoff/EVIDENCE_PACKAGE.md",
    "handoff/COLLABORATION_PACK.md",
    "handoff/collaboration_pack.json",
    "handoff/collaboration_pack.zip",
    "workspace/REFRESH_RUN.md",
    "workspace/refresh_run.json",
    "workspace/refresh_run.zip",
    "workspace/ARTIFACT_FRESHNESS.md",
    "workspace/artifact_freshness.json",
    "workspace/REVIEW_ACTION_PLAN.md",
    "workspace/review_action_plan.json",
    "workspace/MULTI_AGENT_PLAN.md",
    "workspace/multi_agent_plan.json",
    "workspace/MULTI_AGENT_PLAN_VALIDATION.md",
    "workspace/multi_agent_plan_validation.json",
    "workspace/AGENT_DISPATCH.md",
    "workspace/agent_dispatch.json",
    "workspace/AGENT_EXEC_PLAN.md",
    "workspace/agent_exec_plan.json",
    "workspace/AGENT_ADAPTER.md",
    "workspace/agent_adapter.json",
    "workspace/AGENT_ADAPTER_VALIDATION.md",
    "workspace/agent_adapter_validation.json",
    "workspace/AGENT_SANDBOX_RUN.md",
    "workspace/agent_sandbox_run.json",
    "workspace/agent_sandbox_trajectory.jsonl",
    "workspace/agent_trajectory.jsonl",
    "workspace/PAPER_LINEAGE.md",
    "workspace/paper_lineage.json",
    "workspace/EVIDENCE_QUERY.md",
    "workspace/evidence_query.json",
    "workspace/WORKFLOW_PRESET.md",
    "workspace/workflow_preset.json",
    "workspace/WORKFLOW_EXECUTION.md",
    "workspace/workflow_execution.json",
    "workspace/workflow_events.jsonl",
    "workspace/ASSET_CATALOG.md",
    "workspace/ASSET_CATALOG_GRAPH.md",
    "workspace/asset_catalog.json",
    "workspace/ARTIFACT_CACHE.md",
    "workspace/artifact_cache.json",
    "workspace/ARTIFACT_CACHE_VALIDATION.md",
    "workspace/artifact_cache_validation.json",
    "workspace/ARTIFACT_CACHE_REMOTES.md",
    "workspace/artifact_cache_remotes.json",
    "workspace/ARTIFACT_CACHE_PUSH.md",
    "workspace/artifact_cache_push.json",
    "workspace/ARTIFACT_CACHE_PULL.md",
    "workspace/artifact_cache_pull.json",
    "workspace/CACHE_RESTORE_PLAN.md",
    "workspace/cache_restore_plan.json",
    "workspace/EVALUATION_REGISTRY.md",
    "workspace/evaluation_registry.json",
    "workspace/EVALUATION_RESULTS.md",
    "workspace/evaluation_results.json",
    "workspace/EXPERIMENT_LEADERBOARD.md",
    "workspace/experiment_leaderboard.json",
    "workspace/PIPELINE_PLAN.md",
    "workspace/pipeline_plan.json",
    "workspace/PIPELINE_VALIDATION.md",
    "workspace/pipeline_validation.json",
}
EXCLUDED_PROJECT_RELATIVE_DIRS = {"workspace/agents", "workspace/workflow_logs", "workspace/agent_sandbox"}


def _included_files(project_dir: Path) -> list[Path]:
    roots = [
        project_dir / "sources",
        project_dir / "workspace",
        project_dir / "experiments",
        project_dir / "outputs",
        project_dir / "handoff",
        project_dir / "reports",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(project_dir).as_posix()
            if relative in EXCLUDED_PROJECT_RELATIVE_PATHS:
                continue
            if any(relative.startswith(f"{directory}/") for directory in EXCLUDED_PROJECT_RELATIVE_DIRS):
                continue
            if path.is_relative_to(project_dir / "reports"):
                report_parts = path.relative_to(project_dir / "reports").parts
                if report_parts and report_parts[0] in EXCLUDED_REPORT_DIRS:
                    continue
            if path.parent == project_dir / "reports" and path.name in EXCLUDED_REPORT_PREFIXES:
                continue
            files.append(path)
    return sorted(files, key=lambda item: item.as_posix())


def evidence_source_fingerprint(project_dir: Path) -> dict[str, object]:
    """Hash project evidence inputs while excluding generated evidence package files."""
    project_dir = Path(project_dir)
    digest = hashlib.sha256()
    records: list[dict[str, object]] = []
    for path in _included_files(project_dir):
        try:
            relative = path.relative_to(project_dir).as_posix()
        except ValueError:
            relative = str(path)
        file_hash = sha256_file(path)
        size = path.stat().st_size
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("utf-8"))
        digest.update(b"\0")
        records.append(
            {
                "path": relative,
                "size_bytes": size,
                "sha256": file_hash,
            }
        )
    return {
        "schema_version": EVIDENCE_FINGERPRINT_SCHEMA_VERSION,
        "file_count": len(records),
        "sha256": digest.hexdigest(),
        "files": records,
    }


def evidence_package_status(project_dir: Path) -> dict[str, object]:
    """Return missing/current/stale status for the latest evidence package."""
    project_dir = Path(project_dir)
    json_path = project_dir / "reports" / "evidence_package.json"
    markdown_path = project_dir / "reports" / "evidence_package.md"
    current = evidence_source_fingerprint(project_dir)
    if not json_path.exists() or not markdown_path.exists():
        return {
            "status": "missing",
            "stale": True,
            "package_sha256": None,
            "current_sha256": current["sha256"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
        }
    try:
        import json

        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    package_fingerprint = data.get("source_fingerprint", {}) if isinstance(data, dict) else {}
    package_hash = package_fingerprint.get("sha256") if isinstance(package_fingerprint, dict) else None
    stale = package_hash != current["sha256"]
    return {
        "status": "stale" if stale else "current",
        "stale": stale,
        "package_sha256": package_hash,
        "current_sha256": current["sha256"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
