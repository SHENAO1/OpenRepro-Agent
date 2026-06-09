from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.evidence_graph import evidence_graph_summary, generate_evidence_graph
from openrepro.evidence_package import generate_evidence_package
from openrepro.refresh import generate_refresh_run
from openrepro.workflow_registry import build_workflow_state

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_evidence_graph_links_core_workflow_state(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    assert (project / "workspace" / "evidence_graph.json").exists()
    graph = generate_evidence_graph(project)
    summary = evidence_graph_summary(project)
    edge_keys = {(edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]}

    assert graph["schema_version"] == "1.57.0"
    assert graph["status"] == "ready_for_review"
    assert graph["claim_count"] > 0
    assert graph["experiment_count"] > 0
    assert graph["run_count"] > 0
    assert graph["node_count"] >= graph["claim_count"] + graph["experiment_count"] + graph["run_count"]
    assert any(relation == "scoped_by_experiment" for _, relation, _ in edge_keys)
    assert any(relation == "executed_as" for _, relation, _ in edge_keys)
    assert (project / "workspace" / "evidence_graph.json").exists()
    assert (project / "workspace" / "EVIDENCE_GRAPH.md").exists()
    assert summary["status"] == "ready_for_review"
    assert summary["node_count"] == graph["node_count"]
    state = build_workflow_state(project)
    evidence_graph_step = next(step for step in state["steps"] if step["step_id"] == "evidence_graph")
    assert evidence_graph_step["status"] == "complete"


def test_cli_evidence_graph(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["evidence-graph", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Evidence graph generated" in result.output
    assert (project / "workspace" / "evidence_graph.json").exists()
    assert (project / "workspace" / "EVIDENCE_GRAPH.md").exists()


def test_evidence_package_refreshes_evidence_graph(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    package = generate_evidence_package(project)

    assert package["evidence_graph"]["schema_version"] == "1.57.0"
    assert package["evidence_graph"]["node_count"] > 0
    assert any(item["name"] == "evidence_graph.json" and item["present"] for item in package["workspace_artifacts"])
    assert (project / "workspace" / "evidence_graph.json").exists()
