"""Local content-addressed cache for project artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

ARTIFACT_CACHE_SCHEMA_VERSION = "1.39.0"
CACHE_SCAN_ROOTS = ("sources", "data", "experiments", "outputs", "workspace", "reports", "handoff")
CACHE_OUTPUTS = {
    "workspace/artifact_cache.json",
    "workspace/ARTIFACT_CACHE.md",
    "workspace/artifact_cache_validation.json",
    "workspace/ARTIFACT_CACHE_VALIDATION.md",
}


def add_artifact_cache(project_dir: Path, target: Path | None = None) -> dict[str, Any]:
    """Add project artifacts or one target path to the local cache index."""
    project_dir = Path(project_dir)
    selected_files = _collect_files(project_dir, target)
    previous = _read_index(project_dir)
    existing = {} if target is None else {str(entry.get("path")): entry for entry in _entries(previous)}
    created_at = iso_now()

    for path in selected_files:
        relative = _record_path(project_dir, path)
        size = path.stat().st_size
        digest = sha256_file(path)
        blob = _blob_path(project_dir, digest)
        blob.parent.mkdir(parents=True, exist_ok=True)
        copied = False
        if not blob.exists():
            shutil.copy2(path, blob)
            copied = True
        prior = existing.get(relative, {})
        existing[relative] = {
            "path": relative,
            "source_path": str(path),
            "size_bytes": size,
            "sha256": digest,
            "cache_path": relpath(blob, project_dir).replace("\\", "/"),
            "cached": blob.exists(),
            "copied": copied,
            "added_at": prior.get("added_at") or created_at,
            "updated_at": created_at,
        }

    cache = _build_index(project_dir, list(existing.values()), created_at=created_at)
    write_json(project_dir / "workspace" / "artifact_cache.json", cache)
    safe_write_text(project_dir / "workspace" / "ARTIFACT_CACHE.md", _render_markdown(cache))
    return cache


def artifact_cache_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing artifact cache summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "artifact_cache.json"
    markdown_path = project_dir / "workspace" / "ARTIFACT_CACHE.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "cached_file_count": int(data.get("cached_file_count", 0) or 0),
        "blob_count": int(data.get("blob_count", 0) or 0),
        "total_size_bytes": int(data.get("total_size_bytes", 0) or 0),
    }


def list_artifact_cache(project_dir: Path) -> dict[str, Any]:
    """Return cached artifact index records, generating the index when missing."""
    project_dir = Path(project_dir)
    cache = _read_index(project_dir)
    if not cache:
        cache = add_artifact_cache(project_dir)
    return {
        "schema_version": ARTIFACT_CACHE_SCHEMA_VERSION,
        "project_dir": str(project_dir),
        "cached_file_count": int(cache.get("cached_file_count", 0) or 0),
        "blob_count": int(cache.get("blob_count", 0) or 0),
        "entries": _entries(cache),
    }


def verify_artifact_cache(project_dir: Path) -> dict[str, Any]:
    """Verify that cache blobs exist and still match their recorded hashes."""
    project_dir = Path(project_dir)
    cache = _read_index(project_dir)
    entries = _entries(cache)
    records = [_verification_record(project_dir, entry) for entry in entries]
    missing_blob_count = sum(1 for record in records if not record["blob_present"])
    corrupt_blob_count = sum(1 for record in records if record["blob_present"] and not record["blob_valid"])
    source_changed_count = sum(1 for record in records if record["source_present"] and not record["source_current"])
    valid = missing_blob_count == 0 and corrupt_blob_count == 0
    result = {
        "schema_version": ARTIFACT_CACHE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "passed" if valid else "failed",
        "valid": valid,
        "cached_file_count": len(entries),
        "checked_file_count": len(records),
        "missing_blob_count": missing_blob_count,
        "corrupt_blob_count": corrupt_blob_count,
        "source_changed_count": source_changed_count,
        "records": records,
        "policy": "Artifact cache verification checks local cached bytes only; it does not verify scientific correctness.",
    }
    write_json(project_dir / "workspace" / "artifact_cache_validation.json", result)
    safe_write_text(project_dir / "workspace" / "ARTIFACT_CACHE_VALIDATION.md", _render_validation_markdown(result))
    return result


def gc_artifact_cache(project_dir: Path) -> dict[str, Any]:
    """Remove cached blobs that are not referenced by the current cache index."""
    project_dir = Path(project_dir)
    cache_root = _cache_root(project_dir)
    referenced = {_blob_path(project_dir, str(entry.get("sha256"))) for entry in _entries(_read_index(project_dir)) if entry.get("sha256")}
    removed: list[dict[str, Any]] = []
    retained = 0
    if cache_root.exists():
        for path in sorted((item for item in cache_root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
            if path in referenced:
                retained += 1
                continue
            removed.append({"path": relpath(path, project_dir).replace("\\", "/"), "size_bytes": path.stat().st_size})
            path.unlink()
        _remove_empty_dirs(cache_root)
    return {
        "schema_version": ARTIFACT_CACHE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "cache_root": str(cache_root),
        "status": "complete",
        "removed_blob_count": len(removed),
        "retained_blob_count": retained,
        "removed_blobs": removed,
        "policy": "Artifact cache garbage collection removes only unreferenced local cache blobs.",
    }


def _read_index(project_dir: Path) -> dict[str, Any]:
    data = read_json(Path(project_dir) / "workspace" / "artifact_cache.json", default={}) or {}
    return data if isinstance(data, dict) else {}


def _entries(cache: dict[str, Any]) -> list[dict[str, Any]]:
    entries = cache.get("entries", []) if isinstance(cache, dict) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def _build_index(project_dir: Path, entries: list[dict[str, Any]], *, created_at: str) -> dict[str, Any]:
    entries = sorted(entries, key=lambda item: str(item.get("path") or ""))
    unique_blobs = {str(entry.get("sha256")): entry for entry in entries if entry.get("sha256")}
    return {
        "schema_version": ARTIFACT_CACHE_SCHEMA_VERSION,
        "created_at": created_at,
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if entries else "empty",
        "cache_root": str(_cache_root(project_dir)),
        "cached_file_count": len(entries),
        "blob_count": len(unique_blobs),
        "total_size_bytes": sum(int(entry.get("size_bytes", 0) or 0) for entry in entries),
        "blob_size_bytes": sum(int(entry.get("size_bytes", 0) or 0) for entry in unique_blobs.values()),
        "entries": entries,
        "policy": "The local artifact cache stores observed project files by SHA-256 for offline reuse and drift checks; it is not a provenance guarantee.",
    }


def _cache_root(project_dir: Path) -> Path:
    return Path(project_dir) / ".openrepro" / "cache" / "sha256"


def _blob_path(project_dir: Path, digest: str) -> Path:
    digest = str(digest)
    return _cache_root(project_dir) / digest[:2] / digest


def _collect_files(project_dir: Path, target: Path | None) -> list[Path]:
    project_dir = Path(project_dir)
    if target is None:
        roots = [project_dir / root for root in CACHE_SCAN_ROOTS]
        files = [path for root in roots if root.exists() for path in root.rglob("*") if path.is_file()]
    else:
        resolved = _resolve_target(project_dir, target)
        if not resolved.exists():
            raise FileNotFoundError(f"Cache target not found: {target}")
        files = [resolved] if resolved.is_file() else [path for path in resolved.rglob("*") if path.is_file()]
    return sorted((path for path in files if _is_cacheable(project_dir, path)), key=lambda item: item.as_posix())


def _resolve_target(project_dir: Path, target: Path) -> Path:
    target = Path(target)
    if target.is_absolute():
        return target
    project_relative = Path(project_dir) / target
    if project_relative.exists():
        return project_relative
    return target


def _is_cacheable(project_dir: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    relative = _record_path(project_dir, path)
    if relative in CACHE_OUTPUTS:
        return False
    if relative.startswith(".openrepro/"):
        return False
    return True


def _record_path(project_dir: Path, path: Path) -> str:
    return relpath(Path(path), Path(project_dir)).replace("\\", "/")


def _source_path(project_dir: Path, entry: dict[str, Any]) -> Path:
    raw_path = str(entry.get("path") or "")
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else Path(project_dir) / raw_path


def _cache_path(project_dir: Path, entry: dict[str, Any]) -> Path:
    raw_path = str(entry.get("cache_path") or "")
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else Path(project_dir) / raw_path


def _verification_record(project_dir: Path, entry: dict[str, Any]) -> dict[str, Any]:
    expected_hash = str(entry.get("sha256") or "")
    blob = _cache_path(project_dir, entry)
    blob_present = blob.exists() and blob.is_file()
    blob_hash = sha256_file(blob) if blob_present else None
    source = _source_path(project_dir, entry)
    source_present = source.exists() and source.is_file()
    source_hash = sha256_file(source) if source_present else None
    return {
        "path": entry.get("path"),
        "sha256": expected_hash,
        "cache_path": entry.get("cache_path"),
        "blob_present": blob_present,
        "blob_valid": blob_hash == expected_hash if blob_present else False,
        "source_present": source_present,
        "source_current": source_hash == expected_hash if source_present else False,
        "source_sha256": source_hash,
    }


def _remove_empty_dirs(cache_root: Path) -> None:
    if not cache_root.exists():
        return
    for directory in sorted((item for item in cache_root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(cache: dict[str, Any]) -> str:
    lines = [
        "# Artifact Cache",
        "",
        f"- schema_version: {cache['schema_version']}",
        f"- status: {cache['status']}",
        f"- cached_file_count: {cache['cached_file_count']}",
        f"- blob_count: {cache['blob_count']}",
        f"- total_size_bytes: {cache['total_size_bytes']}",
        f"- cache_root: `{cache['cache_root']}`",
        "",
        "| Path | Size bytes | SHA-256 | Cache path |",
        "| --- | --- | --- | --- |",
    ]
    for entry in cache["entries"][:250]:
        lines.append(
            f"| {_cell(entry.get('path'))} | {_cell(entry.get('size_bytes'))} | `{_cell(entry.get('sha256'))}` | {_cell(entry.get('cache_path'))} |"
        )
    if len(cache["entries"]) > 250:
        lines.append(f"| ... | ... | {len(cache['entries']) - 250} more entries omitted | ... |")
    lines.extend(["", "## Policy", "", cache["policy"], ""])
    return "\n".join(lines)


def _render_validation_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Artifact Cache Validation",
        "",
        f"- status: {result['status']}",
        f"- valid: {result['valid']}",
        f"- cached_file_count: {result['cached_file_count']}",
        f"- missing_blob_count: {result['missing_blob_count']}",
        f"- corrupt_blob_count: {result['corrupt_blob_count']}",
        f"- source_changed_count: {result['source_changed_count']}",
        "",
        "| Path | Blob present | Blob valid | Source current |",
        "| --- | --- | --- | --- |",
    ]
    for record in result["records"][:250]:
        lines.append(
            f"| {_cell(record.get('path'))} | {_cell(record.get('blob_present'))} | {_cell(record.get('blob_valid'))} | {_cell(record.get('source_current'))} |"
        )
    if len(result["records"]) > 250:
        lines.append(f"| ... | ... | ... | {len(result['records']) - 250} more records omitted |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
