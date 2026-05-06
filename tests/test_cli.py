from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app

runner = CliRunner()


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
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "figures" / "correlation.png").exists()
    assert (run_dirs[0] / "data" / "demo_metrics.json").exists()
