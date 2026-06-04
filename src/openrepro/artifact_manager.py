"""Artifact, manifest, and run-directory management."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .utils import ensure_dirs, local_timestamp_for_path, slugify
from .utils import iso_now, read_json, relpath, write_json

RUN_SUBDIRS = [
    "logs",
    "figures",
    "data",
    "reports",
    "configs",
    "code",
    "api_usage",
    "handoff",
]

MANIFEST_SCHEMA_VERSION = "0.4.0"
MANIFEST_EXCLUDED_ARTIFACTS = {
    "reports/quality_gate.json",
    "reports/quality_gate.md",
}

REQUIRED_RUN_ARTIFACTS: dict[str, list[str]] = {
    "run-demo": [
        "logs/run.log",
        "figures/correlation.png",
        "data/demo_signal.npy",
        "data/correlation.npy",
        "data/demo_metrics.json",
        "reports/demo_report.md",
        "configs/project_config_snapshot.yaml",
        "code/README.md",
        "api_usage/api_usage.jsonl",
        "api_usage/api_usage_summary.json",
        "handoff/AGENT_HANDOFF.md",
        "metadata.json",
    ],
    "run-sweep": [
        "logs/run.log",
        "figures/sweep_correlation_peak.png",
        "data/sweep_results.json",
        "data/sweep_metrics.csv",
        "reports/sweep_report.md",
        "configs/project_config_snapshot.yaml",
        "code/README.md",
        "api_usage/api_usage.jsonl",
        "api_usage/api_usage_summary.json",
        "metadata.json",
    ],
    "run-experiment": [
        "logs/run.log",
        "data/execution_result.json",
        "reports/experiment_report.md",
        "configs/experiment_config_snapshot.json",
        "configs/experiment_inputs_snapshot.json",
        "configs/experiment_spec_snapshot.json",
        "configs/data_index_snapshot.json",
        "configs/environment_snapshot.json",
        "code/runner.py",
        "metadata.json",
    ],
    "benchmark": [
        "benchmark_result.json",
        "benchmark_report.md",
        "api_usage/api_usage.jsonl",
        "api_usage/api_usage_summary.json",
    ],
    "benchmark-suite": [
        "benchmark_suite_result.json",
        "benchmark_suite_report.md",
    ],
}


@dataclass
class RunDirectory:
    """Structured paths for a single demo run."""

    root: Path
    logs: Path
    figures: Path
    data: Path
    reports: Path
    configs: Path
    code: Path
    api_usage: Path
    handoff: Path

    @classmethod
    def create(cls, project_dir: Path, project_name: str) -> "RunDirectory":
        outputs_dir = project_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = local_timestamp_for_path()
        slug = slugify(project_name)
        root = outputs_dir / f"{timestamp}_{slug}"
        counter = 1
        while root.exists():
            root = outputs_dir / f"{timestamp}_{slug}_{counter}"
            counter += 1
        paths = {name: root / name for name in RUN_SUBDIRS}
        ensure_dirs(paths.values())
        return cls(root=root, **paths)


def ensure_run_subdirs(run_dir: Path) -> None:
    """Ensure all expected subdirectories exist inside a run directory."""
    ensure_dirs(run_dir / name for name in RUN_SUBDIRS)


def list_run_dirs(project_dir: Path) -> list[Path]:
    """List run directories sorted newest first by directory name."""
    outputs = project_dir / "outputs"
    if not outputs.exists():
        return []
    dirs = [p for p in outputs.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.name, reverse=True)


def latest_run_dir(project_dir: Path) -> Path | None:
    """Return the most recent run directory, if any."""
    dirs = list_run_dirs(project_dir)
    return dirs[0] if dirs else None


def required_handoff_files() -> list[str]:
    """Return all project-level handoff files required by the current workflow."""
    return [
        "PROJECT_CONTEXT.md",
        "PAPER_SUMMARY.md",
        "MODEL_LEDGER.md",
        "VERIFIED_CANDIDATES.md",
        "CANDIDATE_REVIEWS.md",
        "EXPERIMENT_PLAN.md",
        "CODE_STATUS.md",
        "RUN_LOG_SUMMARY.md",
        "ERROR_NOTES.md",
        "REPAIR_DRY_RUN.md",
        "RUN_LINEAGE.md",
        "WORKFLOW_CHECKPOINTS.md",
        "ADVANCE_PLAN.md",
        "REVIEW_BOARD.md",
        "REVIEW_DECISIONS.md",
        "REPRODUCTION_PROTOCOL.md",
        "PROTOCOL_COVERAGE.md",
        "PROTOCOL_PLAN.md",
        "PROTOCOL_PREFLIGHT.md",
        "REPRODUCTION_SCORECARD.md",
        "REPRODUCTION_GAPS.md",
        "EVIDENCE_PACKAGE.md",
        "NEXT_STEPS.md",
        "AGENT_HANDOFF.md",
    ]


def files_exist(base_dir: Path, names: Iterable[str]) -> bool:
    """Return True when every named file exists under base_dir."""
    return all((base_dir / name).exists() for name in names)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_category(relative_path: str) -> str:
    parts = Path(relative_path).parts
    if len(parts) <= 1:
        return "run_root"
    return parts[0]


def _artifact_record(run_dir: Path, relative_path: str) -> dict[str, Any]:
    path = run_dir / relative_path
    exists = path.exists() and path.is_file()
    return {
        "path": relative_path.replace("\\", "/"),
        "category": _artifact_category(relative_path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": sha256_file(path) if exists else None,
    }


def build_run_manifest(
    run_dir: Path,
    command: str,
    required_artifacts: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a manifest dictionary for a completed run directory."""
    run_dir = Path(run_dir)
    required = required_artifacts or REQUIRED_RUN_ARTIFACTS.get(command, [])
    discovered = sorted(
        relative_path
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
        for relative_path in [relpath(path, run_dir).replace("\\", "/")]
        if relative_path not in MANIFEST_EXCLUDED_ARTIFACTS
    )
    all_paths = sorted(set(discovered).union(path.replace("\\", "/") for path in required))
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "openrepro_version": __version__,
        "run_id": run_dir.name,
        "command": command,
        "created_at": iso_now(),
        "required_artifacts": [path.replace("\\", "/") for path in required],
        "artifacts": [_artifact_record(run_dir, path) for path in all_paths],
    }
    if extra_metadata:
        manifest["metadata"] = extra_metadata
    return manifest


