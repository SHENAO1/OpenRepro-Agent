from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.doctor import run_doctor
from openrepro.project_manager import init_project

runner = CliRunner()


def test_doctor_writes_health_artifacts(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    result = run_doctor(project)

    assert result["schema_version"] == "0.6.2"
    assert result["healthy"] is True
    assert result["check_count"] >= 1
    assert any(item["code"] == "provider_mock" for item in result["checks"])
    assert (project / "workspace" / "doctor.json").exists()
    assert (project / "workspace" / "DOCTOR.md").exists()


def test_doctor_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("boc_demo", base_dir=tmp_path)

    result = runner.invoke(app, ["doctor", "boc_demo"])

    assert result.exit_code == 0, result.output
    assert "Doctor passed" in result.output
    assert (tmp_path / "boc_demo" / "workspace" / "doctor.json").exists()
