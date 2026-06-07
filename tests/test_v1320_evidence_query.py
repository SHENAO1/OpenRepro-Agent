from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.evidence_query import evidence_query_summary, query_evidence
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_query_evidence_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    query = query_evidence(project, kind="claim", limit=10)
    summary = evidence_query_summary(project)

    assert query["schema_version"] == "1.32.0"
    assert query["kind"] == "claim"
    assert query["result_count"] > 0
    assert all(result["kind"] == "claim" for result in query["results"])
    assert (project / "workspace" / "evidence_query.json").exists()
    assert (project / "workspace" / "EVIDENCE_QUERY.md").exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.32.0"


def test_query_evidence_filters_by_text_and_kind(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    all_query = query_evidence(project, kind="all", limit=100)
    run = next(result for result in all_query["results"] if result["kind"] == "run")

    filtered = query_evidence(project, kind="run", text=run["id"], limit=5)

    assert filtered["kind"] == "run"
    assert filtered["text"] == run["id"]
    assert filtered["result_count"] >= 1
    assert all(result["kind"] == "run" for result in filtered["results"])
    assert any(result["id"] == run["id"] for result in filtered["results"])


def test_refresh_generates_default_evidence_query(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    query = read_json(project / "workspace" / "evidence_query.json")

    assert refresh["status"] == "complete"
    assert any(step["name"] == "evidence_query" and step["status"] == "passed" for step in refresh["steps"])
    assert query["schema_version"] == "1.32.0"
    assert query["kind"] == "all"
    assert query["result_count"] > 0


def test_cli_evidence_query(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_refresh_project(tmp_path)

    result = runner.invoke(app, ["evidence-query", "boc_demo", "--kind", "run", "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "Evidence query generated" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "evidence_query.json").exists()
    assert (tmp_path / "boc_demo" / "workspace" / "EVIDENCE_QUERY.md").exists()
