from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.document_loader import ingest_source
from openrepro.inspector import inspect_project
from openrepro.project_manager import init_project
from openrepro.utils import read_json


def test_section_caption_and_candidate_risk_metadata(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "paper_notes.md"
    source.write_text(
        """# BOC Paper

## Abstract

This paper studies BOC correlation.

## Methods

Formula: x[n] = c[n] * s[n] + noise.

noise_std = 0.05

Figure 1: BOC acquisition pipeline.

## Results

Table 1: Correlation peak summary.
""",
        encoding="utf-8",
    )
    ingest_source(project, source)

    result = analyze_project(project)
    formulas = read_json(project / "workspace" / "formula_candidates.json")
    parameters = read_json(project / "workspace" / "parameter_candidates.json")
    captions = read_json(project / "workspace" / "caption_index.json")
    summary = inspect_project(project)

    assert result["section_counts"]["methods"] >= 1
    assert result["caption_count"] == 2
    assert captions["caption_count"] == 2
    assert formulas["candidates"][0]["section"] == "methods"
    assert "needs_human_review" in formulas["candidates"][0]["risk_flags"]
    assert parameters["candidates"][0]["risk_level"] in {"medium", "high"}
    assert summary["candidate_high_risk_count"] >= 0
    assert (project / "workspace" / "CAPTION_INDEX.md").exists()
