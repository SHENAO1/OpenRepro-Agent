"""Document ingestion for Markdown, text, and PDF placeholder handling."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import iso_now, read_json, unique_path, write_json

SUPPORTED_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
PDF_SUFFIX = ".pdf"


@dataclass
class SourceRecord:
    source_name: str
    original_path: str
    copied_path: str
    suffix: str
    size_bytes: int
    ingested_at: str
    status: str
    note: str


def _log(project_dir: Path, message: str) -> None:
    log_path = project_dir / "logs" / "project.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{iso_now()}] {message}\n")


def load_source_index(project_dir: Path) -> dict[str, Any]:
    """Load workspace/source_index.json."""
    return read_json(project_dir / "workspace" / "source_index.json", default={"sources": []}) or {"sources": []}


def save_source_index(project_dir: Path, index: dict[str, Any]) -> None:
    """Save workspace/source_index.json."""
    index["updated_at"] = iso_now()
    write_json(project_dir / "workspace" / "source_index.json", index)


def ingest_source(project_dir: Path, source: Path) -> SourceRecord:
    """Copy a source file into project/sources and update source_index.json.

    Markdown and text files are supported for analysis.  PDF files are copied and
    explicitly marked as placeholders because v0.1.0 does not implement PDF text
    extraction.
    """
    project_dir = Path(project_dir)
    source = Path(source)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Source file not found: {source}")

    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_TEXT_SUFFIXES and suffix != PDF_SUFFIX:
        raise ValueError("v0.1.0 supports Markdown, txt, and PDF placeholder ingestion only.")

    dest_dir = project_dir / "sources"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_path(dest_dir / source.name)
    shutil.copy2(source, dest)

    if suffix == PDF_SUFFIX:
        status = "placeholder"
        note = "PDF copied. v0.1.0 does not extract PDF text; add a Markdown/txt note for analysis or extend the loader."
    else:
        status = "ready"
        note = "Text source copied and ready for rule-based analysis."

    record = SourceRecord(
        source_name=dest.name,
        original_path=str(source),
        copied_path=str(dest.relative_to(project_dir)),
        suffix=suffix,
        size_bytes=dest.stat().st_size,
        ingested_at=iso_now(),
        status=status,
        note=note,
    )

    index = load_source_index(project_dir)
    sources = index.setdefault("sources", [])
    sources.append(record.__dict__.copy())
    save_source_index(project_dir, index)
    _log(project_dir, f"ingested source {source} -> {dest} ({status})")
    return record


def read_text_sources(project_dir: Path) -> list[dict[str, Any]]:
    """Read all analyzable text sources from source_index.json."""
    project_dir = Path(project_dir)
    index = load_source_index(project_dir)
    documents: list[dict[str, Any]] = []
    for record in index.get("sources", []):
        suffix = str(record.get("suffix", "")).lower()
        if suffix not in SUPPORTED_TEXT_SUFFIXES:
            continue
        copied = project_dir / str(record.get("copied_path", ""))
        if not copied.exists():
            continue
        documents.append(
            {
                "record": record,
                "path": copied,
                "name": copied.name,
                "text": copied.read_text(encoding="utf-8", errors="replace"),
            }
        )
    return documents
