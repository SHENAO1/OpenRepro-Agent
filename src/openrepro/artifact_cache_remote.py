"""Remote operations for the local artifact cache."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .artifact_cache import ARTIFACT_CACHE_SCHEMA_VERSION, add_artifact_cache, list_artifact_cache
from .artifact_manager import sha256_file
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

ARTIFACT_CACHE_REMOTE_SCHEMA_VERSION = "1.41.0"
SUPPORTED_REMOTE_TYPES = {"local"}


def configure_cache_remote(
    project_dir: Path,
    *,
    name: str,
    uri: str,
    remote_type: str = "local",
    make_default: bool = False,
) -> dict[str, Any]:
    """Add or update an artifact cache remote configuration."""
    project_dir = Path(project_dir)
    remote_type = _normalize_remote_type(remote_type)
    name = _normalize_name(name)
    remotes = _remote_entries(project_dir)
    existing = {remote["name"]: remote for remote in remotes}
    created_at = existing.get(name, {}).get("created_at") or iso_now()
    existing[name] = {
        "name": name,
        "type": remote_type,
        "uri": uri,
        "created_at": created_at,
        "updated_at": iso_now(),
        "default": make_default,
        "supported": remote_type in SUPPORTED_REMOTE_TYPES,
    }
    if make_default or not any(remote.get("default") for remote in existing.values()):
        for remote_name, remote in existing.items():
            remote["default"] = remote_name == name
    result = _remote_index(project_dir, list(existing.values()))
    write_json(project_dir / "workspace" / "artifact_cache_remotes.json", result)
    safe_write_text(project_dir / "workspace" / "ARTIFACT_CACHE_REMOTES.md", _render_remotes_markdown(result))
    return result


def list_cache_remotes(project_dir: Path) -> dict[str, Any]:
    """Return configured cache remotes."""
    project_dir = Path(project_dir)
    result = _remote_index(project_dir, _remote_entries(project_dir))
    write_json(project_dir / "workspace" / "artifact_cache_remotes.json", result)
    safe_write_text(project_dir / "workspace" / "ARTIFACT_CACHE_REMOTES.md", _render_remotes_markdown(result))
    return result


def push_artifact_cache(project_dir: Path, *, remote: str | None = None) -> dict[str, Any]:
    """Push local cache blobs and index metadata to a configured remote."""
    project_dir = Path(project_dir)
    cache = list_artifact_cache(project_dir)
    remote_config = _remote(project_dir, remote)
    remote_root = _local_remote_root(project_dir, remote_config)
    copied = []
    skipped = []
    for entry in cache["entries"]:
        local_blob = project_dir / str(entry.get("cache_path"))
        remote_blob = remote_root / "sha256" / str(entry.get("sha256", ""))[:2] / str(entry.get("sha256"))
        if not local_blob.exists():
            skipped.append({"path": entry.get("path"), "reason": "missing_local_blob"})
            continue
        remote_blob.parent.mkdir(parents=True, exist_ok=True)
        if remote_blob.exists() and sha256_file(remote_blob) == entry.get("sha256"):
            skipped.append({"path": entry.get("path"), "reason": "already_present"})
            continue
        shutil.copy2(local_blob, remote_blob)
        copied.append({"path": entry.get("path"), "sha256": entry.get("sha256"), "remote_path": str(remote_blob)})
    manifest = _remote_manifest(project_dir, remote_config, cache)
    write_json(remote_root / "openrepro_cache_remote.json", manifest)
    result = {
        "schema_version": ARTIFACT_CACHE_REMOTE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "remote": remote_config,
        "status": "complete",
        "cached_file_count": cache["cached_file_count"],
        "copied_blob_count": len(copied),
        "skipped_blob_count": len(skipped),
        "copied_blobs": copied,
        "skipped_blobs": skipped,
        "remote_manifest_path": str(remote_root / "openrepro_cache_remote.json"),
        "policy": "Remote cache push copies local content-addressed blobs only; it does not verify provenance or scientific correctness.",
    }
    write_json(project_dir / "workspace" / "artifact_cache_push.json", result)
    safe_write_text(project_dir / "workspace" / "ARTIFACT_CACHE_PUSH.md", _render_transfer_markdown(result, "Artifact Cache Push"))
    return result


def pull_artifact_cache(project_dir: Path, *, remote: str | None = None) -> dict[str, Any]:
    """Pull cache blobs and remote index metadata from a configured remote."""
    project_dir = Path(project_dir)
    remote_config = _remote(project_dir, remote)
    remote_root = _local_remote_root(project_dir, remote_config)
    manifest = read_json(remote_root / "openrepro_cache_remote.json", default={}) or {}
    if not isinstance(manifest, dict) or not manifest:
        raise FileNotFoundError(f"Remote cache manifest not found: {remote_root / 'openrepro_cache_remote.json'}")
    copied = []
    skipped = []
    entries = manifest.get("entries", []) if isinstance(manifest.get("entries"), list) else []
    for entry in entries:
        digest = str(entry.get("sha256") or "")
        remote_blob = remote_root / "sha256" / digest[:2] / digest
        local_blob = project_dir / ".openrepro" / "cache" / "sha256" / digest[:2] / digest
        if not remote_blob.exists():
            skipped.append({"path": entry.get("path"), "reason": "missing_remote_blob"})
            continue
        local_blob.parent.mkdir(parents=True, exist_ok=True)
        if local_blob.exists() and sha256_file(local_blob) == digest:
            skipped.append({"path": entry.get("path"), "reason": "already_present"})
            continue
        shutil.copy2(remote_blob, local_blob)
        copied.append({"path": entry.get("path"), "sha256": digest, "cache_path": relpath(local_blob, project_dir).replace("\\", "/")})
    cache = _cache_from_remote_manifest(project_dir, manifest, entries)
    write_json(project_dir / "workspace" / "artifact_cache.json", cache)
    result = {
        "schema_version": ARTIFACT_CACHE_REMOTE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "remote": remote_config,
        "status": "complete",
        "cached_file_count": cache["cached_file_count"],
        "copied_blob_count": len(copied),
        "skipped_blob_count": len(skipped),
        "copied_blobs": copied,
        "skipped_blobs": skipped,
        "remote_manifest_path": str(remote_root / "openrepro_cache_remote.json"),
        "policy": "Remote cache pull copies content-addressed blobs into the local cache only; it does not restore source files by itself.",
    }
    write_json(project_dir / "workspace" / "artifact_cache_pull.json", result)
    safe_write_text(project_dir / "workspace" / "ARTIFACT_CACHE_PULL.md", _render_transfer_markdown(result, "Artifact Cache Pull"))
    return result


def restore_artifact_cache(
    project_dir: Path,
    *,
    remote: str | None = None,
    confirm: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Plan or restore source files from cached blobs."""
    project_dir = Path(project_dir)
    if remote:
        pull_artifact_cache(project_dir, remote=remote)
    cache = list_artifact_cache(project_dir)
    actions = []
    restored = []
    skipped = []
    for entry in cache["entries"]:
        source = project_dir / str(entry.get("path"))
        blob = project_dir / str(entry.get("cache_path"))
        current_hash = sha256_file(source) if source.exists() and source.is_file() else None
        desired_hash = str(entry.get("sha256") or "")
        source_current = current_hash == desired_hash
        action = "none" if source_current else "restore_missing" if not source.exists() else "restore_changed" if overwrite else "skip_changed"
        record = {
            "path": entry.get("path"),
            "sha256": desired_hash,
            "cache_path": entry.get("cache_path"),
            "source_present": source.exists(),
            "source_current": source_current,
            "action": action,
        }
        actions.append(record)
        if action.startswith("restore") and confirm:
            if not blob.exists():
                skipped.append({**record, "reason": "missing_local_blob"})
                continue
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(blob, source)
            restored.append(record)
        elif action != "none":
            skipped.append(record)
    result = {
        "schema_version": ARTIFACT_CACHE_REMOTE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "remote_name": remote,
        "confirmed": confirm,
        "overwrite": overwrite,
        "status": "restored" if restored else "planned",
        "action_count": len(actions),
        "restore_action_count": sum(1 for action in actions if str(action.get("action", "")).startswith("restore")),
        "restored_count": len(restored),
        "skipped_count": len(skipped),
        "actions": actions,
        "restored": restored,
        "skipped": skipped,
        "policy": "Cache restore copies previously cached bytes only when confirmed; review changed-source actions before using --overwrite.",
    }
    write_json(project_dir / "workspace" / "cache_restore_plan.json", result)
    safe_write_text(project_dir / "workspace" / "CACHE_RESTORE_PLAN.md", _render_restore_markdown(result))
    return result


