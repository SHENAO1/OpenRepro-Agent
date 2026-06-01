from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "OpenRepro-Agent v0.2.0" in result.output


def test_cli_full_workflow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "notes.md"
    source.write_text("# BOC CLI Notes\n\nBOC pseudo-random code and autocorrelation metrics.", encoding="utf-8")

    commands = [
        ["init", "boc_demo"],
        ["ingest", "boc_demo", "--source", str(source)],
        ["analyze", "boc_demo"],
        ["plan", "boc_demo"],
        ["run-demo", "boc_demo"],
        ["validate", "boc_demo"],
        ["run-sweep", "boc_demo", "--noise-std", "0.0", "--noise-std", "0.1", "--seed", "1"],
        ["validate", "boc_demo"],
        ["report", "boc_demo"],
        ["handoff", "boc_demo"],
        ["status", "boc_demo"],
    ]
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 0, result.output

    project = tmp_path / "boc_demo"
    assert (project / "sources" / "notes.md").exists()
    assert (project / "workspace" / "paper_summary.md").exists()
    assert (project / "workspace" / "MODEL_LEDGER.md").exists()
    assert (project / "workspace" / "EXPERIMENT_PLAN.md").exists()
    assert (project / "reports" / "report.md").exists()
    run_dirs = list((project / "outputs").iterdir())
    assert len(run_dirs) == 2
    assert any((run_dir / "figures" / "correlation.png").exists() for run_dir in run_dirs)
    assert any((run_dir / "data" / "demo_metrics.json").exists() for run_dir in run_dirs)
    assert any((run_dir / "data" / "sweep_results.json").exists() for run_dir in run_dirs)
    assert all((run_dir / "manifest.json").exists() for run_dir in run_dirs)
