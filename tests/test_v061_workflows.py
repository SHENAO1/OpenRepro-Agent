from pathlib import Path

from typer.testing import CliRunner

from openrepro.analyzer import analyze_project
from openrepro.artifact_manager import validate_run_manifest
from openrepro.cli import app
from openrepro.demo_runner import run_demo
from openrepro.document_loader import ingest_source
from openrepro.planner import generate_experiment_plan
from openrepro.project_manager import init_project
from openrepro.repair import apply_repair_actions, preview_repair_actions

runner = CliRunner()


def _prepare_project(tmp_path: Path) -> tuple[Path, Path]:
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC Notes\n\nFormula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 128",
        encoding="utf-8",
    )
    ingest_source(project, source)
    analyze_project(project)
    generate_experiment_plan(project)
    run_dir = Path(run_demo(project)["run_dir"])
    (run_dir / "data" / "demo_metrics.json").write_text("{}", encoding="utf-8")
    return project, run_dir


def test_apply_manifest_repair_after_dry_run(tmp_path: Path):
    project, run_dir = _prepare_project(tmp_path)

    preview = preview_repair_actions(project, run_dir)
    result = apply_repair_actions(project, run_dir, only="manifest", confirm=True)
    validation = validate_run_manifest(run_dir)

    assert preview["action_count"] >= 1
    assert result["schema_version"] == "0.6.1"
    assert result["modified_file_count"] == 1
    assert validation["valid"] is True
    assert (project / "workspace" / "repair_apply.json").exists()
    assert (project / "workspace" / "REPAIR_APPLY.md").exists()


def test_repair_apply_requires_confirm(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prepare_project(tmp_path)

    result = runner.invoke(app, ["repair", "boc_demo", "--apply", "--only", "manifest"])

    assert result.exit_code == 1
    assert "requires --confirm" in result.output


def test_repair_apply_cli_regenerates_manifest(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project, run_dir = _prepare_project(tmp_path)

    result = runner.invoke(app, ["repair", "boc_demo", "--apply", "--only", "manifest", "--confirm"])

    assert result.exit_code == 0, result.output
    assert "Repair apply completed" in result.output
    assert validate_run_manifest(run_dir)["valid"] is True
    assert (project / "workspace" / "repair_apply.json").exists()