def _remote_entries(project_dir: Path) -> list[dict[str, Any]]:
    data = read_json(Path(project_dir) / "workspace" / "artifact_cache_remotes.json", default={}) or {}
    if not isinstance(data, dict):
        return []
    remotes = data.get("remotes", [])
    return [remote for remote in remotes if isinstance(remote, dict)]


def _remote_index(project_dir: Path, remotes: list[dict[str, Any]]) -> dict[str, Any]:
    remotes = sorted(remotes, key=lambda item: str(item.get("name") or ""))
    default_remote = next((remote.get("name") for remote in remotes if remote.get("default")), None)
    return {
        "schema_version": ARTIFACT_CACHE_REMOTE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": Path(project_dir).name,
        "project_dir": str(Path(project_dir)),
        "status": "ready" if remotes else "empty",
        "remote_count": len(remotes),
        "default_remote": default_remote,
        "remotes": remotes,
        "policy": "Cache remotes point to external or local blob stores; only local remotes are executable in this release.",
    }


def _remote(project_dir: Path, name: str | None) -> dict[str, Any]:
    remotes = _remote_entries(project_dir)
    selected = name or next((remote.get("name") for remote in remotes if remote.get("default")), None)
    if not selected:
        raise ValueError("No cache remote configured. Use openrepro cache remote-add first.")
    for remote in remotes:
        if remote.get("name") == selected:
            if remote.get("type") not in SUPPORTED_REMOTE_TYPES:
                raise ValueError(f"Remote type is configured but not executable in this release: {remote.get('type')}")
            return remote
    raise ValueError(f"Cache remote not found: {selected}")


