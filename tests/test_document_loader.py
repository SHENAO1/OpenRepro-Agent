from pathlib import Path

from openrepro.document_loader import ingest_source, load_source_index
from openrepro.project_manager import init_project


def test_ingest_copies_markdown(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# Test Paper\n\nBOC correlation notes.", encoding="utf-8")

    record = ingest_source(tmp_path / "boc_demo", source)
    project = tmp_path / "boc_demo"

    assert record.status == "ready"
    assert (project / "sources" / "notes.md").exists()
    index = load_source_index(project)
    assert len(index["sources"]) == 1
    assert index["sources"][0]["source_name"] == "notes.md"


def test_ingest_pdf_placeholder(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4 placeholder")

    record = ingest_source(tmp_path / "boc_demo", source)

    assert record.status == "placeholder"
    assert "PDF copied" in record.note
