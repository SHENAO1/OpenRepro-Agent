"""Document ingestion for Markdown, text, and PDF extraction."""

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
    extraction_status: str | None = None
    extracted_text_path: str | None = None
    pages_path: str | None = None
    page_count: int | None = None
    char_count: int | None = None
    table_count: int | None = None


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


def _normalize_table(table: list[list[Any]]) -> list[list[str]]:
    normalized: list[list[str]] = []
    for row in table:
        normalized.append(["" if cell is None else str(cell) for cell in row])
    return normalized


def _extract_pdf_source(project_dir: Path, copied_pdf: Path) -> dict[str, Any]:
    extracted_dir = project_dir / "workspace" / "extracted_sources"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    text_path = unique_path(extracted_dir / f"{copied_pdf.stem}.txt")
    pages_path = text_path.with_suffix(".pages.json")

    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover - dependency failures are environment-specific.
        return {
            "extraction_status": "extraction_failed",
            "note": f"PDF copied, but pdfplumber is unavailable: {exc}",
            "extracted_text_path": None,
            "pages_path": None,
            "page_count": 0,
            "char_count": 0,
            "table_count": 0,
        }

    pages: list[dict[str, Any]] = []
    all_text: list[str] = []
    table_count = 0
    try:
        with pdfplumber.open(copied_pdf) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                try:
                    tables = [_normalize_table(table) for table in (page.extract_tables() or [])]
                except Exception:
                    tables = []
                table_count += len(tables)
                pages.append(
                    {
                        "page_number": page_number,
                        "char_count": len(text),
                        "table_count": len(tables),
                        "text": text,
                        "tables": tables,
                    }
                )
                all_text.append(f"\n\n--- page {page_number} ---\n\n{text}".strip())
    except Exception as exc:
        return {
            "extraction_status": "extraction_failed",
            "note": f"PDF copied, but text extraction failed: {exc}",
            "extracted_text_path": None,
            "pages_path": None,
            "page_count": 0,
            "char_count": 0,
            "table_count": 0,
        }

    combined_text = "\n\n".join(part for part in all_text if part.strip())
    safe_text = combined_text if combined_text.strip() else ""
    text_path.write_text(safe_text, encoding="utf-8")
    write_json(
        pages_path,
        {
            "source_pdf": str(copied_pdf.relative_to(project_dir)),
            "extracted_text_path": str(text_path.relative_to(project_dir)),
            "page_count": len(pages),
            "char_count": len(safe_text),
            "table_count": table_count,
            "pages": pages,
        },
    )

    extraction_status = "extracted" if safe_text.strip() else "extracted_empty"
    note = "PDF copied and text extracted with pdfplumber."
    if extraction_status == "extracted_empty":
        note = "PDF copied, but pdfplumber did not extract readable text."
    return {
        "extraction_status": extraction_status,
        "note": note,
        "extracted_text_path": str(text_path.relative_to(project_dir)),
        "pages_path": str(pages_path.relative_to(project_dir)),
        "page_count": len(pages),
        "char_count": len(safe_text),
        "table_count": table_count,
    }


def ingest_source(project_dir: Path, source: Path) -> SourceRecord:
    """Copy a source file into project/sources and update source_index.json.

    Markdown and text files are copied directly. PDF files are copied and then
    extracted into workspace/extracted_sources with page-level provenance.
    """
    project_dir = Path(project_dir)
    source = Path(source)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Source file not found: {source}")

    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_TEXT_SUFFIXES and suffix != PDF_SUFFIX:
        raise ValueError("v0.2.0 supports Markdown, txt, and PDF ingestion only.")

    dest_dir = project_dir / "sources"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_path(dest_dir / source.name)
    shutil.copy2(source, dest)

    extraction: dict[str, Any] = {}
    if suffix == PDF_SUFFIX:
        extraction = _extract_pdf_source(project_dir, dest)
        extraction_status = extraction.get("extraction_status")
        if extraction_status == "extracted":
            status = "ready"
        elif extraction_status == "extracted_empty":
            status = "extraction_empty"
        else:
            status = "extraction_failed"
        note = str(extraction.get("note", "PDF copied."))
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
        extraction_status=extraction.get("extraction_status"),
        extracted_text_path=extraction.get("extracted_text_path"),
        pages_path=extraction.get("pages_path"),
        page_count=extraction.get("page_count"),
        char_count=extraction.get("char_count"),
        table_count=extraction.get("table_count"),
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
        if suffix in SUPPORTED_TEXT_SUFFIXES:
            copied = project_dir / str(record.get("copied_path", ""))
        elif suffix == PDF_SUFFIX and record.get("extraction_status") == "extracted":
            copied = project_dir / str(record.get("extracted_text_path", ""))
        else:
            continue
        if not copied.exists():
            continue
        documents.append(
            {
                "record": record,
                "path": copied,
                "name": str(record.get("source_name") or copied.name),
                "text": copied.read_text(encoding="utf-8", errors="replace"),
            }
        )
    return documents


def read_pdf_page_records(project_dir: Path) -> list[dict[str, Any]]:
    """Read page-level PDF extraction records from source_index.json."""
    project_dir = Path(project_dir)
    index = load_source_index(project_dir)
    page_records: list[dict[str, Any]] = []
    for record in index.get("sources", []):
        if str(record.get("suffix", "")).lower() != PDF_SUFFIX:
            continue
        pages_path = record.get("pages_path")
        if not pages_path:
            continue
        data = read_json(project_dir / str(pages_path), default={}) or {}
        for page in data.get("pages", []):
            page_records.append(
                {
                    "record": record,
                    "source_name": record.get("source_name"),
                    "page": page,
                }
            )
    return page_records
