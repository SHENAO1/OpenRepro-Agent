"""Run lineage generation for auditable project state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .utils import iso_now, read_json, safe_write_text, write_json

LINEAGE_SCHEMA_VERSION = "0.6.0"


def _hash_file(path: Path) -> str | None:
    return sha256_file(path) if path.exists() and path.is_file() else None


def _run_config_path(project_dir: Path, run_dir: Path) -> Path:
    snapshot = run_dir / "configs" / "project_config_snapshot.yaml"
    return snapshot if snapshot.exists() else project_dir / "project_config.yaml"


def _lineage_entry(project_dir: Path, run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path, default={}) or {}
    command = str(manifest.get("command") or "unknown") if isinstance(manifest, dict) else "unknown"
    source_index = project_dir / "workspace" / "source_index.json"
    verified_candidates = project_dir / "workspace" / "verified_candidates.json"
    config_path = _run_config_path(project_dir, run_dir)
    hashes = {
        "manifest_sha256": _hash_file(manifest_path),
        "config_sha256": _hash_file(config_path),
        "source_index_sha256": _hash_file(source_index),
        "verified_candidates_sha256": _hash_file(verified_candidates),
    }
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "parent_command": command,
        "created_at": manifest.get("created_at") if isinstance(manifest, dict) else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "config_path": str(config_path) if config_path.exists() else None,
        "source_index_path": str(source_index) if source_index.exists() else None,
        "verified_candidates_path": str(verified_candidates) if verified_candidates.exists() else None,
        "hashes": hashes,
        "provenance_complete": all(
            value is not None
            for key, value in hashes.items()
            if key != "verified_candidates_sha256"
        ),
        "verified_candidates_present": hashes["verified_candidates_sha256"] is not None,
    }


def generate_run_lineage(project_dir: Path) -> dict[str, Any]:
    """Write workspace/run_lineage.json and workspace/RUN_LINEAGE.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    entries = [_lineage_entry(project_dir, run_dir) for run_dir in reversed(list_run_dirs(project_dir))]
    lineage = {
        "schema_version": LINEAGE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "run_count": len(entries),
        "runs": entries,
        "policy": "Run lineage records file hashes and workflow evidence only; it does not claim reproduction success.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "run_lineage.json", lineage)
    safe_write_text(workspace / "RUN_LINEAGE.md", _render_lineage_markdown(lineage))
    return lineage


def _short_hash(value: str | None) -> str:
    return value[:12] if value else "missing"


def _render_lineage_markdown(lineage: dict[str, Any]) -> str:
    lines = [
        "# Run Lineage",
        "",
        f"- schema_version: {lineage['schema_version']}",
        f"- run_count: {lineage['run_count']}",
        f"- project_dir: `{lineage['project_dir']}`",
        "",
        "| Run | Command | Manifest | Config | Source Index | Verified Candidates | Complete |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in lineage["runs"]:
        hashes = run["hashes"]
        lines.append(
            "| {run_id} | {parent_command} | {manifest} | {config} | {source} | {verified} | {complete} |".format(
                run_id=run["run_id"],
                parent_command=run["parent_command"],
                manifest=_short_hash(hashes.get("manifest_sha256")),
                config=_short_hash(hashes.get("config_sha256")),
                source=_short_hash(hashes.get("source_index_sha256")),
                verified=_short_hash(hashes.get("verified_candidates_sha256")),
                complete=run["provenance_complete"],
            )
        )
    lines.extend(["", "## Policy", "", lineage["policy"], ""])
    return "\n".join(lines)
