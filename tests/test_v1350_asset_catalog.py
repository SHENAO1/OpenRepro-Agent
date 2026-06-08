from pathlib import Path

from typer.testing import CliRunner

from openrepro.asset_catalog import (
    asset_catalog_summary,
    generate_asset_catalog,
    generate_asset_catalog_graph,
    get_catalog_asset,
    list_catalog_assets,
)
from openrepro.cli import app
from openrepro.refresh import generate_refresh_run
from openrepro.utils import read_json

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_asset_catalog_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)

    catalog = generate_asset_catalog(project)
    summary = asset_catalog_summary(project)

    assert catalog["schema_version"] == "1.35.0"
    assert catalog["status"] == "ready"
    assert catalog["asset_count"] > 0
    assert catalog["kind_counts"].get("data", 0) >= 1
    assert catalog["kind_counts"].get("run", 0) >= 1
    assert (project / "workspace" / "asset_catalog.json").exists()
    assert (project / "workspace" / "ASSET_CATALOG.md").exists()
    assert (project / "workspace" / "ASSET_CATALOG_GRAPH.md").exists()
    assert summary["present"] is True
    assert summary["schema_version"] == "1.35.0"


def test_catalog_list_show_and_graph(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    catalog = generate_asset_catalog(project)
    data_asset = next(asset for asset in catalog["assets"] if asset["kind"] == "data")

    listed = list_catalog_assets(project, kind="data")
    shown = get_catalog_asset(project, data_asset["asset_id"])
    graph = generate_asset_catalog_graph(project)

    assert listed["asset_count"] >= 1
    assert all(asset["kind"] == "data" for asset in listed["assets"])
    assert shown["asset_id"] == data_asset["asset_id"]
    assert graph["status"] == "ready"
    assert (project / "workspace" / "ASSET_CATALOG_GRAPH.md").exists()


def test_refresh_generates_asset_catalog(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)

    refresh = generate_refresh_run(project)
    catalog = read_json(project / "workspace" / "asset_catalog.json")

    assert refresh["status"] == "complete"
    assert any(step["name"] == "asset_catalog" and step["status"] == "passed" for step in refresh["steps"])
    assert catalog["schema_version"] == "1.35.0"
    assert catalog["asset_count"] > 0


def test_cli_catalog_commands(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project)
    catalog = read_json(project / "workspace" / "asset_catalog.json")
    asset_id = catalog["assets"][0]["asset_id"]

    build = runner.invoke(app, ["catalog", "build", "boc_demo"])
    listed = runner.invoke(app, ["catalog", "list", "boc_demo", "--kind", "data"])
    shown = runner.invoke(app, ["catalog", "show", "boc_demo", asset_id])
    graph = runner.invoke(app, ["catalog", "graph", "boc_demo"])

    assert build.exit_code == 0, build.output
    assert "Asset catalog generated" in build.output
    assert listed.exit_code == 0, listed.output
    assert shown.exit_code == 0, shown.output
    assert graph.exit_code == 0, graph.output
    assert (project / "workspace" / "asset_catalog.json").exists()
