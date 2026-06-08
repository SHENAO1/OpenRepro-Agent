from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.security_policy import init_security_policy, run_security_audit, security_summary
from openrepro.utils import read_json, safe_write_text

runner = CliRunner()


def test_security_policy_clean_project_passes(tmp_path: Path):
    init_project("security_demo", base_dir=tmp_path)
    project = tmp_path / "security_demo"

    policy = init_security_policy(project)
    audit = run_security_audit(project)
    summary = security_summary(project)

    assert policy["schema_version"] == "1.50.0"
    assert audit["schema_version"] == "1.50.0"
    assert audit["status"] == "passed"
    assert audit["valid"] is True
    assert audit["finding_count"] == 0
    assert summary["present"] is True
    assert summary["status"] == "passed"
    assert (project / "workspace" / "security_policy.json").exists()
    assert (project / "workspace" / "SECURITY_POLICY.md").exists()
    assert (project / "workspace" / "security_audit.json").exists()
    assert (project / "workspace" / "SECURITY_AUDIT.md").exists()


def test_security_audit_detects_secret_without_leaking_value(tmp_path: Path):
    init_project("security_demo", base_dir=tmp_path)
    project = tmp_path / "security_demo"
    fake_secret = "sk-test1234567890abcdef"
    safe_write_text(project / "sources" / "notes.md", f"token = {fake_secret}\n")

    audit = run_security_audit(project)
    audit_json = (project / "workspace" / "security_audit.json").read_text(encoding="utf-8")
    audit_markdown = (project / "workspace" / "SECURITY_AUDIT.md").read_text(encoding="utf-8")

    assert audit["status"] == "failed"
    assert audit["valid"] is False
    assert audit["high_count"] == 1
    assert any(finding["code"] == "secret_pattern" for finding in audit["findings"])
    assert any(finding["path"] == "sources/notes.md" and finding["line"] == 1 for finding in audit["findings"])
    assert fake_secret not in audit_json
    assert fake_secret not in audit_markdown


def test_cli_security_init_audit_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("security_demo", base_dir=tmp_path)

    initialized = runner.invoke(app, ["security", "init", "security_demo"])
    audited = runner.invoke(app, ["security", "audit", "security_demo"])
    summarized = runner.invoke(app, ["security", "summary", "security_demo"])
    audit = read_json(tmp_path / "security_demo" / "workspace" / "security_audit.json")

    assert initialized.exit_code == 0, initialized.output
    assert "Security policy initialized" in initialized.output
    assert audited.exit_code == 0, audited.output
    assert "Security audit passed" in audited.output
    assert summarized.exit_code == 0, summarized.output
    assert "Security Summary" in summarized.output
    assert audit["status"] == "passed"