def write_run_manifest(
    run_dir: Path,
    command: str,
    required_artifacts: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> Path:
    """Write manifest.json for a completed run directory."""
    run_dir = Path(run_dir)
    manifest = build_run_manifest(
        run_dir,
        command,
        required_artifacts=required_artifacts,
        extra_metadata=extra_metadata,
    )
    write_json(run_dir / "manifest.json", manifest)
    return run_dir / "manifest.json"


def validate_run_manifest(run_dir: Path, required_artifacts: list[str] | None = None) -> dict[str, Any]:
    """Validate a run manifest against files currently on disk."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    errors: list[str] = []
    warnings: list[str] = []

    if not run_dir.exists() or not run_dir.is_dir():
        return {
            "valid": False,
            "run_dir": str(run_dir),
            "errors": [f"Run directory not found: {run_dir}"],
            "warnings": [],
            "checked_artifacts": 0,
        }

    manifest = read_json(manifest_path, default=None)
    if not isinstance(manifest, dict):
        return {
            "valid": False,
            "run_dir": str(run_dir),
            "errors": [f"Manifest not found or invalid: {manifest_path}"],
            "warnings": [],
            "checked_artifacts": 0,
        }

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        warnings.append(
            f"Manifest schema is {manifest.get('schema_version')!r}; expected {MANIFEST_SCHEMA_VERSION!r}."
        )

    manifest_required = manifest.get("required_artifacts", [])
    required = required_artifacts or [str(path) for path in manifest_required]
    artifact_map = {str(item.get("path")): item for item in manifest.get("artifacts", []) if isinstance(item, dict)}

    checked = 0
    for required_path in required:
        normalized = required_path.replace("\\", "/")
        if not (run_dir / normalized).exists():
            errors.append(f"Missing required artifact: {normalized}")
        if normalized not in artifact_map:
            errors.append(f"Required artifact missing from manifest: {normalized}")

    for relative_path, record in artifact_map.items():
        checked += 1
        path = run_dir / relative_path
        expected_exists = bool(record.get("exists"))
        actual_exists = path.exists() and path.is_file()
        if expected_exists and not actual_exists:
            errors.append(f"Manifest artifact missing on disk: {relative_path}")
            continue
        if not expected_exists:
            continue
        actual_size = path.stat().st_size
        if actual_size != record.get("size_bytes"):
            errors.append(
                f"Size mismatch for {relative_path}: expected {record.get('size_bytes')}, got {actual_size}"
            )
        actual_hash = sha256_file(path)
        if actual_hash != record.get("sha256"):
            errors.append(f"SHA-256 mismatch for {relative_path}")

    return {
        "valid": not errors,
        "run_dir": str(run_dir),
        "manifest": str(manifest_path),
        "command": manifest.get("command"),
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": checked,
    }


def validate_all_run_manifests(project_dir: Path) -> list[dict[str, Any]]:
    """Validate every run directory under project/outputs."""
    return [validate_run_manifest(run_dir) for run_dir in list_run_dirs(Path(project_dir))]
