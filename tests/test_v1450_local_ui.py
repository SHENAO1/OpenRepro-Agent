from pathlib import Path

from typer.testing import CliRunner

from openrepro.ci_integration import init_ci_config, validate_ci_config
from openrepro.cli import app
from openrepro.local_ui import generate_local_ui, local_ui_summary
from openrepro.project_manager import init_project
from openrepro.utils import read_json

runner = CliRunner()


def test_generate_local_ui_with_existing_ci_artifacts(tmp_path: Path):
    init_project("ui_demo", base_dir=tmp_path)
    project = tmp_path / "ui_demo"
    init_ci_config(project, test_command="python -m pytest tests/test_cli.py -q")
    validate_ci_config(project)

    ui = generate_local_ui(project, export_zip=True)
    summary = local_ui_summary(project)
    manifest = read_json(project / "reports" / "local_ui_manifest.json")

    assert ui["schema_version"] == "1.45.0"
    assert ui["status"] == "partial"
    assert ui["panel_count"] == 5
    assert ui["present_panel_count"] >= 1
    assert any(panel["id"] == "automation" for panel in ui["panels"])
    assert manifest["schema_version"] == "1.45.0"
    assert summary["present"] is True
    assert summary["schema_version"] == "1.45.0"
    assert (project / "reports" / "local_ui" / "index.html").exists()
    assert (project / "workspace" / "local_ui_summary.json").exists()
    assert (project / "workspace" / "LOCAL_UI_SUMMARY.md").exists()
    assert (project / "reports" / "local_ui.zip").exists()
    html = (project / "reports" / "local_ui" / "index.html").read_text(encoding="utf-8")
    assert "OpenRepro Local UI" in html
    assert "Search artifacts" in html
    assert "CI summary" in html


def test_cli_serve_build_and_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("ui_demo", base_dir=tmp_path)

    built = runner.invoke(app, ["serve", "build", "ui_demo", "--zip"])
    summarized = runner.invoke(app, ["serve", "summary", "ui_demo"])

    assert built.exit_code == 0, built.output
    assert "Local UI generated" in built.output
    assert summarized.exit_code == 0, summarized.output
    assert "Local UI Summary" in summarized.output
    assert (tmp_path / "ui_demo" / "reports" / "local_ui" / "index.html").exists()
