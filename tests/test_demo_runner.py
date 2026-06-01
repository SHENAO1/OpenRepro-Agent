from pathlib import Path

from openrepro.artifact_manager import validate_run_manifest
from openrepro.demo_runner import run_demo, run_sweep
from openrepro.document_loader import ingest_source
from openrepro.project_manager import init_project


def _prepare_project(tmp_path: Path) -> Path:
    init_project("boc_demo", base_dir=tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# BOC Notes\n\nBOC correlation demo.", encoding="utf-8")
    project = tmp_path / "boc_demo"
    ingest_source(project, source)
    return project


def test_run_demo_generates_timestamped_artifacts(tmp_path: Path):
    project = _prepare_project(tmp_path)

    metadata = run_demo(project)
    run_dir = Path(metadata["run_dir"])

    assert run_dir.exists()
    for name in ["logs", "figures", "data", "reports", "configs", "code", "api_usage", "handoff"]:
        assert (run_dir / name).is_dir()
    assert (run_dir / "logs" / "run.log").exists()
    assert (run_dir / "figures" / "correlation.png").exists()
    assert (run_dir / "data" / "demo_signal.npy").exists()
    assert (run_dir / "data" / "correlation.npy").exists()
    assert (run_dir / "data" / "demo_metrics.json").exists()
    assert (run_dir / "reports" / "demo_report.md").exists()
    assert (run_dir / "configs" / "project_config_snapshot.yaml").exists()
    assert (run_dir / "api_usage" / "api_usage.jsonl").exists()
    assert (run_dir / "api_usage" / "api_usage_summary.json").exists()
    assert (run_dir / "handoff" / "AGENT_HANDOFF.md").exists()
    assert (run_dir / "metadata.json").exists()
    assert (run_dir / "manifest.json").exists()
    assert validate_run_manifest(run_dir)["valid"] is True


def test_api_usage_summary_fields(tmp_path: Path):
    project = _prepare_project(tmp_path)

    metadata = run_demo(project)
    summary = metadata["api_usage_summary"]

    assert summary["total_calls"] == 0
    assert summary["total_prompt_tokens"] == 0
    assert summary["total_completion_tokens"] == 0
    assert summary["total_tokens"] == 0
    assert summary["estimated_total_cost_usd"] == 0.0
    assert "mock" in summary["providers"]
    assert summary["providers"]["mock"]["calls"] == 0


def test_validate_run_manifest_detects_tampering(tmp_path: Path):
    project = _prepare_project(tmp_path)

    metadata = run_demo(project)
    run_dir = Path(metadata["run_dir"])
    (run_dir / "data" / "demo_metrics.json").write_text("{}", encoding="utf-8")

    result = validate_run_manifest(run_dir)

    assert result["valid"] is False
    assert any("SHA-256 mismatch" in error or "Size mismatch" in error for error in result["errors"])


def test_run_sweep_generates_artifacts(tmp_path: Path):
    project = _prepare_project(tmp_path)

    metadata = run_sweep(project, noise_std_values=[0.0, 0.1], seeds=[1, 2])
    run_dir = Path(metadata["run_dir"])

    assert metadata["result_count"] == 4
    assert (run_dir / "data" / "sweep_results.json").exists()
    assert (run_dir / "data" / "sweep_metrics.csv").exists()
    assert (run_dir / "figures" / "sweep_correlation_peak.png").exists()
    assert (run_dir / "reports" / "sweep_report.md").exists()
    assert (run_dir / "metadata.json").exists()
    assert (run_dir / "manifest.json").exists()
    assert validate_run_manifest(run_dir)["valid"] is True
