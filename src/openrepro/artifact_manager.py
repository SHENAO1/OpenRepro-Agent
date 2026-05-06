"""Artifact and run-directory management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .utils import ensure_dirs, local_timestamp_for_path, slugify

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
    """Return all project-level handoff files required by v0.1.0."""
    return [
        "PROJECT_CONTEXT.md",
        "PAPER_SUMMARY.md",
        "MODEL_LEDGER.md",
        "EXPERIMENT_PLAN.md",
        "CODE_STATUS.md",
        "RUN_LOG_SUMMARY.md",
        "ERROR_NOTES.md",
        "NEXT_STEPS.md",
        "AGENT_HANDOFF.md",
    ]


def files_exist(base_dir: Path, names: Iterable[str]) -> bool:
    """Return True when every named file exists under base_dir."""
    return all((base_dir / name).exists() for name in names)
