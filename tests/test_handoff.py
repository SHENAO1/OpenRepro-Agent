from pathlib import Path

from openrepro.analyzer import analyze_project
from openrepro.artifact_manager import required_handoff_files
from openrepro.demo_runner import run_demo
from openrepro.document_loader import ingest_source
from openrepro.handoff_generator import generate_handoff
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.report_generator import generate_report


def _prepare_full_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC subcarrier correlation model and metric notes.", encoding="utf-8")
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    run_demo(project)
    return project


def test_report_generates_report_md(tmp_path: Path):
    project = _prepare_full_project(tmp_path)

    path = generate_report(project)

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "API 使用统计摘要" in text
    assert "最近一次 Demo" in text
    assert "Verified Candidate 审批摘要" in text
    assert "Repair Dry-Run 摘要" in text
    assert "Workflow Checkpoints 摘要" in text
    assert "Advance Plan 摘要" in text
    assert "Review Board 摘要" in text
    assert "Review Decisions 摘要" in text
    assert "Reproduction Protocol 摘要" in text
    assert "Protocol Coverage 摘要" in text
    assert "Protocol Plan 摘要" in text
    assert "Protocol Preflight 摘要" in text
    assert "Claim Evidence Binder 摘要" in text
    assert "Claim Evidence Binder Validation 摘要" in text
    assert "Claim Signoffs 摘要" in text
    assert "Claim Signoff Validation 摘要" in text
    assert "Claim Evidence Report 摘要" in text
    assert "Claim Evidence Report Validation 摘要" in text
    assert "Reviewer Packet 摘要" in text
    assert "Reproduction Readiness Scorecard 摘要" in text
    assert "Reproduction Gaps 摘要" in text


def test_handoff_generates_all_files(tmp_path: Path):
    project = _prepare_full_project(tmp_path)

    files = generate_handoff(project)

    assert len(files) == len(required_handoff_files())
    for name in required_handoff_files():
        path = project / "handoff" / name
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip()
    assert (project / "handoff" / "VERIFIED_CANDIDATES.md").exists()
    assert (project / "handoff" / "REPAIR_DRY_RUN.md").exists()
    assert (project / "handoff" / "WORKFLOW_CHECKPOINTS.md").exists()
    assert (project / "handoff" / "ADVANCE_PLAN.md").exists()
    assert (project / "handoff" / "REVIEW_BOARD.md").exists()
    assert (project / "handoff" / "REVIEW_DECISIONS.md").exists()
    assert (project / "handoff" / "REPRODUCTION_PROTOCOL.md").exists()
    assert (project / "handoff" / "PROTOCOL_COVERAGE.md").exists()
    assert (project / "handoff" / "PROTOCOL_PLAN.md").exists()
    assert (project / "handoff" / "PROTOCOL_PREFLIGHT.md").exists()
    assert (project / "handoff" / "CLAIM_EVIDENCE_BINDER.md").exists()
    assert (project / "handoff" / "CLAIM_EVIDENCE_BINDER_VALIDATION.md").exists()
    assert (project / "handoff" / "CLAIM_SIGNOFFS.md").exists()
    assert (project / "handoff" / "CLAIM_SIGNOFF_VALIDATION.md").exists()
    assert (project / "handoff" / "CLAIM_EVIDENCE_REPORT.md").exists()
    assert (project / "handoff" / "CLAIM_EVIDENCE_REPORT_VALIDATION.md").exists()
    assert (project / "handoff" / "REVIEWER_PACKET.md").exists()
    assert (project / "handoff" / "REPRODUCTION_GAPS.md").exists()