def _local_remote_root(project_dir: Path, remote: dict[str, Any]) -> Path:
    uri = str(remote.get("uri") or "")
    path = Path(uri)
    return path if path.is_absolute() else Path(project_dir) / path


def _remote_manifest(project_dir: Path, remote: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_CACHE_REMOTE_SCHEMA_VERSION,
        "artifact_cache_schema_version": ARTIFACT_CACHE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": Path(project_dir).name,
        "remote": remote,
        "cached_file_count": cache.get("cached_file_count", 0),
        "blob_count": cache.get("blob_count", 0),
        "entries": cache.get("entries", []),
    }


def _cache_from_remote_manifest(project_dir: Path, manifest: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    for entry in entries:
        digest = str(entry.get("sha256") or "")
        normalized.append(
            {
                **entry,
                "source_path": str(Path(project_dir) / str(entry.get("path"))),
                "cache_path": f".openrepro/cache/sha256/{digest[:2]}/{digest}",
                "cached": (Path(project_dir) / ".openrepro" / "cache" / "sha256" / digest[:2] / digest).exists(),
                "updated_at": iso_now(),
            }
        )
    unique_blobs = {entry.get("sha256"): entry for entry in normalized if entry.get("sha256")}
    return {
        "schema_version": ARTIFACT_CACHE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": Path(project_dir).name,
        "project_dir": str(Path(project_dir)),
        "status": "ready" if normalized else "empty",
        "cache_root": str(Path(project_dir) / ".openrepro" / "cache" / "sha256"),
        "cached_file_count": len(normalized),
        "blob_count": len(unique_blobs),
        "total_size_bytes": sum(int(entry.get("size_bytes", 0) or 0) for entry in normalized),
        "blob_size_bytes": sum(int(entry.get("size_bytes", 0) or 0) for entry in unique_blobs.values()),
        "entries": sorted(normalized, key=lambda item: str(item.get("path") or "")),
        "remote_manifest_created_at": manifest.get("created_at"),
        "policy": "The local artifact cache stores observed project files by SHA-256 for offline reuse and drift checks; it is not a provenance guarantee.",
    }


def _normalize_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        raise ValueError("Remote name cannot be empty.")
    return value


def _normalize_remote_type(remote_type: str) -> str:
    value = (remote_type or "local").strip().lower()
    if value not in {"local", "s3", "ssh"}:
        raise ValueError("Remote type must be one of: local, s3, ssh")
    return value


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_remotes_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Artifact Cache Remotes",
        "",
        f"- status: {result['status']}",
        f"- remote_count: {result['remote_count']}",
        f"- default_remote: {result['default_remote']}",
        "",
        "| Name | Type | URI | Default | Supported |",
        "| --- | --- | --- | --- | --- |",
    ]
    for remote in result["remotes"]:
        lines.append(f"| {_cell(remote.get('name'))} | {_cell(remote.get('type'))} | {_cell(remote.get('uri'))} | {_cell(remote.get('default'))} | {_cell(remote.get('supported'))} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _render_transfer_markdown(result: dict[str, Any], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"- status: {result['status']}",
        f"- remote: {result['remote'].get('name')}",
        f"- cached_file_count: {result['cached_file_count']}",
        f"- copied_blob_count: {result['copied_blob_count']}",
        f"- skipped_blob_count: {result['skipped_blob_count']}",
        f"- remote_manifest_path: `{result['remote_manifest_path']}`",
        "",
        "## Copied",
        "",
        "| Path | SHA-256 |",
        "| --- | --- |",
    ]
    for item in result["copied_blobs"][:250]:
        lines.append(f"| {_cell(item.get('path'))} | `{_cell(item.get('sha256'))}` |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _render_restore_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Cache Restore Plan",
        "",
        f"- status: {result['status']}",
        f"- confirmed: {result['confirmed']}",
        f"- overwrite: {result['overwrite']}",
        f"- action_count: {result['action_count']}",
        f"- restore_action_count: {result['restore_action_count']}",
        f"- restored_count: {result['restored_count']}",
        "",
        "| Path | Present | Current | Action |",
        "| --- | --- | --- | --- |",
    ]
    for action in result["actions"][:250]:
        lines.append(f"| {_cell(action.get('path'))} | {_cell(action.get('source_present'))} | {_cell(action.get('source_current'))} | {_cell(action.get('action'))} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
