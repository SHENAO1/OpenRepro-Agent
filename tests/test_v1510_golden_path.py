from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.golden_path import run_golden_path
from openrepro.utils import read_json

runner = CliRunner()


def test_golden_path_runs_packaged_random_search_example(tmp_path: Path):
    result = run_golden_path("random_demo", base_dir=tmp_path)
    project = tmp_path / "random_demo"
    golden = read_json(project / "workspace" / "golden_path.json")

    assert result["status"] == "ready"
    assert result["template"] == "random-search-toy"
    assert result["quality_gate_status"] == "passed"
    assert golden["run_dir"] == result["run_dir"]
    assert (project / "workspace" / "GOLDEN_PATH.md").exists()
    assert (project / "reports" / "report.md").exists()

    run_dir = Path(result["run_dir"])
    metrics = read_json(run_dir / "data" / "metrics.json")
    assert metrics["random_better"] is True


def test_cli_start_uses_golden_path(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["start", "random_demo"])

    assert result.exit_code == 0, result.output
    assert "Golden path status: ready" in result.output
    assert (tmp_path / "random_demo" / "workspace" / "golden_path.json").exists()
