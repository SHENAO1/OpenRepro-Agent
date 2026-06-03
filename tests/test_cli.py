from pathlib import Path

from typer.testing import CliRunner

from openrepro.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "OpenRepro-Agent v1.9.1" in result.output


def test_cli_full_workflow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "notes.md"
    source.write_text(
        "# BOC CLI Notes\n\nBOC pseudo-random code and autocorrelation metrics.\n\n"
        "Formula: x[n] = c[n] * s[n] + noise.\n\nnoise_std = 0.05\ncode_length: 128",
        encoding="utf-8",
    )
    data_file = tmp_path / "cli_dataset.json"
    data_file.write_text('{"samples": [1, 2, 3]}', encoding="utf-8")
    task = tmp_path / "task.json"
    task.write_text(
        f"""{{
  "schema_version": "0.3.0",
  "task_id": "cli_task",
  "paper_title": "CLI task",
  "source_files": ["{source.as_posix()}"],
  "expected_artifacts": [
    "workspace/paper_summary.md",
    "workspace/MODEL_LEDGER.md",
    "workspace/EXPERIMENT_PLAN.md",
    "outputs/<timestamp>_<project>/figures/correlation.png",
    "outputs/<timestamp>_<project>/data/demo_metrics.json"
  ],
  "evaluation_metrics": ["signal_length", "correlation_peak"]
}}
""",
        encoding="utf-8",
    )
    suite = tmp_path / "suite.json"
    suite.write_text(
        f"""{{
  "schema_version": "0.4.0",
  "suite_id": "cli_suite",
  "tasks": [{{"task": "{task.as_posix()}", "project": "boc_suite_project"}}]
}}
""",
        encoding="utf-8",
    )

    commands = [
        ["init", "boc_demo"],
        ["configure-provider", "boc_demo", "--provider", "mock", "--disable-real-api"],
        ["ingest", "boc_demo", "--source", str(source)],
        ["analyze", "boc_demo"],
        ["plan", "boc_demo"],
        ["list-templates"],
        ["list-candidates", "boc_demo"],
        ["review-candidates", "boc_demo", "--candidate-id", "F001", "--status", "needs_more_evidence", "--reviewer", "cli-test"],
        ["approve-candidates", "boc_demo", "--all", "--reviewer", "cli-test"],
        ["register-data", "boc_demo", "--path", str(data_file), "--role", "dataset", "--note", "CLI fixture data"],
        ["validate-data", "boc_demo"],
        ["scaffold-experiment", "boc_demo", "--experiment-id", "cli_exp"],
        ["validate-inputs", "boc_demo", "--experiment-id", "cli_exp"],
        ["validate-experiment-spec", "boc_demo", "--experiment-id", "cli_exp"],
        ["run-experiment", "boc_demo", "--experiment-id", "cli_exp", "--confirm"],
        ["quality-gate", "boc_demo"],
        ["rerun-experiment", "boc_demo", "--experiment-id", "cli_exp", "--confirm"],
        ["compare-experiments", "boc_demo", "--experiment-id", "cli_exp"],
        ["run-demo", "boc_demo"],
        ["validate", "boc_demo"],
        ["validate", "boc_demo", "--all"],
        ["inspect", "boc_demo"],
        ["run-sweep", "boc_demo", "--noise-std", "0.0", "--noise-std", "0.1", "--seed", "1"],
        ["quality-gate", "boc_demo"],
        ["validate", "boc_demo"],
        ["validate", "boc_demo", "--all"],
        ["compare-runs", "boc_demo"],
        ["quality-gate", "boc_demo", "--all"],
        ["lineage", "boc_demo"],
        ["trace-claims", "boc_demo", "--validate"],
        ["validate-claims", "boc_demo"],
        ["scorecard", "boc_demo"],
        ["gaps", "boc_demo"],
        ["todo", "boc_demo"],
        ["checkpoints", "boc_demo"],
        ["advance", "boc_demo", "--dry-run"],
        ["review-board", "boc_demo"],
        ["doctor", "boc_demo"],
        ["diagnose", "boc_demo"],
        ["repair-plan", "boc_demo"],
        ["repair", "boc_demo", "--dry-run"],
        ["benchmark", "--task", str(task), "--project", "boc_benchmark"],
        ["benchmark-suite", "--suite", str(suite)],
        ["benchmark-index"],
        ["report", "boc_demo"],
        ["handoff", "boc_demo"],
        ["evidence-package", "boc_demo"],
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
    assert (project / "workspace" / "inspect_summary.json").exists()
    assert (project / "workspace" / "experiment_scaffold_summary.json").exists()
    assert (project / "workspace" / "verified_candidates.json").exists()
    assert (project / "workspace" / "candidate_reviews.json").exists()
    assert (project / "workspace" / "data_index.json").exists()
    assert (project / "workspace" / "data_validation.json").exists()
    assert (project / "workspace" / "repair_dry_run.json").exists()
    assert (project / "workspace" / "repair_plan.json").exists()
    assert (project / "workspace" / "experiment_comparison.json").exists()
    assert (project / "workspace" / "EXPERIMENT_COMPARISON.md").exists()
    assert (project / "workspace" / "run_comparison.json").exists()
    assert (project / "workspace" / "run_lineage.json").exists()
    assert (project / "workspace" / "doctor.json").exists()
    assert (project / "reports" / "report.md").exists()
    assert (project / "reports" / "evidence_package.json").exists()
    assert (project / "reports" / "evidence_package.md").exists()
    assert (project / "experiments" / "cli_exp" / "APPROVAL_REQUIRED.md").exists()
    assert (project / "experiments" / "cli_exp" / "experiment_config.json").exists()
    assert (project / "experiments" / "cli_exp" / "experiment_spec.json").exists()
    assert (project / "workspace" / "experiment_spec_validation.json").exists()
    assert (project / "workspace" / "DATA_INDEX.md").exists()
    assert (project / "workspace" / "DATA_VALIDATION.md").exists()
    assert (project / "workspace" / "quality_gate_summary.json").exists()
    assert (project / "workspace" / "QUALITY_GATE_SUMMARY.md").exists()
    assert (project / "workspace" / "claim_trace.json").exists()
    assert (project / "workspace" / "CLAIM_TRACE.md").exists()
    assert (project / "workspace" / "claim_trace_validation.json").exists()
    assert (project / "workspace" / "CLAIM_TRACE_VALIDATION.md").exists()
    assert (project / "workspace" / "reproduction_scorecard.json").exists()
    assert (project / "workspace" / "REPRODUCTION_SCORECARD.md").exists()
    assert (project / "workspace" / "reproduction_gaps.json").exists()
    assert (project / "workspace" / "REPRODUCTION_GAPS.md").exists()
    assert (project / "workspace" / "workflow_checkpoints.json").exists()
    assert (project / "workspace" / "WORKFLOW_CHECKPOINTS.md").exists()
    assert (project / "workspace" / "advance_plan.json").exists()
    assert (project / "workspace" / "ADVANCE_PLAN.md").exists()
    assert (project / "workspace" / "review_board.json").exists()
    assert (project / "workspace" / "REVIEW_BOARD.md").exists()
    assert (project / "workspace" / "review_decisions.json").exists()
    assert (project / "workspace" / "REVIEW_DECISIONS.md").exists()
    run_dirs = list((project / "outputs").iterdir())
    assert len(run_dirs) == 4
    assert any((run_dir / "figures" / "correlation.png").exists() for run_dir in run_dirs)
    assert any((run_dir / "data" / "demo_metrics.json").exists() for run_dir in run_dirs)
    assert any((run_dir / "data" / "sweep_results.json").exists() for run_dir in run_dirs)
    assert any((run_dir / "data" / "execution_result.json").exists() for run_dir in run_dirs)
    assert all((run_dir / "manifest.json").exists() for run_dir in run_dirs)
    assert any((run_dir / "reports" / "quality_gate.json").exists() for run_dir in run_dirs)
    assert (tmp_path / "benchmarks" / "runs" / "benchmark_index.json").exists()
    assert (tmp_path / "benchmarks" / "runs" / "benchmark_index.md").exists()
