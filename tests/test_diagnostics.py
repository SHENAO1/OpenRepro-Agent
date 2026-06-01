from pathlib import Path

from openrepro.artifact_manager import validate_run_manifest
from openrepro.demo_runner import run_demo
from openrepro.diagnostics import diagnose_project, diagnose_validation_result
from openrepro.document_loader import ingest_source
from openrepro.project_manager import init_project


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC correlation demo.", encoding="utf-8")
    ingest_source(project, source)
    return project


def test_diagnose_validation_result_for_hash_mismatch(tmp_path: Path):
    project = _prepare_project(tmp_path)
    metadata = run_demo(project)
    run_dir = Path(metadata["run_dir"])
    (run_dir / "data" / "demo_metrics.json").write_text("{}", encoding="utf-8")

    validation = validate_run_manifest(run_dir)
    issues = diagnose_validation_result(validation)

    assert any(item["code"] == "manifest_mismatch" for item in issues)
    assert any("repair_suggestion" in item for item in issues)


def test_diagnose_project_for_missing_artifact(tmp_path: Path):
    project = _prepare_project(tmp_path)
    metadata = run_demo(project)
    run_dir = Path(metadata["run_dir"])
    (run_dir / "figures" / "correlation.png").unlink()

    result = diagnose_project(project, run_dir)

    assert result["healthy"] is False
    assert any(item["code"] == "missing_artifact" for item in result["issues"])
