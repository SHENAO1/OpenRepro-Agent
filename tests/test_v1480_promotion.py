from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.promotion import plan_promotion, promotion_summary, record_promotion
from openrepro.utils import safe_write_text, write_json

runner = CliRunner()


def _write_delivery_gates(project: Path) -> None:
    write_json(project / "reports" / "delivery_bundle.json", {"status": "ready"})
    write_json(project / "reports" / "readiness_review_validation.json", {"status": "passed"})
    safe_write_text(project / "reports" / "local_ui" / "index.html", "<html>local ui</html>")
    write_json(project / "workspace" / "ci_validation.json", {"status": "passed"})
    write_json(project / "workspace" / "plugin_validation.json", {"status": "passed"})


def test_promotion_plan_blocks_missing_report_gates(tmp_path: Path):
    init_project("promo_demo", base_dir=tmp_path)
    project = tmp_path / "promo_demo"

    plan = plan_promotion(project, target="report", candidate_id="review-pack", to_state="validated")

    assert plan["schema_version"] == "1.48.0"
    assert plan["status"] == "blocked"
    assert plan["failed_gate_count"] > 0
    assert plan["top_blocker"] == "evidence_package_present"
    assert (project / "workspace" / "promotion_plan.json").exists()
    assert (project / "workspace" / "PROMOTION_PLAN.md").exists()


def test_record_promotion_requires_confirm_and_passing_gates(tmp_path: Path):
    init_project("promo_demo", base_dir=tmp_path)
    project = tmp_path / "promo_demo"
    _write_delivery_gates(project)

    plan = plan_promotion(project, target="delivery", candidate_id="release-1", to_state="released")
    dry_run = record_promotion(project, target="delivery", candidate_id="release-1", to_state="released")
    recorded = record_promotion(
        project,
        target="delivery",
        candidate_id="release-1",
        to_state="released",
        reviewer="qa",
        note="All engineering gates passed.",
        confirm=True,
    )
    summary = promotion_summary(project)

    assert plan["status"] == "ready"
    assert dry_run["status"] == "dry_run"
    assert recorded["status"] == "recorded"
    assert recorded["recorded"] is True
    assert summary["promotion_count"] == 1
    assert summary["latest_state"] == "released"
    assert (project / "workspace" / "promotion_registry.json").exists()
    assert (project / "workspace" / "PROMOTION_REGISTRY.md").exists()


def test_cli_promote_plan_record_summary(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("promo_demo", base_dir=tmp_path)
    project = tmp_path / "promo_demo"
    _write_delivery_gates(project)

    planned = runner.invoke(app, ["promote", "plan", "promo_demo", "--target", "delivery", "--candidate-id", "release-1", "--to", "released"])
    recorded = runner.invoke(
        app,
        [
            "promote",
            "record",
            "promo_demo",
            "--target",
            "delivery",
            "--candidate-id",
            "release-1",
            "--to",
            "released",
            "--reviewer",
            "qa",
            "--confirm",
        ],
    )
    summarized = runner.invoke(app, ["promote", "summary", "promo_demo"])

    assert planned.exit_code == 0, planned.output
    assert "Promotion gates passed" in planned.output
    assert recorded.exit_code == 0, recorded.output
    assert "Promotion recorded" in recorded.output
    assert summarized.exit_code == 0, summarized.output
    assert "Promotion Summary" in summarized.output
