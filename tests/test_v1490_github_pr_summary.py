from pathlib import Path

from typer.testing import CliRunner

from openrepro.ci_integration import init_ci_config, validate_ci_config
from openrepro.cli import app
from openrepro.github_pr_summary import generate_github_pr_summary, github_pr_summary_status
from openrepro.local_ui import generate_local_ui
from openrepro.project_manager import init_project

runner = CliRunner()


def test_generate_github_pr_summary_ready_with_local_ci(tmp_path: Path):
    init_project("pr_demo", base_dir=tmp_path)
    project = tmp_path / "pr_demo"
    init_ci_config(project)
    validate_ci_config(project)
    generate_local_ui(project)

    summary = generate_github_pr_summary(project, pr_number=7, repo_dir=Path.cwd())
    status = github_pr_summary_status(project)
    comment = (project / "reports" / "pr_comment.md").read_text(encoding="utf-8")

    assert summary["schema_version"] == "1.49.0"
    assert summary["status"] == "ready"
    assert summary["failed_check_count"] == 0
    assert status["present"] is True
    assert status["schema_version"] == "1.49.0"
    assert "OpenRepro Local Review Summary" in comment
    assert "Remote CI success is not inferred" in comment
    assert (project / "workspace" / "github_pr_summary.json").exists()
    assert (project / "workspace" / "GITHUB_PR_SUMMARY.md").exists()


def test_github_pr_summary_blocks_missing_required_checks(tmp_path: Path):
    init_project("pr_demo", base_dir=tmp_path)
    project = tmp_path / "pr_demo"

    summary = generate_github_pr_summary(project, repo_dir=tmp_path)

    assert summary["status"] == "blocked"
    assert summary["failed_check_count"] >= 2
    assert any(check["name"] == "ci_workflow_present" and not check["passed"] for check in summary["checks"])


def test_cli_github_pr_summary_and_status(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("pr_demo", base_dir=tmp_path)
    project = tmp_path / "pr_demo"
    init_ci_config(project)
    validate_ci_config(project)
    generate_local_ui(project)

    generated = runner.invoke(app, ["github", "pr-summary", "pr_demo", "--pr-number", "7", "--repo-dir", str(Path.cwd())])
    summarized = runner.invoke(app, ["github", "summary", "pr_demo"])

    assert generated.exit_code == 0, generated.output
    assert "GitHub PR summary generated" in generated.output
    assert summarized.exit_code == 0, summarized.output
    assert "GitHub PR Summary" in summarized.output
    assert (project / "reports" / "pr_comment.md").exists()
