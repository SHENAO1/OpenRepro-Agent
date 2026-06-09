from pathlib import Path

from typer.testing import CliRunner

from openrepro.agent_result import agent_result_summary, ingest_agent_result, validate_agent_results
from openrepro.agent_task_spec import generate_agent_task_spec
from openrepro.cli import app
from openrepro.evidence_package import generate_evidence_package
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json, write_json
from openrepro.workflow_registry import build_workflow_state

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def _first_task_result(project: Path, status: str = "completed", requires_human_review: bool = False) -> dict:
    spec = generate_agent_task_spec(project)
    task = spec["tasks"][0]
    notes = project / "workspace" / "agent_notes.md"
    notes.write_text("# Agent Notes\n\nReviewed supervised task output.\n", encoding="utf-8")
    focus = task.get("evidence_graph_focus", {})
    node_ids = []
    for values in focus.values():
        if isinstance(values, list):
            node_ids.extend(values[:1])
    return {
        "event": "agent_result",
        "created_at": "2026-01-01T00:00:00+00:00",
        "task_spec_id": task["task_spec_id"],
        "task_id": task["task_id"],
        "agent_id": task["agent_id"],
        "status": status,
        "summary": "Reviewed the task and recorded supervised workflow evidence.",
        "artifacts_written": ["workspace/agent_notes.md"],
        "commands_run": [f"openrepro inspect {project}"],
        "evidence_graph_node_ids": node_ids,
        "requires_human_review": requires_human_review,
        "policy_acknowledged": True,
    }


def test_ingest_agent_result_validates_supervised_result(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    result_path = tmp_path / "agent_result.json"
    write_json(result_path, _first_task_result(project))

    ingest = ingest_agent_result(project, result_path)
    validation = read_json(project / "workspace" / "agent_result_validation.json")
    summary = agent_result_summary(project)

    assert ingest["schema_version"] == "1.59.0"
    assert ingest["status"] == "validated"
    assert validation["status"] == "validated"
    assert validation["result_count"] == 1
    assert validation["valid_result_count"] == 1
    assert validation["issue_count"] == 0
    assert summary["status"] == "validated"
    assert (project / "workspace" / "agent_results.json").exists()
    assert (project / "workspace" / "agent_results.jsonl").exists()
    assert (project / "workspace" / "AGENT_RESULT_REVIEW.md").exists()


def test_validate_agent_result_flags_forbidden_paths_and_commands(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    result = _first_task_result(project)
    result["artifacts_written"] = ["../outside.txt", "workspace/review_decisions.json"]
    result["commands_run"] = [f"openrepro run-experiment {project} --experiment-id baseline --confirm"]
    result["policy_acknowledged"] = False
    result_path = tmp_path / "bad_agent_result.json"
    write_json(result_path, result)

    ingest = ingest_agent_result(project, result_path)
    validation = validate_agent_results(project)

    issue_codes = {issue["code"] for issue in validation["issues"]}
    assert ingest["status"] == "invalid"
    assert validation["status"] == "invalid"
    assert validation["issue_count"] >= 3
    assert {"artifact_outside_project", "forbidden_artifact_path", "forbidden_command", "policy_not_acknowledged"} <= issue_codes


def test_cli_agent_result_ingest_and_validate(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    result_path = tmp_path / "agent_result.json"
    write_json(result_path, _first_task_result(project, status="needs_human_review", requires_human_review=True))

    ingest = runner.invoke(app, ["agent-result", "ingest", "boc_demo", "--file", str(result_path)])
    validate = runner.invoke(app, ["agent-result", "validate", "boc_demo"])
    status = get_status(project)

    assert ingest.exit_code == 0, ingest.output
    assert "Agent result ingested" in ingest.output
    assert validate.exit_code == 0, validate.output
    assert "Agent result validation completed" in validate.output
    assert status.agent_result_exists is True
    assert status.agent_result_status == "needs_human_review"
    assert status.agent_result_needs_human_review_count == 1


def test_agent_result_validation_integrates_refresh_workflow_and_package(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)
    state = build_workflow_state(project)
    step = next(item for item in state["steps"] if item["step_id"] == "agent_result_validation")
    package = generate_evidence_package(project)

    assert step["status"] == "complete"
    assert (project / "workspace" / "agent_result_validation.json").exists()
    assert (project / "workspace" / "AGENT_RESULT_REVIEW.md").exists()
    assert package["agent_results"]["schema_version"] == "1.59.0"
    assert package["agent_results"]["status"] == "no_results"
    assert any(item["name"] == "agent_result_validation.json" and item["present"] for item in package["workspace_artifacts"])
