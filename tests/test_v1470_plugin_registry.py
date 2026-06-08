from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.plugin_registry import plugin_registry_summary, register_plugin, validate_plugin_registry
from openrepro.project_manager import init_project
from openrepro.utils import read_json, read_yaml

runner = CliRunner()


def test_register_and_validate_declarative_plugin(tmp_path: Path):
    init_project("plugin_demo", base_dir=tmp_path)
    project = tmp_path / "plugin_demo"

    registry = register_plugin(
        project,
        plugin_id="dashboard-publisher",
        kind="command",
        entrypoint="openrepro dashboard <project>",
        description="Build the static dashboard.",
        capabilities=["dashboard", "handoff"],
        run_mode="safe_command",
    )
    validation = validate_plugin_registry(project)
    summary = plugin_registry_summary(project)
    config = read_yaml(project / "openrepro.plugins.yaml")

    assert registry["schema_version"] == "1.47.0"
    assert registry["plugin_count"] == 1
    assert validation["status"] == "passed"
    assert validation["valid"] is True
    assert summary["present"] is True
    assert summary["validation_status"] == "passed"
    assert config["plugins"][0]["plugin_id"] == "dashboard-publisher"
    assert (project / "workspace" / "plugin_registry.json").exists()
    assert (project / "workspace" / "PLUGIN_REGISTRY.md").exists()
    assert (project / "workspace" / "plugin_validation.json").exists()
    assert (project / "workspace" / "PLUGIN_VALIDATION.md").exists()


def test_plugin_validation_blocks_unsafe_safe_command(tmp_path: Path):
    init_project("plugin_demo", base_dir=tmp_path)
    project = tmp_path / "plugin_demo"

    register_plugin(
        project,
        plugin_id="experiment-runner",
        kind="command",
        entrypoint="openrepro run-experiment plugin_demo --confirm",
        run_mode="safe_command",
    )
    validation = read_json(project / "workspace" / "plugin_validation.json")

    assert validation["status"] == "failed"
    assert validation["valid"] is False
    assert any(issue["code"] == "unsafe_command" for issue in validation["errors"])


def test_cli_plugins_register_list_validate_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("plugin_demo", base_dir=tmp_path)

    registered = runner.invoke(
        app,
        [
            "plugins",
            "register",
            "plugin_demo",
            "--id",
            "report-export",
            "--kind",
            "reporter",
            "--entrypoint",
            "external-report-export",
            "--capability",
            "reports",
        ],
    )
    listed = runner.invoke(app, ["plugins", "list", "plugin_demo"])
    validated = runner.invoke(app, ["plugins", "validate", "plugin_demo"])
    summarized = runner.invoke(app, ["plugins", "summary", "plugin_demo"])

    assert registered.exit_code == 0, registered.output
    assert "Plugin registered" in registered.output
    assert listed.exit_code == 0, listed.output
    assert "report-export" in listed.output
    assert validated.exit_code == 0, validated.output
    assert "Plugin registry is valid" in validated.output
    assert summarized.exit_code == 0, summarized.output
    assert "Plugin Summary" in summarized.output
    assert (tmp_path / "plugin_demo" / "openrepro.plugins.yaml").exists()
