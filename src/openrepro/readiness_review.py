"""Final readiness review report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .acceptance_criteria import acceptance_criteria_summary
from .artifact_manager import sha256_file
from .collaboration_pack import collaboration_pack_summary
from .dashboard import dashboard_summary
from .evidence_fingerprint import evidence_package_status
from .freshness import artifact_freshness_summary
from .gaps import gaps_summary
from .project_profile import project_profile_summary
from .protocol_preflight import protocol_preflight_summary
from .refresh import refresh_run_summary
from .review_decisions import review_decision_summary
from .review_site import review_site_summary
from .reviewer_packet import reviewer_packet_summary
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

READINESS_REVIEW_SCHEMA_VERSION = "1.21.0"


def generate_readiness_review(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write reports/readiness_review.json and reports/READINESS_REVIEW.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    review = build_readiness_review(project_dir)
    json_path = project_dir / "reports" / "readiness_review.json"
    markdown_path = project_dir / "reports" / "READINESS_REVIEW.md"
    review["path"] = str(json_path)
    review["markdown_path"] = str(markdown_path)
    review["zip_path"] = str(project_dir / "reports" / "readiness_review.zip") if export_zip else None
    write_json(json_path, review)
    safe_write_text(markdown_path, _render_markdown(review))
    if export_zip:
        review["zip_path"] = str(_export_zip(project_dir, review))
        write_json(json_path, review)
    return review


def build_readiness_review(project_dir: Path) -> dict[str, Any]:
    """Build readiness review payload without writing files."""
    project_dir = Path(project_dir)
    profile = project_profile_summary(project_dir)
    acceptance = acceptance_criteria_summary(project_dir)
    evidence = evidence_package_status(project_dir)
    freshness = artifact_freshness_summary(project_dir)
    refresh = refresh_run_summary(project_dir)
    dashboard = dashboard_summary(project_dir)
    collaboration = collaboration_pack_summary(project_dir)
    review_site = review_site_summary(project_dir)
    reviewer_packet = reviewer_packet_summary(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    preflight = protocol_preflight_summary(project_dir)
    decisions = review_decision_summary(project_dir)
    checks = [
        _check(
            "project_profile_ready",
            "Project profile is ready.",
            profile["present"] and profile["status"] in {"ready", "ready_with_open_work"},
            profile,
            str(profile.get("top_command") or f"openrepro profile {project_dir}"),
        ),
        _check(
            "acceptance_criteria_ready",
            "Acceptance criteria are ready.",
            acceptance["present"] and acceptance["status"] == "ready",
            acceptance,
            str(acceptance.get("top_command") or f"openrepro acceptance {project_dir}"),
        ),
        _check(
            "evidence_package_current",
            "Evidence package is current.",
            evidence["status"] == "current" and not evidence["stale"],
            evidence,
            f"openrepro evidence-package {project_dir} --zip",
        ),
        _check(
            "artifact_freshness_current",
            "Artifact freshness graph is current.",
            freshness["present"] and freshness["status"] == "current",
            freshness,
            str(freshness.get("top_command") or f"openrepro freshness {project_dir}"),
        ),
        _check(
            "refresh_complete",
            "Latest refresh run completed.",
            refresh["present"] and refresh["status"] == "complete",
            refresh,
            str(refresh.get("top_command") or f"openrepro refresh {project_dir} --zip"),
        ),
        _check(
            "dashboard_ready",
            "Static dashboard is ready.",
            dashboard["present"] and dashboard["status"] == "ready",
            dashboard,
            str(dashboard.get("top_command") or f"openrepro dashboard {project_dir} --zip"),
        ),
        _check(
            "collaboration_pack_ready",
            "Collaboration pack has no open next safe commands.",
            collaboration["present"] and collaboration["status"] == "ready" and collaboration["next_safe_command_count"] == 0,
            collaboration,
            str(collaboration.get("top_command") or f"openrepro collaboration-pack {project_dir} --zip"),
        ),
        _check(
            "review_site_ready",
            "Static review site is ready.",
            review_site["present"] and review_site["status"] == "ready" and review_site["blocker_count"] == 0,
            review_site,
            str(review_site.get("top_command") or f"openrepro review-site {project_dir} --zip"),
        ),
        _check(
            "reviewer_packet_ready",
            "Reviewer packet is ready.",
            reviewer_packet["present"] and reviewer_packet["status"] == "ready" and reviewer_packet["open_action_count"] == 0,
            reviewer_packet,
            str(reviewer_packet.get("top_command") or f"openrepro reviewer-packet {project_dir} --zip"),
        ),
        _check(
            "scorecard_ready",
            "Readiness scorecard is ready.",
            scorecard["present"] and scorecard["overall_status"] == "ready",
            scorecard,
            f"openrepro scorecard {project_dir}",
        ),
        _check(
            "gaps_clear",
            "Reproduction gaps are clear.",
            gaps["present"] and gaps["status"] == "clear",
            gaps,
            str(gaps.get("top_suggested_command") or f"openrepro gaps {project_dir}"),
        ),
        _check(
            "protocol_preflight_ready",
            "Protocol preflight is ready.",
            preflight["present"] and preflight["status"] == "ready" and preflight["blocking_count"] == 0,
            preflight,
            str(preflight.get("top_command") or f"openrepro protocol-preflight {project_dir}"),
        ),
        _check(
            "review_decisions_clear",
            "Review decisions are clear.",
            decisions["unresolved_item_count"] == 0,
            decisions,
            str(decisions.get("top_command") or f"openrepro review-board {project_dir}"),
        ),
    ]
    blockers = [item for item in checks if item["status"] != "passed"]
    status = "ready_for_human_review" if not blockers else "needs_work"
    return {
        "schema_version": READINESS_REVIEW_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": blockers[0]["suggested_command"] if blockers else None,
        "check_count": len(checks),
        "passed_check_count": len(checks) - len(blockers),
        "blocker_count": len(blockers),
        "open_action_count": len(blockers),
        "checks": checks,
        "summary": {
            "readiness_score": scorecard.get("overall_score"),
            "acceptance_status": acceptance.get("status"),
            "evidence_package_status": evidence.get("status"),
            "freshness_status": freshness.get("status"),
            "dashboard_status": dashboard.get("status"),
        },
        "artifact_links": _artifact_links(project_dir),
        "policy": "Readiness reviews organize final human-review state only; they do not claim scientific reproduction success.",
    }


def readiness_review_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing readiness review summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "reports" / "readiness_review.json"
    markdown_path = project_dir / "reports" / "READINESS_REVIEW.md"
    zip_path = project_dir / "reports" / "readiness_review.zip"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "top_command": data.get("top_command"),
        "check_count": int(data.get("check_count", 0) or 0),
        "passed_check_count": int(data.get("passed_check_count", 0) or 0),
        "blocker_count": int(data.get("blocker_count", 0) or 0),
        "open_action_count": int(data.get("open_action_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _check(check_id: str, label: str, passed: bool, details: dict[str, Any], command: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "label": label,
        "status": "passed" if passed else "blocked",
        "severity": "blocking",
        "suggested_command": None if passed else command,
        "details": details,
    }


def _artifact_links(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "workspace" / "PROJECT_PROFILE.md",
        project_dir / "workspace" / "ACCEPTANCE_CRITERIA.md",
        project_dir / "reports" / "evidence_package.md",
        project_dir / "workspace" / "ARTIFACT_FRESHNESS.md",
        project_dir / "reports" / "dashboard" / "index.html",
        project_dir / "handoff" / "COLLABORATION_PACK.md",
        project_dir / "reports" / "review_site" / "index.html",
        project_dir / "reports" / "reviewer_packet.md",
    ]
    return [
        {
            "label": path.name,
            "path": relpath(path, project_dir),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for path in paths
    ]


def _export_zip(project_dir: Path, review: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "readiness_review.zip"
    files = [
        project_dir / "reports" / "readiness_review.json",
        project_dir / "reports" / "READINESS_REVIEW.md",
    ]
    files.extend(project_dir / str(item["path"]) for item in review.get("artifact_links", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _render_markdown(review: dict[str, Any]) -> str:
    check_rows = [
        "| Check | Status | Severity | Suggested command |",
        "| --- | --- | --- | --- |",
    ]
    for check in review["checks"]:
        check_rows.append(
            "| {check} | {status} | {severity} | `{command}` |".format(
                check=_cell(check["check_id"]),
                status=_cell(check["status"]),
                severity=_cell(check["severity"]),
                command=_cell(check.get("suggested_command") or ""),
            )
        )
    artifact_rows = [
        "| Artifact | Present | Path | SHA-256 |",
        "| --- | --- | --- | --- |",
    ]
    for item in review["artifact_links"]:
        artifact_rows.append(
            f"| {_cell(item['label'])} | {_cell(item['present'])} | `{_cell(item['path'])}` | `{_cell(item.get('sha256'))}` |"
        )
    return f"""# Readiness Review

- schema_version: {review['schema_version']}
- created_at: {review['created_at']}
- project_name: {review['project_name']}
- status: {review['status']}
- top_command: {review['top_command']}
- check_count: {review['check_count']}
- passed_check_count: {review['passed_check_count']}
- blocker_count: {review['blocker_count']}
- open_action_count: {review['open_action_count']}

## Summary

- readiness_score: {review['summary']['readiness_score']}
- acceptance_status: {review['summary']['acceptance_status']}
- evidence_package_status: {review['summary']['evidence_package_status']}
- freshness_status: {review['summary']['freshness_status']}
- dashboard_status: {review['summary']['dashboard_status']}

## Checks

{chr(10).join(check_rows)}

## Artifacts

{chr(10).join(artifact_rows)}

## Policy

{review['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
