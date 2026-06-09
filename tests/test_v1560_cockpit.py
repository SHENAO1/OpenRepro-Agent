from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.cockpit import cockpit_summary, generate_cockpit
from openrepro.dataset_card import run_data_quality_gate
from openrepro.data_registry import register_data
from openrepro.golden_path import run_golden_path
from openrepro.integrations import run_integration_execution
from openrepro.run_index import generate_run_index
from openrepro.claim_trace import generate_claim_trace, validate_claim_trace

runner = CliRunner()


def _prepare_cockpit_project(tmp_path: Path) -> Path:
    run_golden_path("cockpit_demo", base_dir=tmp_path, report=False, handoff=False)
    project = tmp_path / "cockpit_demo"
    data_file = project / "data" / "dataset.csv"
    data_file.write_text("id,label,split,feature\n1,0,train,0.1\n2,1,test,0.2\n", encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Cockpit fixture data")
    run_data_quality_gate(project)
    generate_run_index(project)
    generate_claim_trace(project)
    validate_claim_trace(project)
    run_integration_execution(project, targets=["mlflow"])
    return project


def test_generate_cockpit_writes_static_review_surface(tmp_path: Path):
    project = _prepare_cockpit_project(tmp_path)

    cockpit = generate_cockpit(project, export_zip=True)
    summary = cockpit_summary(project)

    assert cockpit["schema_version"] == "1.56.0"
    assert cockpit["status"] == "needs_attention"
    assert cockpit["summary"]["data_quality_status"] == "passed"
    assert cockpit["summary"]["run_count"] >= 1
    assert cockpit["summary"]["integration_execution_status"] == "planned"
    assert any(action["action_id"] == "bench_lite" for action in cockpit["next_actions"])
    assert (project / "reports" / "cockpit" / "index.html").exists()
    assert (project / "reports" / "cockpit_manifest.json").exists()
    assert (project / "workspace" / "cockpit_summary.json").exists()
    assert (project / "workspace" / "COCKPIT_SUMMARY.md").exists()
    assert (project / "reports" / "cockpit.zip").exists()
    assert summary["present"] is True
    assert summary["status"] == "needs_attention"


def test_cli_cockpit_build_and_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_cockpit_project(tmp_path)

    built = runner.invoke(app, ["cockpit", "build", "cockpit_demo", "--zip"])
    summarized = runner.invoke(app, ["cockpit", "summary", "cockpit_demo"])

    assert built.exit_code == 0, built.output
    assert "Reproduction cockpit generated" in built.output
    assert summarized.exit_code == 0, summarized.output
    assert "next_action_count" in summarized.output
    assert (tmp_path / "cockpit_demo" / "reports" / "cockpit.zip").exists()
