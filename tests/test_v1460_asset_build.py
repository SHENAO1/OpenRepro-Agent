from pathlib import Path

from typer.testing import CliRunner

from openrepro.asset_build import asset_build_summary, materialize_assets, plan_asset_build
from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_asset_build_plan_blocks_unsafe_source_steps(tmp_path: Path):
    init_project("build_demo", base_dir=tmp_path)
    project = tmp_path / "build_demo"

    plan = plan_asset_build(project, target="ingest", refresh_catalog=True)
    summary = asset_build_summary(project)

    assert plan["schema_version"] == "1.46.0"
    assert plan["status"] == "blocked"
    assert plan["blocked_step_count"] > 0
    assert plan["materialize_step_count"] == 0
    assert any(step["step_id"] == "ingest" and step["action"] == "skip_unsafe" for step in plan["steps"])
    assert summary["present"] is True
    assert summary["schema_version"] == "1.46.0"
    assert (project / "workspace" / "asset_build_plan.json").exists()
    assert (project / "workspace" / "ASSET_BUILD_PLAN.md").exists()


def test_asset_build_materialize_dry_run_for_missing_local_ui(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    for path in [
        project / "reports" / "local_ui" / "index.html",
        project / "reports" / "local_ui_manifest.json",
        project / "workspace" / "local_ui_summary.json",
        project / "workspace" / "LOCAL_UI_SUMMARY.md",
    ]:
        if path.exists():
            path.unlink()

    plan = plan_asset_build(project, target="local_ui")
    materialization = materialize_assets(project, step_id="local_ui")
    readback = read_json(project / "workspace" / "asset_materialization.json")

    assert plan["status"] == "ready"
    assert plan["top_step_id"] == "local_ui"
    assert plan["materialize_step_count"] == 1
    assert materialization["status"] == "dry_run"
    assert materialization["selected_step_count"] == 1
    assert readback["schema_version"] == "1.46.0"
    assert (project / "workspace" / "ASSET_MATERIALIZATION.md").exists()


def test_cli_assets_plan_and_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("build_demo", base_dir=tmp_path)

    planned = runner.invoke(app, ["assets", "plan", "build_demo", "--refresh-catalog"])
    summarized = runner.invoke(app, ["assets", "summary", "build_demo"])

    assert planned.exit_code == 0, planned.output
    assert "Asset build plan generated" in planned.output
    assert summarized.exit_code == 0, summarized.output
    assert "Asset Build Summary" in summarized.output
    assert (tmp_path / "build_demo" / "workspace" / "asset_build_plan.json").exists()
