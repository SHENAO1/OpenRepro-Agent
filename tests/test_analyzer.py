from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.document_loader import ingest_source
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC Test\n\nA BOC subcarrier and pseudo-random spreading code can be analyzed by autocorrelation.",
        encoding="utf-8",
    )
    project = tmp_path / "boc_demo"
    ingest_source(project, source)
    return project


def test_analyze_generates_summary_and_ledger(tmp_path: Path):
    project = _prepare_project(tmp_path)

    result = analyze_project(project)

    assert (project / "workspace" / "paper_summary.md").exists()
    assert (project / "workspace" / "MODEL_LEDGER.md").exists()
    assert (project / "workspace" / "analysis_result.json").exists()
    assert result["project_name"] == "boc_demo"
    assert "BOC modulation" in result["detected_keywords"]


def test_plan_generates_experiment_plan(tmp_path: Path):
    project = _prepare_project(tmp_path)
    analyze_project(project)

    path = generate_experiment_plan(project)

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "实验目标" in text
    assert "v0.1.0 Demo" in text
