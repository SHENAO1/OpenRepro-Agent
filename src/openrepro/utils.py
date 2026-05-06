"""General utilities for OpenRepro-Agent.

The helpers in this module intentionally avoid heavyweight dependencies.  They
centralize timestamp handling, JSON/YAML IO, safe file writes, and lightweight
markdown utilities used by the project workflow.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


def now_utc() -> datetime:
    """Return the current UTC datetime with timezone information."""
    return datetime.now(timezone.utc)


def iso_now() -> str:
    """Return an ISO-8601 UTC timestamp without microseconds."""
    return now_utc().replace(microsecond=0).isoformat()


def local_timestamp_for_path() -> str:
    """Return a filesystem-friendly timestamp for run directories."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def slugify(value: str) -> str:
    """Convert an arbitrary name to a safe lowercase path slug."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "openrepro_project"


def ensure_dirs(paths: Iterable[Path]) -> None:
    """Create a collection of directories if they do not already exist."""
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path, default: str = "") -> str:
    """Read UTF-8 text from a file, returning *default* when it is missing."""
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def safe_write_text(path: Path, content: str, overwrite: bool = True) -> bool:
    """Write text safely.

    Returns True when the file was written and False when an existing file was
    intentionally preserved.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def read_json(path: Path, default: Any | None = None) -> Any:
    """Read a JSON file; return *default* when missing."""
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any, overwrite: bool = True) -> bool:
    """Write a JSON file using stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return True


def read_yaml(path: Path, default: Any | None = None) -> Any:
    """Read YAML from *path*; return *default* when missing or empty."""
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return default if data is None else data


def write_yaml(path: Path, data: Any, overwrite: bool = True) -> bool:
    """Write YAML using UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return True


def first_markdown_heading(text: str) -> str | None:
    """Extract the first level-1 Markdown heading from text."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def truncate(text: str, max_chars: int = 1200) -> str:
    """Return a compact text preview for reports and handoff files."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + "\n... [truncated]"


def project_required_dirs(project_dir: Path) -> list[Path]:
    """Return the standard directory set for a reproduction project."""
    return [
        project_dir / "sources",
        project_dir / "workspace",
        project_dir / "outputs",
        project_dir / "handoff",
        project_dir / "reports",
        project_dir / "logs",
    ]


def relpath(path: Path, base: Path) -> str:
    """Return a safe relative path string when possible."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending a numeric suffix when needed."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1
