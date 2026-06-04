from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.approval import approve_candidates
from openrepro.candidate_review import review_candidates
from openrepro.claim_evidence_binder import generate_claim_evidence_binder, validate_claim_evidence_binder
from openrepro.claim_evidence_report import generate_claim_evidence_report
from openrepro.claim_evidence_report_validation import validate_claim_evidence_report
from openrepro.claim_signoff import record_claim_signoff
from openrepro.claim_signoff_validation import validate_claim_signoffs
from openrepro.claim_trace import generate_claim_trace, validate_claim_trace
from openrepro.cli import app
from openrepro.data_registry import register_data
from openrepro.document_loader import ingest_source
from openrepro.evidence_package import generate_evidence_package
from openrepro.experiment_runner import run_experiment
from openrepro.experiment_scaffold import scaffold_experiment
from openrepro.gaps import generate_reproduction_gaps
from openrepro.handoff_generator import generate_handoff
from openrepro.lineage import generate_run_lineage
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import get_status, init_project
from openrepro.protocol_coverage import generate_protocol_coverage
from openrepro.protocol_plan import generate_protocol_plan
from openrepro.protocol_preflight import generate_protocol_preflight
from openrepro.reproduction_protocol import generate_reproduction_protocol
from openrepro.reviewer_packet import generate_reviewer_packet
from openrepro.scorecard import generate_reproduction_scorecard
from openrepro.timeline import generate_project_timeline

runner = CliRunner()


def _prepare_timeline_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# Timeline Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 32",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    review_candidates(project, candidate_ids=["F001"], status="needs_more_evidence", reviewer="timeline")
    approve_candidates(project, approve_all=True, reviewer="timeline")
    data_file = project / "data" / "timeline_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Timeline fixture data")
    scaffold_experiment(project, experiment_id="timeline_exp", template="boc-like")
    run_experiment(project, "timeline_exp", confirm=True)
    generate_run_lineage(project)
    generate_claim_trace(project)
    validate_claim_trace(project)
    generate_reproduction_scorecard(project)
    generate_reproduction_gaps(project)
    generate_reproduction_protocol(project)
    generate_protocol_coverage(project)
    generate_protocol_plan(project)
    generate_protocol_preflight(project)
    binder = generate_claim_evidence_binder(project)
    validate_claim_evidence_binder(project)
    for claim in binder["claims"]:
        record_claim_signoff(
            project,
            claim_id=claim["claim_id"],
            decision="accepted_workflow_evidence",
            reviewer="timeline",
            note="Timeline fixture signoff.",
        )
    validate_claim_signoffs(project)
    generate_claim_evidence_report(project)
    validate_claim_evidence_report(project)
    generate_reviewer_packet(project)
    return project


def test_generate_project_timeline_records_decisions_and_runs(tmp_path: Path):
    project = _prepare_timeline_project(tmp_path)

    timeline = generate_project_timeline(project)

    assert timeline["schema_version"] == "1.16.1"
    assert timeline["status"] == "ready"
    assert timeline["event_count"] > 0
    assert timeline["human_decision_count"] >= 2
    assert timeline["run_event_count"] >= 1
    assert timeline["stage_counts"]["claim_signoff"] >= 1
    assert timeline["stage_counts"]["run"] >= 1
    assert (project / "workspace" / "project_timeline.json").exists()
    assert (project / "workspace" / "PROJECT_TIMELINE.md").exists()


def test_cli_timeline_updates_status(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_timeline_project(tmp_path)

    result = runner.invoke(app, ["timeline", "boc_demo"])
    status = get_status(project)

    assert result.exit_code == 0, result.output
    assert "Project timeline generated" in result.output
    assert status.project_timeline_exists is True
    assert status.project_timeline_status == "ready"
    assert status.project_timeline_event_count > 0


def test_evidence_package_and_handoff_include_timeline(tmp_path: Path):
    project = _prepare_timeline_project(tmp_path)
    generate_project_timeline(project)
    generate_handoff(project)

    package = generate_evidence_package(project)

    assert package["project_timeline"]["status"] == "ready"
    assert package["project_timeline"]["event_count"] > 0
    assert package["reports"]["project_timeline"]["present"] is True
    assert (project / "handoff" / "PROJECT_TIMELINE.md").exists()
