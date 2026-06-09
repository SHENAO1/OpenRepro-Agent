from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.data_registry import register_data
from openrepro.dataset_card import (
    data_quality_gate_summary,
    dataset_card_summary,
    generate_dataset_card,
    run_data_quality_gate,
)
from openrepro.project_manager import init_project

runner = CliRunner()


def _project_with_csv(tmp_path: Path, content: str) -> Path:
    init_project("data_demo", base_dir=tmp_path)
    project = tmp_path / "data_demo"
    data_file = project / "data" / "dataset.csv"
    data_file.write_text(content, encoding="utf-8")
    register_data(project, data_file, role="dataset", note="Dataset quality fixture")
    return project


def test_dataset_card_and_quality_gate_pass_for_structured_csv(tmp_path: Path):
    project = _project_with_csv(
        tmp_path,
        "id,label,split,feature\n1,0,train,0.1\n2,1,train,0.2\n3,0,test,0.3\n",
    )

    card = generate_dataset_card(project)
    gate = run_data_quality_gate(project)
    card_summary = dataset_card_summary(project)
    gate_summary = data_quality_gate_summary(project)

    assert card["schema_version"] == "1.55.0"
    assert card["status"] == "ready"
    assert card["dataset_count"] == 1
    assert card["label_dataset_count"] == 1
    assert card["split_dataset_count"] == 1
    assert gate["schema_version"] == "1.55.0"
    assert gate["status"] == "passed"
    assert gate["valid"] is True
    assert gate["failed_count"] == 0
    assert card_summary["status"] == "ready"
    assert gate_summary["status"] == "passed"
    assert (project / "workspace" / "DATASET_CARD.md").exists()
    assert (project / "workspace" / "DATA_QUALITY_GATE.md").exists()


def test_data_quality_gate_fails_high_missingness(tmp_path: Path):
    project = _project_with_csv(
        tmp_path,
        "id,label,split,feature\n1,0,train,\n2,1,train,\n3,0,test,0.3\n",
    )

    gate = run_data_quality_gate(project, max_missing_ratio=0.5)

    assert gate["status"] == "failed"
    assert gate["valid"] is False
    assert gate["top_failed_check"] == "missingness_within_threshold"
    assert any(check["check_id"] == "missingness_within_threshold" and check["status"] == "failed" for check in gate["checks"])


def test_cli_dataset_card_and_data_quality(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _project_with_csv(
        tmp_path,
        "id,label,split,feature\n1,0,train,0.1\n2,1,train,0.2\n3,0,test,0.3\n",
    )

    card = runner.invoke(app, ["dataset-card", "generate", "data_demo"])
    quality = runner.invoke(app, ["data-quality", "run", "data_demo"])
    summary = runner.invoke(app, ["data-quality", "summary", "data_demo"])

    assert card.exit_code == 0, card.output
    assert "Dataset card generated" in card.output
    assert quality.exit_code == 0, quality.output
    assert "Data quality gate passed" in quality.output
    assert summary.exit_code == 0, summary.output
    assert "failed_count" in summary.output
