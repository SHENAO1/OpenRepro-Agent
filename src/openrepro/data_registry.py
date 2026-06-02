"""Project data source registry and validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, safe_write_text, slugify, write_json, read_json

DATA_INDEX_SCHEMA_VERSION = "1.3.0"


def _index_path(project_dir: Path) -> Path:
    return Path(project_dir) / "workspace" / "data_index.json"


def _validation_path(project_dir: Path) -> Path:
    return Path(project_dir) / "workspace" / "data_validation.json"


def _empty_index(project_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": DATA_INDEX_SCHEMA_VERSION,
        "created_at": None,
        "project_dir": str(Path(project_dir)),
        "sources": [],
        "summary": {"registered_count": 0, "role_counts": {}},
        "policy": "Data registry records file provenance only; it does not verify scientific correctness.",
    }


def load_data_index(project_dir: Path) -> dict[str, Any]:
    """Load workspace/data_index.json, returning an empty registry when missing."""
    project_dir = Path(project_dir).resolve()
    index = read_json(_index_path(project_dir), default=None)
    if not isinstance(index, dict):
        return _empty_index(project_dir)
    sources = index.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    index["sources"] = [source for source in sources if isinstance(source, dict)]
    return index


def _write_data_index(project_dir: Path, index: dict[str, Any]) -> None:
    role_counts: dict[str, int] = {}
    for source in index.get("sources", []):
        role = str(source.get("role") or "dataset")
        role_counts[role] = role_counts.get(role, 0) + 1
    index["schema_version"] = DATA_INDEX_SCHEMA_VERSION
    if not index.get("created_at"):
        index["created_at"] = iso_now()
    index["updated_at"] = iso_now()
    index["summary"] = {
        "registered_count": len(index.get("sources", [])),
        "role_counts": role_counts,
    }
    write_json(_index_path(project_dir), index)
    safe_write_text(Path(project_dir) / "workspace" / "DATA_INDEX.md", _render_data_index_markdown(index))


def _resolve_data_path(project_dir: Path, path: Path) -> Path:
    project_dir = Path(project_dir).resolve()
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    project_candidate = (project_dir / path).resolve()
    if project_candidate.exists():
        return project_candidate
    return (Path.cwd() / path).resolve()


def _path_record(project_dir: Path, path: Path) -> tuple[str, str]:
    project_dir = Path(project_dir).resolve()
    try:
        return str(path.relative_to(project_dir)).replace("\\", "/"), "project_relative"
    except ValueError:
        return str(path), "absolute"


def _path_from_record(project_dir: Path, source: dict[str, Any]) -> Path:
    project_dir = Path(project_dir).resolve()
    path = Path(str(source.get("path") or ""))
    if source.get("path_mode") == "project_relative":
        return project_dir / path
    return path


def _data_id(role: str, path: Path) -> str:
    payload = f"{role}:{path}".encode("utf-8")
    suffix = hashlib.sha256(payload).hexdigest()[:8]
    return slugify(f"{role}_{path.stem}_{suffix}")


def register_data(
    project_dir: Path,
    path: Path,
    role: str = "dataset",
    note: str = "",
    source: str = "manual",
) -> dict[str, Any]:
    """Register a local data file with size and SHA-256 provenance."""
    project_dir = Path(project_dir).resolve()
    resolved = _resolve_data_path(project_dir, path)
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"Data file not found: {resolved}")
    role = slugify(role or "dataset")
    path_value, path_mode = _path_record(project_dir, resolved)
    record = {
        "data_id": _data_id(role, resolved),
        "role": role,
        "path": path_value,
        "path_mode": path_mode,
        "source": source or "manual",
        "note": note,
        "registered_at": iso_now(),
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "status": "registered",
    }
    index = load_data_index(project_dir)
    sources = [item for item in index.get("sources", []) if item.get("data_id") != record["data_id"]]
    sources.append(record)
    index["sources"] = sorted(sources, key=lambda item: str(item.get("data_id")))
    _write_data_index(project_dir, index)
    return record


def data_contract(project_dir: Path) -> dict[str, Any]:
    """Return the registry contract used by experiment specs."""
    index = load_data_index(project_dir)
    sources = []
    for source in index.get("sources", []):
        sources.append(
            {
                "data_id": source.get("data_id"),
                "role": source.get("role"),
                "path": source.get("path"),
                "path_mode": source.get("path_mode"),
                "size_bytes": source.get("size_bytes"),
                "sha256": source.get("sha256"),
            }
        )
    return {
        "schema_version": DATA_INDEX_SCHEMA_VERSION,
        "registered_data": sorted(sources, key=lambda item: str(item.get("data_id"))),
    }


def data_index_summary(project_dir: Path) -> dict[str, Any]:
    """Inspect registered data without mutating files."""
    project_dir = Path(project_dir).resolve()
    index = load_data_index(project_dir)
    entries: list[dict[str, Any]] = []
    for source in index.get("sources", []):
        data_path = _path_from_record(project_dir, source)
        exists = data_path.exists() and data_path.is_file()
        current_hash = sha256_file(data_path) if exists else None
        current_size = data_path.stat().st_size if exists else None
        if not exists:
            status = "missing"
        elif current_hash != source.get("sha256"):
            status = "hash_mismatch"
        else:
            status = "current"
        entries.append(
            {
                "data_id": source.get("data_id"),
                "role": source.get("role"),
                "path": str(data_path),
                "registered_path": source.get("path"),
                "path_mode": source.get("path_mode"),
                "status": status,
                "valid": status == "current",
                "size_bytes": source.get("size_bytes"),
                "current_size_bytes": current_size,
                "sha256": source.get("sha256"),
                "current_sha256": current_hash,
                "note": source.get("note"),
            }
        )
    status_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status") or "unknown")
        role = str(entry.get("role") or "dataset")
        status_counts[status] = status_counts.get(status, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1
    invalid_count = sum(count for status, count in status_counts.items() if status != "current")
    return {
        "schema_version": DATA_INDEX_SCHEMA_VERSION,
        "index_path": str(_index_path(project_dir)),
        "index_exists": _index_path(project_dir).exists(),
        "registered_count": len(entries),
        "valid_count": status_counts.get("current", 0),
        "invalid_count": invalid_count,
        "missing_count": status_counts.get("missing", 0),
        "hash_mismatch_count": status_counts.get("hash_mismatch", 0),
        "status_counts": status_counts,
        "role_counts": role_counts,
        "sources": entries,
    }


def validate_data_index(project_dir: Path) -> dict[str, Any]:
    """Validate registered data files and write workspace validation artifacts."""
    project_dir = Path(project_dir).resolve()
    summary = data_index_summary(project_dir)
    errors = []
    for source in summary["sources"]:
        if source["status"] == "missing":
            errors.append(f"Missing registered data: {source['data_id']}")
        elif source["status"] == "hash_mismatch":
            errors.append(f"SHA-256 mismatch for registered data: {source['data_id']}")
    result = {
        "schema_version": DATA_INDEX_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "valid": not errors,
        "errors": errors,
        "summary": summary,
        "policy": "Data validation checks registered file presence and hashes only; it does not verify scientific correctness.",
    }
    write_json(_validation_path(project_dir), result)
    safe_write_text(project_dir / "workspace" / "DATA_VALIDATION.md", _render_data_validation_markdown(result))
    return result


def _render_data_index_markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Data Index",
        "",
        f"- schema_version: {index.get('schema_version')}",
        f"- registered_count: {index.get('summary', {}).get('registered_count', 0)}",
        "",
        "| Data ID | Role | Path | Size | SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for source in index.get("sources", []):
        lines.append(
            "| {data_id} | {role} | `{path}` | {size} | {sha} |".format(
                data_id=source.get("data_id"),
                role=source.get("role"),
                path=source.get("path"),
                size=source.get("size_bytes"),
                sha=str(source.get("sha256") or "")[:12],
            )
        )
    lines.extend(["", "## Policy", "", str(index.get("policy") or ""), ""])
    return "\n".join(lines)


def _render_data_validation_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Data Validation",
        "",
        f"- valid: {result['valid']}",
        f"- registered_count: {summary['registered_count']}",
        f"- invalid_count: {summary['invalid_count']}",
        f"- status_counts: {summary['status_counts']}",
        f"- errors: {result['errors']}",
        "",
        "## Policy",
        "",
        result["policy"],
        "",
    ]
    return "\n".join(lines)
