from pathlib import Path

from typer.testing import CliRunner

from openrepro.artifact_cache import (
    add_artifact_cache,
    artifact_cache_summary,
    gc_artifact_cache,
    list_artifact_cache,
    verify_artifact_cache,
)
from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json
from openrepro.workflow_registry import workflow_step_map

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def _cache_project(tmp_path: Path) -> Path:
    init_project("cache_demo", base_dir=tmp_path)
    project = tmp_path / "cache_demo"
    (project / "sources" / "paper.md").write_text("# Paper\n\nEvidence notes.\n", encoding="utf-8")
    (project / "workspace" / "notes.txt").write_text("Derived note.\n", encoding="utf-8")
    (project / "data" / "table.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    return project


def test_add_and_verify_artifact_cache(tmp_path: Path):
    project = _cache_project(tmp_path)

    cache = add_artifact_cache(project)
    summary = artifact_cache_summary(project)
    validation = verify_artifact_cache(project)
    listed = list_artifact_cache(project)
    cached_paths = {entry["path"] for entry in cache["entries"]}

    assert cache["schema_version"] == "1.39.0"
    assert cache["status"] == "ready"
    assert "sources/paper.md" in cached_paths
    assert "workspace/artifact_cache.json" not in cached_paths
    assert (project / "workspace" / "artifact_cache.json").exists()
    assert (project / "workspace" / "ARTIFACT_CACHE.md").exists()
    assert summary["present"] is True
    assert summary["cached_file_count"] == cache["cached_file_count"]
    assert validation["status"] == "passed"
    assert validation["valid"] is True
    assert listed["cached_file_count"] == cache["cached_file_count"]


def test_cache_verification_reports_source_drift_without_invalidating_blob(tmp_path: Path):
    project = _cache_project(tmp_path)
    add_artifact_cache(project)

    (project / "sources" / "paper.md").write_text("# Paper\n\nChanged notes.\n", encoding="utf-8")
    validation = verify_artifact_cache(project)

    assert validation["valid"] is True
    assert validation["source_changed_count"] == 1
    assert any(record["path"] == "sources/paper.md" and record["source_current"] is False for record in validation["records"])


def test_cache_target_and_gc(tmp_path: Path):
    project = _cache_project(tmp_path)
    cache = add_artifact_cache(project, target=Path("data/table.csv"))
    orphan = project / ".openrepro" / "cache" / "sha256" / "zz" / "orphan"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("orphan", encoding="utf-8")

    result = gc_artifact_cache(project)

    assert cache["cached_file_count"] == 1
    assert cache["entries"][0]["path"] == "data/table.csv"
    assert result["removed_blob_count"] == 1
    assert orphan.exists() is False


def test_cli_artifact_cache(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _cache_project(tmp_path)

    added = runner.invoke(app, ["cache", "add", "cache_demo"])
    listed = runner.invoke(app, ["cache", "list", "cache_demo"])
    verified = runner.invoke(app, ["cache", "verify", "cache_demo"])
    collected = runner.invoke(app, ["cache", "gc", "cache_demo"])

    assert added.exit_code == 0, added.output
    assert "Artifact cache updated" in added.output
    assert listed.exit_code == 0, listed.output
    assert verified.exit_code == 0, verified.output
    assert collected.exit_code == 0, collected.output
    assert (tmp_path / "cache_demo" / "workspace" / "artifact_cache_validation.json").exists()


def test_refresh_generates_artifact_cache(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    cache = read_json(project / "workspace" / "artifact_cache.json")
    cached_paths = {entry["path"] for entry in cache["entries"]}

    assert refresh["status"] == "complete"
    assert any(step["name"] == "artifact_cache" and step["status"] == "passed" for step in refresh["steps"])
    assert cache["schema_version"] == "1.39.0"
    assert cache["cached_file_count"] > 0
    assert "workspace/artifact_cache.json" not in cached_paths


def test_workflow_registers_artifact_cache_step():
    step = workflow_step_map()["artifact_cache"]

    assert step.command == "openrepro cache add <project>"
    assert step.dependencies == ("asset_catalog",)
