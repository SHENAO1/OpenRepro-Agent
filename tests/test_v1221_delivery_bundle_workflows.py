from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.delivery_bundle import generate_delivery_bundle, delivery_bundle_summary
from openrepro.project_manager import get_status, init_project
from openrepro.refresh import generate_refresh_run

from test_v1180_workflows import _prepare_refresh_project

runner = CliRunner()


def test_generate_delivery_bundle_ready_after_refresh(tmp_path: Path):
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    bundle = generate_delivery_bundle(project, export_zip=True)
    summary = delivery_bundle_summary(project)
    status = get_status(project)

    assert bundle["schema_version"] == "1.22.1"
    assert bundle["status"] == "ready"
    assert bundle["missing_file_count"] == 0
    assert bundle["top_command"] is None
    assert (project / "reports" / "delivery_bundle.json").exists()
    assert (project / "reports" / "DELIVERY_BUNDLE.md").exists()
    assert (project / "reports" / "delivery_bundle.zip").exists()
    assert summary["status"] == "ready"
    assert status.delivery_bundle_exists is True
    assert status.delivery_bundle_status == "ready"


def test_delivery_bundle_surfaces_missing_prerequisites(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    bundle = generate_delivery_bundle(project)

    assert bundle["status"] == "needs_work"
    assert bundle["missing_file_count"] > 0
    assert bundle["top_command"] is not None
    assert bundle["files"][0]["present"] is False


def test_cli_delivery_bundle(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _prepare_refresh_project(tmp_path)
    generate_refresh_run(project, export_zip=True)

    result = runner.invoke(app, ["delivery-bundle", "boc_demo", "--zip"])

    assert result.exit_code == 0, result.output
    assert "Delivery bundle generated" in result.output
    assert (project / "reports" / "delivery_bundle.json").exists()
    assert (project / "reports" / "delivery_bundle.zip").exists()
