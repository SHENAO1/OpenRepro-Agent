from pathlib import Path

from openrepro.document_loader import ingest_source, load_source_index, read_text_sources
from openrepro.project_manager import init_project


def _write_minimal_pdf(path: Path, text: str) -> None:
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(bytes(content))


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


def test_ingest_pdf_extracts_text_with_provenance(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    source = tmp_path / "paper.pdf"
    _write_minimal_pdf(source, "BOC formula x[n] = c[n] s[n] and noise_std = 0.05")

    record = ingest_source(tmp_path / "boc_demo", source)
    project = tmp_path / "boc_demo"
    index = load_source_index(project)
    stored = index["sources"][0]

    assert record.status == "ready"
    assert record.extraction_status == "extracted"
    assert record.extracted_text_path
    assert record.pages_path
    assert stored["page_count"] == 1
    assert stored["char_count"] > 0
    assert (project / record.extracted_text_path).exists()
    assert read_text_sources(project)[0]["text"]


def test_ingest_malformed_pdf_marks_extraction_failed(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4 placeholder")

    record = ingest_source(tmp_path / "boc_demo", source)

    assert record.status == "extraction_failed"
    assert record.extraction_status == "extraction_failed"
    assert "PDF copied" in record.note
