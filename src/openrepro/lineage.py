"""Run lineage generation for auditable project state."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .utils import iso_now, read_json, safe_write_text, write_json

LINEAGE_SCHEMA_VERSION = "1.4.0"


def _hash_file(path: Path) -> str | None:
    return sha256_file(path) if path.exists() and path.is_file() else None


def _run_config_path(project_dir: Path, run_dir: Path) -> Path:
    snapshot = run_dir / "configs" / "project_config_snapshot.yaml"
    return snapshot if snapshot.exists() else project_dir / "project_config.yaml"


def _lineage_entry(project_dir: Path, run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path, default={}) or {}
    command = str(manifest.get("command") or "unknown") if isinstance(manifest, dict) else "unknown"
    metadata = manifest.get("metadata", {}) if isinstance(manifest, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    experiment_id = metadata.get("experiment_id")
    repeat_group_id = f"experiment:{experiment_id}" if command == "run-experiment" and experiment_id else None
    source_index = project_dir / "workspace" / "source_index.json"
    verified_candidates = project_dir / "workspace" / "verified_candidates.json"
    config_path = _run_config_path(project_dir, run_dir)
    experiment_config = run_dir / "configs" / "experiment_config_snapshot.json"
    experiment_inputs = run_dir / "configs" / "experiment_inputs_snapshot.json"
    experiment_spec = run_dir / "configs" / "experiment_spec_snapshot.json"
    data_index = run_dir / "configs" / "data_index_snapshot.json"
    environment_snapshot = run_dir / "configs" / "environment_snapshot.json"
    quality_gate = run_dir / "reports" / "quality_gate.json"
    runner = run_dir / "code" / "runner.py"
    hashes = {
        "manifest_sha256": _hash_file(manifest_path),
        "config_sha256": _hash_file(config_path),
        "source_index_sha256": _hash_file(source_index),
        "verified_candidates_sha256": _hash_file(verified_candidates),
        "experiment_config_sha256": _hash_file(experiment_config),
        "experiment_inputs_sha256": _hash_file(experiment_inputs),
        "experiment_spec_sha256": _hash_file(experiment_spec),
        "data_index_sha256": _hash_file(data_index),
        "environment_snapshot_sha256": _hash_file(environment_snapshot),
        "quality_gate_sha256": _hash_file(quality_gate),
        "runner_sha256": _hash_file(runner),
    }
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "parent_command": command,
        "created_at": manifest.get("created_at") if isinstance(manifest, dict) else None,
        "experiment_id": experiment_id,
        "template": metadata.get("template"),
        "repeat_group_id": repeat_group_id,
        "repeat_run_index": None,
        "repeat_run_count": None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "config_path": str(config_path) if config_path.exists() else None,
        "source_index_path": str(source_index) if source_index.exists() else None,
        "verified_candidates_path": str(verified_candidates) if verified_candidates.exists() else None,
        "experiment_config_path": str(experiment_config) if experiment_config.exists() else None,
        "experiment_inputs_path": str(experiment_inputs) if experiment_inputs.exists() else None,
        "experiment_spec_path": str(experiment_spec) if experiment_spec.exists() else None,
        "data_index_path": str(data_index) if data_index.exists() else None,
        "environment_snapshot_path": str(environment_snapshot) if environment_snapshot.exists() else None,
        "quality_gate_path": str(quality_gate) if quality_gate.exists() else None,
        "runner_path": str(runner) if runner.exists() else None,
        "hashes": hashes,
        "provenance_complete": all(
            value is not None
            for key, value in hashes.items()
            if key not in {
                "verified_candidates_sha256",
                "experiment_config_sha256",
                "experiment_inputs_sha256",
                "experiment_spec_sha256",
                "data_index_sha256",
                "environment_snapshot_sha256",
                "quality_gate_sha256",
                "runner_sha256",
            }
        ),
        "experiment_provenance_complete": all(
            hashes[key] is not None
            for key in [
                "experiment_config_sha256",
                "experiment_inputs_sha256",
                "experiment_spec_sha256",
                "data_index_sha256",
                "environment_snapshot_sha256",
                "quality_gate_sha256",
                "runner_sha256",
            ]
        )
        if command == "run-experiment"
        else None,
        "verified_candidates_present": hashes["verified_candidates_sha256"] is not None,
    }


def generate_run_lineage(project_dir: Path) -> dict[str, Any]:
    """Write workspace/run_lineage.json and workspace/RUN_LINEAGE.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    entries = [_lineage_entry(project_dir, run_dir) for run_dir in reversed(list_run_dirs(project_dir))]
    repeat_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        group_id = entry.get("repeat_group_id")
        if group_id:
            repeat_groups[str(group_id)].append(entry)
    for group_entries in repeat_groups.values():
        for index, entry in enumerate(group_entries, start=1):
            entry["repeat_run_index"] = index
            entry["repeat_run_count"] = len(group_entries)
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
        "| Run | Command | Repeat | Manifest | Config | Inputs | Spec | Data | Environment | Gate | Runner | Complete |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in lineage["runs"]:
        hashes = run["hashes"]
        repeat = (
            f"{run['repeat_run_index']}/{run['repeat_run_count']}"
            if run.get("repeat_run_index") and run.get("repeat_run_count")
            else ""
        )
        lines.append(
            "| {run_id} | {parent_command} | {repeat} | {manifest} | {config} | {inputs} | {spec} | {data} | {environment} | {gate} | {runner} | {complete} |".format(
                run_id=run["run_id"],
                parent_command=run["parent_command"],
                repeat=repeat,
                manifest=_short_hash(hashes.get("manifest_sha256")),
                config=_short_hash(hashes.get("config_sha256")),
                inputs=_short_hash(hashes.get("experiment_inputs_sha256")),
                spec=_short_hash(hashes.get("experiment_spec_sha256")),
                data=_short_hash(hashes.get("data_index_sha256")),
                environment=_short_hash(hashes.get("environment_snapshot_sha256")),
                gate=_short_hash(hashes.get("quality_gate_sha256")),
                runner=_short_hash(hashes.get("runner_sha256")),
                complete=run.get("experiment_provenance_complete")
                if run.get("experiment_provenance_complete") is not None
                else run["provenance_complete"],
            )
        )
    lines.extend(["", "## Policy", "", lineage["policy"], ""])
    return "\n".join(lines)
