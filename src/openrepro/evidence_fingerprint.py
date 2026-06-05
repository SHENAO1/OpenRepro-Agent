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
    "readiness_review.json",
    "READINESS_REVIEW.md",
    "readiness_review.zip",
    "readiness_review_validation.json",
    "READINESS_REVIEW_VALIDATION.md",
}
EXCLUDED_REPORT_DIRS = {"review_site", "dashboard"}
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
}


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
