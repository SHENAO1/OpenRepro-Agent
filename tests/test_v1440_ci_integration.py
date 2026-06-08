from pathlib import Path

from typer.testing import CliRunner

from openrepro.ci_integration import ci_summary, init_ci_config, validate_ci_config
from openrepro.cli import app
from openrepro.project_manager import init_project

runner = CliRunner()


def test_init_and_validate_ci_config(tmp_path: Path):
    init_project("ci_demo", base_dir=tmp_path)
    project = tmp_path / "ci_demo"

    summary = init_ci_config(project, test_command="python -m pytest tests/test_cli.py -q")
    validation = validate_ci_config(project)
    existing = init_ci_config(project)
    readback = ci_summary(project)

    assert summary["schema_version"] == "1.44.0"
    assert summary["status"] == "written"
    assert validation["status"] == "passed"
    assert validation["valid"] is True
    assert existing["status"] == "preserved"
    assert readback["present"] is True
    assert (project / ".github" / "workflows" / "openrepro-ci.yml").exists()
    assert (project / "workspace" / "CI_VALIDATION.md").exists()


def test_cli_ci_commands(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("ci_demo", base_dir=tmp_path)
    project = tmp_path / "ci_demo"

    initialized = runner.invoke(app, ["ci", "init", "ci_demo", "--test-command", "python -m pytest tests/test_cli.py -q"])
    validated = runner.invoke(app, ["ci", "validate", "ci_demo"])
    summarized = runner.invoke(app, ["ci", "summary", "ci_demo"])

    assert initialized.exit_code == 0, initialized.output
    assert "CI workflow scaffold generated" in initialized.output
    assert validated.exit_code == 0, validated.output
    assert "CI workflow scaffold is valid" in validated.output
    assert summarized.exit_code == 0, summarized.output
    assert (project / "workspace" / "ci_summary.json").exists()
