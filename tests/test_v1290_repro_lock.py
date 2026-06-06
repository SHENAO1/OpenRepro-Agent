from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.data_registry import register_data
from openrepro.project_manager import init_project
from openrepro.repro_lock import generate_repro_lock, repro_lock_summary, validate_repro_lock

runner = CliRunner()


def _prepare_lock_project(tmp_path: Path) -> tuple[Path, Path]:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    data_file = project / "data" / "dataset.csv"
    data_file.write_text("x,y\n1,2\n", encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Lockfile test data")
    return project, data_file


def test_generate_and_validate_repro_lock(tmp_path: Path):
    project, _ = _prepare_lock_project(tmp_path)

    lock = generate_repro_lock(project)
    validation = validate_repro_lock(project)
    summary = repro_lock_summary(project)

    assert lock["schema_version"] == "1.29.0"
    assert lock["status"] == "locked"
    assert lock["data"]["registered_count"] == 1
    assert lock["environment"]["dependencies"]["numpy"]
    assert validation["valid"] is True
    assert validation["error_count"] == 0
    assert (project / "openrepro.lock.json").exists()
    assert (project / "workspace" / "REPRO_LOCK.md").exists()
    assert (project / "workspace" / "repro_lock_validation.json").exists()
    assert (project / "workspace" / "REPRO_LOCK_VALIDATION.md").exists()
    assert summary["present"] is True
    assert summary["validation_valid"] is True


def test_validate_repro_lock_detects_data_hash_drift(tmp_path: Path):
    project, data_file = _prepare_lock_project(tmp_path)
    generate_repro_lock(project)

    data_file.write_text("x,y\n1,3\n", encoding="utf-8")
    validation = validate_repro_lock(project)

    assert validation["valid"] is False
    assert any("Registered data changed" in error for error in validation["errors"])


def test_cli_lock_and_validate_lock(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_lock_project(tmp_path)

    lock_result = runner.invoke(app, ["lock", "boc_demo"])
    validate_result = runner.invoke(app, ["validate-lock", "boc_demo"])

    assert lock_result.exit_code == 0, lock_result.output
    assert "Repro lock generated" in lock_result.output
    assert validate_result.exit_code == 0, validate_result.output
    assert "Repro lock is valid" in validate_result.output
