"""Typer command-line interface for OpenRepro-Agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .acceptance_criteria import generate_acceptance_criteria
from .advance import generate_advance_plan
from .agent_board import generate_agent_board
from .analyzer import analyze_project
from .approval import approve_candidates
from .artifact_manager import latest_run_dir, validate_all_run_manifests, validate_run_manifest
from .benchmark_runner import generate_benchmark_index, run_benchmark, run_benchmark_suite
from .candidate_review import list_candidates, review_candidates
from .checkpoints import generate_workflow_checkpoints
from .claim_evidence_binder import generate_claim_evidence_binder, validate_claim_evidence_binder
from .claim_evidence_report import generate_claim_evidence_report
from .claim_evidence_report_validation import validate_claim_evidence_report
from .claim_signoff import ALLOWED_CLAIM_SIGNOFF_DECISIONS, generate_claim_signoffs, record_claim_signoff
from .claim_signoff_validation import validate_claim_signoffs
from .claim_trace import generate_claim_trace, validate_claim_trace
from .collaboration_pack import generate_collaboration_pack
from .config import configure_api_provider, provider_status
from .data_registry import register_data, validate_data_index
from .dashboard import generate_dashboard
from .delivery_bundle import generate_delivery_bundle
from .diagnostics import diagnose_error, diagnose_project, diagnose_validation_result
from .demo_runner import run_demo, run_sweep
from .document_loader import ingest_source
from .doctor import run_doctor
from .evidence_package import generate_evidence_package
from .experiment_compare import compare_experiments, rerun_experiment
from .experiment_scaffold import scaffold_experiment
from .experiment_inputs import set_experiment_input, validate_experiment_inputs
from .experiment_runner import run_experiment
from .experiment_spec import validate_experiment_spec
from .experiment_templates import list_experiment_templates
from .freshness import generate_artifact_freshness
from .gaps import generate_reproduction_gaps
from .handoff_generator import generate_handoff
from .inspector import inspect_project
from .lineage import generate_run_lineage
from .multi_agent_plan import generate_multi_agent_plan
from .multi_agent_plan_validation import validate_multi_agent_plan
from .planner import generate_experiment_plan
from .protocol_coverage import generate_protocol_coverage
from .protocol_plan import generate_protocol_plan
from .protocol_preflight import generate_protocol_preflight
from .project_profile import generate_project_profile
from .project_manager import get_status, init_project, require_project
from .quality_gate import evaluate_all_quality_gates, evaluate_run_quality
from .readiness_review import generate_readiness_review
from .readiness_review_validation import validate_readiness_review
from .refresh import generate_refresh_run
from .repair import apply_repair_actions, create_repair_plan, preview_repair_actions
from .report_generator import generate_report
from .reproduction_protocol import generate_reproduction_protocol
from .review_board import generate_review_board
from .review_action_plan import generate_review_action_plan
from .review_decisions import ALLOWED_REVIEW_DECISIONS, record_review_decision
from .review_site import generate_review_site
from .reviewer_packet import generate_reviewer_packet
from .run_compare import compare_runs
from .scorecard import generate_reproduction_scorecard
from .timeline import generate_project_timeline

app = typer.Typer(
    name="openrepro",
    help="OpenRepro-Agent: minimal paper reproduction workflow CLI.",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()


def _success(message: str) -> None:
    console.print(f"[green]OK[/green] {message}")


def _warn(message: str) -> None:
    console.print(f"[yellow]![/yellow] {message}")


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Show OpenRepro-Agent version and exit."),
) -> None:
    """OpenRepro-Agent command group."""
    if version:
        console.print(f"OpenRepro-Agent v{__version__}")
        raise typer.Exit()


@app.command("init")
def init_cmd(project_name: str = typer.Argument(..., help="Project directory name to create.")) -> None:
    """Initialize a paper reproduction project."""
    result = init_project(project_name)
    if result.created:
        _success(result.message)
    else:
        _warn(result.message)
    console.print("\nNext steps:")
    for step in result.next_steps:
        console.print(f"  - {step}")


@app.command("ingest")
def ingest_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    source: Path = typer.Option(..., "--source", "-s", help="Markdown/txt/PDF source file."),
) -> None:
    """Ingest Markdown/txt research notes or extract a PDF."""
    project_dir = require_project(project_name)
    record = ingest_source(project_dir, source)
    if record.status != "ready":
        _warn(record.note)
    else:
        _success(f"Ingested {record.source_name}")
    console.print(f"Copied path: {record.copied_path}")
    if record.extracted_text_path:
        console.print(f"Extracted text: {record.extracted_text_path}")
    console.print(f"Updated: {project_dir / 'workspace' / 'source_index.json'}")


@app.command("analyze")
def analyze_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate paper_summary.md, MODEL_LEDGER.md, and analysis_result.json."""
    project_dir = require_project(project_name)
    result = analyze_project(project_dir)
    _success("Analysis artifacts generated.")
    console.print(f"Detected keywords: {', '.join(result.get('detected_keywords', [])) or 'none'}")
    for file in result.get("generated_files", []):
        console.print(f"  - {file}")


@app.command("plan")
def plan_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate workspace/EXPERIMENT_PLAN.md."""
    project_dir = require_project(project_name)
    path = generate_experiment_plan(project_dir)
    _success(f"Experiment plan generated: {path}")


@app.command("configure-provider")
def configure_provider_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    provider: str = typer.Option("mock", "--provider", help="Provider name: mock or openai."),
    model: str | None = typer.Option(None, "--model", help="Provider model name."),
    enable_real_api: bool = typer.Option(False, "--enable-real-api", help="Explicitly enable real provider calls."),
    disable_real_api: bool = typer.Option(False, "--disable-real-api", help="Disable real provider calls."),
    api_key_env: str | None = typer.Option(None, "--api-key-env", help="Environment variable containing the API key."),
    endpoint: str | None = typer.Option(None, "--endpoint", help="OpenAI-compatible chat completions endpoint."),
    cache_enabled: bool = typer.Option(False, "--cache-enabled", help="Enable provider response cache."),
    cache_disabled: bool = typer.Option(False, "--cache-disabled", help="Disable provider response cache."),
    cache_ttl_seconds: int | None = typer.Option(None, "--cache-ttl-seconds", help="Provider cache TTL in seconds."),
    redact_prompts: bool = typer.Option(False, "--redact-prompts", help="Redact prompt/response previews in usage records."),
    no_redact_prompts: bool = typer.Option(False, "--no-redact-prompts", help="Disable prompt/response preview redaction."),
) -> None:
    """Configure provider settings without storing secrets."""
    if enable_real_api and disable_real_api:
        _warn("--enable-real-api and --disable-real-api cannot be combined.")
        raise typer.Exit(1)
    if cache_enabled and cache_disabled:
        _warn("--cache-enabled and --cache-disabled cannot be combined.")
        raise typer.Exit(1)
    if redact_prompts and no_redact_prompts:
        _warn("--redact-prompts and --no-redact-prompts cannot be combined.")
        raise typer.Exit(1)
    project_dir = require_project(project_name)
    real_api_setting = True if enable_real_api else False if disable_real_api else None
    cache_setting = True if cache_enabled else False if cache_disabled else None
    redaction_setting = True if redact_prompts else False if no_redact_prompts else None
    config = configure_api_provider(
        project_dir,
        provider=provider,
        model=model,
        enable_real_api=real_api_setting,
        api_key_env=api_key_env,
        endpoint=endpoint,
        cache_enabled=cache_setting,
        cache_ttl_seconds=cache_ttl_seconds,
        redact_prompts=redaction_setting,
    )
    status = provider_status(project_dir)
    _success("Provider configuration updated.")
    table = Table(title=f"Provider: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "default_provider",
        "default_model",
        "enable_real_api",
        "api_key_env",
        "api_key_present",
        "cache_enabled",
        "cache_ttl_seconds",
        "redact_prompts",
        "ready_for_real_calls",
    ]:
        table.add_row(key, str(status[key]))
    console.print(table)
    if config["default_provider"] != "mock" and not status["ready_for_real_calls"]:
        _warn("Real provider is configured but not ready; check --enable-real-api and the API key environment variable.")


@app.command("run-demo")
def run_demo_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Run the built-in lightweight BOC-like demo."""
    project_dir = require_project(project_name)
    metadata = run_demo(project_dir)
    _success("Demo run completed.")
    console.print(f"Run directory: {metadata['run_dir']}")
    console.print(f"Metrics: {metadata['metrics']}")


@app.command("run-sweep")
def run_sweep_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    noise_std: list[float] | None = typer.Option(
        None,
        "--noise-std",
        help="Noise standard deviation value. Repeat to build a sweep grid.",
    ),
    seed: list[int] | None = typer.Option(
        None,
        "--seed",
        help="Random seed value. Repeat to build a sweep grid.",
    ),
) -> None:
    """Run the built-in lightweight BOC-like parameter sweep."""
    project_dir = require_project(project_name)
    metadata = run_sweep(project_dir, noise_std_values=noise_std, seeds=seed)
    _success("Sweep run completed.")
    console.print(f"Run directory: {metadata['run_dir']}")
    console.print(f"Result count: {metadata['result_count']}")


@app.command("run-experiment")
def run_experiment_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str = typer.Option(..., "--experiment-id", help="Experiment scaffold id under experiments/."),
    confirm: bool = typer.Option(False, "--confirm", help="Required to execute a verified experiment runner."),
    timeout_seconds: int = typer.Option(300, "--timeout-seconds", help="Runner timeout in seconds."),
) -> None:
    """Run a verified experiment scaffold and record execution evidence."""
    project_dir = require_project(project_name)
    try:
        metadata = run_experiment(
            project_dir,
            experiment_id=experiment_id,
            confirm=confirm,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    if metadata["status"] == "completed":
        _success("Experiment run completed.")
    else:
        _warn("Experiment run completed with runner failure.")
    console.print(f"Run directory: {metadata['run_dir']}")
    console.print(f"Exit code: {metadata['exit_code']}")
    if metadata.get("quality_gate"):
        console.print(f"Quality gate: {metadata['quality_gate']['status']}")


@app.command("quality-gate")
def quality_gate_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    run_dir: Path | None = typer.Option(None, "--run-dir", help="Run directory. Defaults to the latest project run."),
    all_runs: bool = typer.Option(False, "--all", help="Evaluate quality gates for all project run directories."),
) -> None:
    """Evaluate quality gates for a run directory."""
    project_dir = require_project(project_name)
    if all_runs:
        try:
            summary = evaluate_all_quality_gates(project_dir)
        except Exception as exc:
            _warn(str(exc))
            raise typer.Exit(1) from exc
        table = Table(title=f"Quality Gate Summary: {project_name}")
        table.add_column("Run")
        table.add_column("Command")
        table.add_column("Status")
        table.add_column("Failed Checks")
        for item in summary["runs"]:
            table.add_row(
                str(item["run_id"]),
                str(item["command"]),
                str(item["status"]),
                ", ".join(item["failed_check_names"]),
            )
        console.print(table)
        console.print(f"Runs: {summary['run_count']}")
        console.print(f"Failed: {summary['failed_count']}")
        console.print(f"Failed checks: {summary['failed_gate_check_names']}")
        console.print(f"JSON: {project_dir / 'workspace' / 'quality_gate_summary.json'}")
        console.print(f"Markdown: {project_dir / 'workspace' / 'QUALITY_GATE_SUMMARY.md'}")
        if summary["failed_count"]:
            raise typer.Exit(1)
        _success("All run quality gates passed.")
        return
    try:
        result = evaluate_run_quality(project_dir, run_dir)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Run Quality Gate: {result['run_id']}")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    for check in result["checks"]:
        table.add_row(str(check["name"]), str(check["status"]), str(check["message"]))
    console.print(table)
    console.print(f"Status: {result['status']}")
    console.print(f"JSON: {Path(result['run_dir']) / 'reports' / 'quality_gate.json'}")
    console.print(f"Markdown: {Path(result['run_dir']) / 'reports' / 'quality_gate.md'}")
    if not result["valid"]:
        raise typer.Exit(1)
    _success("Run quality gate passed.")


@app.command("rerun-experiment")
def rerun_experiment_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str = typer.Option(..., "--experiment-id", help="Experiment scaffold id under experiments/."),
    confirm: bool = typer.Option(False, "--confirm", help="Required to execute the experiment runner again."),
    timeout_seconds: int = typer.Option(300, "--timeout-seconds", help="Runner timeout in seconds."),
) -> None:
    """Run an existing verified experiment scaffold again."""
    project_dir = require_project(project_name)
    try:
        metadata = rerun_experiment(
            project_dir,
            experiment_id=experiment_id,
            confirm=confirm,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success("Experiment rerun completed.")
    console.print(f"Run directory: {metadata['run_dir']}")
    console.print(f"Exit code: {metadata['exit_code']}")


@app.command("compare-experiments")
def compare_experiments_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str = typer.Option(..., "--experiment-id", help="Experiment scaffold id to compare."),
    left_run: Path | None = typer.Option(None, "--left-run", help="Older run directory. Defaults to second-latest experiment run."),
    right_run: Path | None = typer.Option(None, "--right-run", help="Newer run directory. Defaults to latest experiment run."),
) -> None:
    """Compare two run-experiment outputs for one experiment."""
    project_dir = require_project(project_name)
    try:
        comparison = compare_experiments(project_dir, experiment_id=experiment_id, left_run=left_run, right_run=right_run)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success("Experiment comparison written.")
    table = Table(title=f"Experiment Comparison: {experiment_id}")
    table.add_column("Metric")
    table.add_column("Left")
    table.add_column("Right")
    table.add_column("Equal")
    for item in comparison["metric_deltas"]:
        table.add_row(str(item["metric"]), str(item["left"]), str(item["right"]), str(item["equal"]))
    console.print(table)
    console.print(f"All metrics equal: {comparison['all_metrics_equal']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'experiment_comparison.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EXPERIMENT_COMPARISON.md'}")
    for warning in comparison.get("warnings", []):
        _warn(str(warning))


@app.command("trace-claims")
def trace_claims_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    validate: bool = typer.Option(False, "--validate", help="Validate claim trace freshness and link integrity after generation."),
) -> None:
    """Generate claim-to-evidence traceability artifacts."""
    project_dir = require_project(project_name)
    trace = generate_claim_trace(project_dir)
    _success("Claim trace generated.")
    console.print(f"Claims: {trace['claim_count']}")
    console.print(f"Verified claims: {trace['verified_claim_count']}")
    console.print(f"Experiments: {trace['experiment_trace_count']}")
    console.print(f"Runs: {trace['run_trace_count']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'claim_trace.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CLAIM_TRACE.md'}")
    if validate:
        validation = validate_claim_trace(project_dir)
        console.print(f"Validation: {validation['status']}")
        console.print(f"Validation issues: {validation['issue_count']}")
        console.print(f"Validation warnings: {validation['warning_count']}")
        console.print(f"Validation JSON: {project_dir / 'workspace' / 'claim_trace_validation.json'}")
        console.print(f"Validation Markdown: {project_dir / 'workspace' / 'CLAIM_TRACE_VALIDATION.md'}")
        if not validation["valid"]:
            raise typer.Exit(1)


@app.command("validate-claims")
def validate_claims_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate claim trace freshness and link integrity."""
    project_dir = require_project(project_name)
    validation = validate_claim_trace(project_dir)
    table = Table(title=f"Claim Trace Validation: {project_name}")
    table.add_column("Code")
    table.add_column("Message")
    rows = validation["issues"] or validation["warnings"]
    if rows:
        for item in rows:
            table.add_row(str(item["code"]), str(item["message"]))
    else:
        table.add_row("none", "No claim trace issues found.")
    console.print(table)
    console.print(f"Status: {validation['status']}")
    console.print(f"Issues: {validation['issue_count']}")
    console.print(f"Warnings: {validation['warning_count']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'claim_trace_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CLAIM_TRACE_VALIDATION.md'}")
    if not validation["valid"]:
        raise typer.Exit(1)
    _success("Claim trace validation passed.")


@app.command("scorecard")
def scorecard_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a workflow readiness scorecard."""
    project_dir = require_project(project_name)
    scorecard = generate_reproduction_scorecard(project_dir)
    table = Table(title=f"Reproduction Readiness Scorecard: {project_name}")
    table.add_column("Dimension")
    table.add_column("Score")
    table.add_column("Status")
    for item in scorecard["dimensions"]:
        table.add_row(str(item["label"]), str(item["score"]), str(item["status"]))
    console.print(table)
    console.print(f"Overall score: {scorecard['overall_score']}")
    console.print(f"Overall status: {scorecard['overall_status']}")
    console.print(f"Recommended actions: {len(scorecard['recommended_actions'])}")
    console.print(f"JSON: {project_dir / 'workspace' / 'reproduction_scorecard.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REPRODUCTION_SCORECARD.md'}")
    _success("Reproduction readiness scorecard generated.")


def _print_gaps(project_name: str, gaps: dict[str, object], project_dir: Path) -> None:
    table = Table(title=f"Reproduction Gaps: {project_name}")
    table.add_column("Severity")
    table.add_column("Source")
    table.add_column("Gap")
    table.add_column("Suggested")
    for item in gaps["gaps"]:
        table.add_row(str(item["severity"]), str(item["source"]), str(item["title"]), str(item["suggested_command"]))
    if not gaps["gaps"]:
        table.add_row("none", "workflow", "No open upstream reproduction workflow gaps found.", "")
    console.print(table)
    console.print(f"Status: {gaps['status']}")
    console.print(f"Open gaps: {gaps['open_count']}")
    console.print(f"Top command: {gaps['top_suggested_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'reproduction_gaps.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REPRODUCTION_GAPS.md'}")


@app.command("gaps")
def gaps_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate actionable reproduction workflow gaps."""
    project_dir = require_project(project_name)
    gaps = generate_reproduction_gaps(project_dir)
    _print_gaps(project_name, gaps, project_dir)
    _success("Reproduction gaps generated.")


@app.command("todo")
def todo_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate actionable reproduction workflow to-dos."""
    project_dir = require_project(project_name)
    gaps = generate_reproduction_gaps(project_dir)
    _print_gaps(project_name, gaps, project_dir)
    _success("Reproduction to-dos generated.")


@app.command("checkpoints")
def checkpoints_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate normalized workflow checkpoints."""
    project_dir = require_project(project_name)
    checkpoints = generate_workflow_checkpoints(project_dir)
    table = Table(title=f"Workflow Checkpoints: {project_name}")
    table.add_column("Checkpoint")
    table.add_column("Status")
    table.add_column("Next")
    for item in checkpoints["checkpoints"]:
        table.add_row(str(item["label"]), str(item["status"]), str(item.get("next_command") or ""))
    console.print(table)
    console.print(f"Status: {checkpoints['status']}")
    console.print(f"Next checkpoint: {checkpoints['next_checkpoint']}")
    console.print(f"Next command: {checkpoints['next_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'workflow_checkpoints.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'WORKFLOW_CHECKPOINTS.md'}")
    _success("Workflow checkpoints generated.")


@app.command("advance")
def advance_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the next workflow command without executing it."),
) -> None:
    """Preview the next workflow advance command."""
    if not dry_run:
        _warn("Use --dry-run to preview the next workflow command.")
        raise typer.Exit(1)
    project_dir = require_project(project_name)
    plan = generate_advance_plan(project_dir, dry_run=True)
    table = Table(title=f"Advance Plan: {project_name}")
    table.add_column("Action")
    table.add_column("Source")
    table.add_column("Command")
    table.add_column("Will Execute")
    if plan["actions"]:
        for item in plan["actions"]:
            table.add_row(str(item["action_id"]), str(item["source"]), str(item["command"]), str(item["will_execute"]))
    else:
        table.add_row("none", "workflow", "", "False")
    console.print(table)
    console.print(f"Status: {plan['status']}")
    console.print(f"Top command: {plan['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'advance_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ADVANCE_PLAN.md'}")
    _success("Advance dry-run plan generated.")


@app.command("review-board")
def review_board_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a human review board."""
    project_dir = require_project(project_name)
    board = generate_review_board(project_dir)
    table = Table(title=f"Review Board: {project_name}")
    table.add_column("Priority")
    table.add_column("Source")
    table.add_column("Item")
    table.add_column("Suggested")
    if board["items"]:
        for item in board["items"]:
            table.add_row(str(item["priority"]), str(item["source"]), str(item["title"]), str(item["suggested_command"]))
    else:
        table.add_row("none", "workflow", "No open human review items found.", "")
    console.print(table)
    console.print(f"Status: {board['status']}")
    console.print(f"Items: {board['item_count']}")
    console.print(f"Top command: {board['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'review_board.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REVIEW_BOARD.md'}")
    _success("Review board generated.")


@app.command("review-decision")
def review_decision_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    item_id: str = typer.Option(..., "--item-id", help="Review board item id to decide."),
    decision: str = typer.Option(..., "--decision", help="Decision: resolved, deferred, rejected, or needs_followup."),
    reviewer: str = typer.Option(..., "--reviewer", help="Human reviewer name or role."),
    note: str = typer.Option("", "--note", help="Decision note."),
    followup_command: str | None = typer.Option(None, "--followup-command", help="Optional follow-up command."),
) -> None:
    """Record a human decision for a review board item."""
    project_dir = require_project(project_name)
    try:
        result = record_review_decision(
            project_dir,
            item_id=item_id,
            decision=decision,
            reviewer=reviewer,
            note=note,
            followup_command=followup_command,
        )
    except Exception as exc:
        allowed = ", ".join(sorted(ALLOWED_REVIEW_DECISIONS))
        _warn(f"{exc} Allowed decisions: {allowed}")
        raise typer.Exit(1) from exc
    table = Table(title=f"Review Decisions: {project_name}")
    table.add_column("Item")
    table.add_column("Decision")
    table.add_column("Reviewer")
    table.add_column("Closes")
    for item in result["latest_decisions"]:
        table.add_row(str(item["item_id"]), str(item["decision"]), str(item["reviewer"]), str(item["closes_item"]))
    console.print(table)
    console.print(f"Status: {result['status']}")
    console.print(f"Decisions: {result['decision_count']}")
    console.print(f"Unresolved items: {result['unresolved_item_count']}")
    console.print(f"Top command: {result['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'review_decisions.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REVIEW_DECISIONS.md'}")
    _success("Review decision recorded.")


@app.command("protocol")
def protocol_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a reproduction protocol."""
    project_dir = require_project(project_name)
    protocol = generate_reproduction_protocol(project_dir)
    table = Table(title=f"Reproduction Protocol: {project_name}")
    table.add_column("Criterion")
    table.add_column("Status")
    table.add_column("Suggested")
    for item in protocol["acceptance_criteria"]:
        table.add_row(str(item["label"]), str(item["status"]), str(item["suggested_command"]))
    console.print(table)
    console.print(f"Status: {protocol['status']}")
    console.print(f"Blocking criteria: {protocol['blocking_criterion_count']}")
    console.print(f"Top command: {protocol['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'reproduction_protocol.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REPRODUCTION_PROTOCOL.md'}")
    _success("Reproduction protocol generated.")


@app.command("protocol-coverage")
def protocol_coverage_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate protocol coverage checks."""
    project_dir = require_project(project_name)
    coverage = generate_protocol_coverage(project_dir)
    table = Table(title=f"Protocol Coverage: {project_name}")
    table.add_column("Dimension")
    table.add_column("Status")
    table.add_column("Covered")
    table.add_column("Total")
    table.add_column("Coverage")
    for item in coverage["dimensions"]:
        table.add_row(
            str(item["label"]),
            str(item["status"]),
            str(item["covered_count"]),
            str(item["total_count"]),
            str(item["coverage_percent"]),
        )
    console.print(table)
    console.print(f"Status: {coverage['status']}")
    console.print(f"Coverage score: {coverage['coverage_score']}")
    console.print(f"Uncovered: {coverage['uncovered_count']}")
    console.print(f"Top command: {coverage['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'protocol_coverage.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PROTOCOL_COVERAGE.md'}")
    _success("Protocol coverage generated.")


@app.command("protocol-plan")
def protocol_plan_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate prioritized actions from protocol coverage gaps."""
    project_dir = require_project(project_name)
    plan = generate_protocol_plan(project_dir)
    table = Table(title=f"Protocol Plan: {project_name}")
    table.add_column("Action")
    table.add_column("Priority")
    table.add_column("Source")
    table.add_column("Suggested")
    for item in plan["actions"]:
        table.add_row(
            str(item["action_id"]),
            str(item["priority"]),
            str(item["source"]),
            str(item["suggested_command"]),
        )
    console.print(table)
    console.print(f"Status: {plan['status']}")
    console.print(f"Actions: {plan['action_count']}")
    console.print(f"Critical: {plan['critical_count']}")
    console.print(f"High: {plan['high_count']}")
    console.print(f"Top command: {plan['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'protocol_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PROTOCOL_PLAN.md'}")
    _success("Protocol plan generated.")


@app.command("protocol-preflight")
def protocol_preflight_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Run protocol readiness preflight checks."""
    project_dir = require_project(project_name)
    preflight = generate_protocol_preflight(project_dir)
    table = Table(title=f"Protocol Preflight: {project_name}")
    table.add_column("Check")
    table.add_column("Severity")
    table.add_column("Status")
    table.add_column("Suggested")
    for item in preflight["checks"]:
        table.add_row(
            str(item["label"]),
            str(item["severity"]),
            str(item["status"]),
            str(item["suggested_command"]),
        )
    console.print(table)
    console.print(f"Status: {preflight['status']}")
    console.print(f"Checks: {preflight['check_count']}")
    console.print(f"Blocking: {preflight['blocking_count']}")
    console.print(f"Warnings: {preflight['warning_count']}")
    console.print(f"Top command: {preflight['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'protocol_preflight.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PROTOCOL_PREFLIGHT.md'}")
    _success("Protocol preflight generated.")


@app.command("evidence-binder")
def evidence_binder_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Bind traced claims to workflow evidence."""
    project_dir = require_project(project_name)
    binder = generate_claim_evidence_binder(project_dir)
    table = Table(title=f"Claim Evidence Binder: {project_name}")
    table.add_column("Claim")
    table.add_column("Status")
    table.add_column("Experiments")
    table.add_column("Runs")
    table.add_column("Missing")
    for item in binder["claims"]:
        table.add_row(
            str(item["claim_id"]),
            str(item["status"]),
            str(len(item["linked_experiments"])),
            str(len(item["linked_runs"])),
            ", ".join(item["missing_evidence"]),
        )
    console.print(table)
    console.print(f"Status: {binder['status']}")
    console.print(f"Claims: {binder['claim_count']}")
    console.print(f"Complete claims: {binder['complete_claim_count']}")
    console.print(f"Incomplete claims: {binder['incomplete_claim_count']}")
    console.print(f"Top command: {binder['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'claim_evidence_binder.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CLAIM_EVIDENCE_BINDER.md'}")
    _success("Claim evidence binder generated.")


@app.command("validate-evidence-binder")
def validate_evidence_binder_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate claim evidence binder freshness and consistency."""
    project_dir = require_project(project_name)
    validation = validate_claim_evidence_binder(project_dir)
    table = Table(title=f"Claim Evidence Binder Validation: {project_name}")
    table.add_column("Code")
    table.add_column("Message")
    rows = validation["issues"] or validation["warnings"]
    if rows:
        for item in rows:
            table.add_row(str(item["code"]), str(item["message"]))
    else:
        table.add_row("none", "No claim evidence binder issues found.")
    console.print(table)
    console.print(f"Status: {validation['status']}")
    console.print(f"Issues: {validation['issue_count']}")
    console.print(f"Warnings: {validation['warning_count']}")
    console.print(f"Top command: {validation['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'claim_evidence_binder_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CLAIM_EVIDENCE_BINDER_VALIDATION.md'}")
    if not validation["valid"]:
        raise typer.Exit(1)
    _success("Claim evidence binder validation passed.")


@app.command("claim-signoff")
def claim_signoff_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    claim_id: str | None = typer.Option(None, "--claim-id", help="Claim id from workspace/claim_evidence_binder.json."),
    decision: str | None = typer.Option(
        None,
        "--decision",
        help=f"Claim signoff decision: {', '.join(sorted(ALLOWED_CLAIM_SIGNOFF_DECISIONS))}.",
    ),
    reviewer: str | None = typer.Option(None, "--reviewer", help="Human reviewer name."),
    note: str = typer.Option("", "--note", help="Optional signoff note."),
    followup_command: str | None = typer.Option(None, "--followup-command", help="Optional follow-up command."),
) -> None:
    """Record or summarize human signoffs for claim evidence binder claims."""
    project_dir = require_project(project_name)
    wants_record = any(value is not None for value in [claim_id, decision, reviewer])
    try:
        if wants_record:
            if claim_id is None or decision is None or reviewer is None:
                raise ValueError("--claim-id, --decision, and --reviewer are required together.")
            signoffs = record_claim_signoff(
                project_dir,
                claim_id=claim_id,
                decision=decision,
                reviewer=reviewer,
                note=note,
                followup_command=followup_command,
            )
        else:
            signoffs = generate_claim_signoffs(project_dir)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc

    table = Table(title=f"Claim Signoffs: {project_name}")
    table.add_column("Claim")
    table.add_column("Decision")
    table.add_column("Reviewer")
    table.add_column("Terminal")
    if signoffs["latest_signoffs"]:
        for item in signoffs["latest_signoffs"]:
            table.add_row(
                str(item.get("claim_id")),
                str(item.get("decision")),
                str(item.get("reviewer")),
                str(item.get("terminal")),
            )
    else:
        table.add_row("none", "none", "none", "False")
    console.print(table)
    console.print(f"Status: {signoffs['status']}")
    console.print(f"Claims: {signoffs['claim_count']}")
    console.print(f"Signed claims: {signoffs['signed_claim_count']}")
    console.print(f"Open claims: {signoffs['open_claim_count']}")
    console.print(f"Top command: {signoffs['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'claim_signoffs.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CLAIM_SIGNOFFS.md'}")
    _success("Claim signoffs updated.")


@app.command("claim-evidence-report")
def claim_evidence_report_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a reviewer-facing claim evidence report."""
    project_dir = require_project(project_name)
    report = generate_claim_evidence_report(project_dir)
    table = Table(title=f"Claim Evidence Report: {project_name}")
    table.add_column("Claim")
    table.add_column("Evidence")
    table.add_column("Signoff")
    table.add_column("Next step")
    for item in report["claims"]:
        table.add_row(
            str(item["claim_id"]),
            str(item["evidence_status"]),
            str(item["signoff_decision"]),
            str(item["next_step"]),
        )
    if not report["claims"]:
        table.add_row("none", "needs_claims", "none", "openrepro trace-claims <project>")
    console.print(table)
    console.print(f"Status: {report['status']}")
    console.print(f"Claims: {report['claim_count']}")
    console.print(f"Open actions: {report['open_action_count']}")
    console.print(f"Top command: {report['top_command']}")
    console.print(f"JSON: {project_dir / 'reports' / 'claim_evidence_report.json'}")
    console.print(f"Markdown: {project_dir / 'reports' / 'claim_evidence_report.md'}")
    _success("Claim evidence report generated.")


@app.command("validate-claim-signoffs")
def validate_claim_signoffs_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate claim signoff coverage and freshness."""
    project_dir = require_project(project_name)
    validation = validate_claim_signoffs(project_dir)
    table = Table(title=f"Claim Signoff Validation: {project_name}")
    table.add_column("Code")
    table.add_column("Message")
    rows = validation["issues"] or validation["warnings"]
    if rows:
        for item in rows:
            table.add_row(str(item["code"]), str(item["message"]))
    else:
        table.add_row("none", "No claim signoff validation issues found.")
    console.print(table)
    console.print(f"Status: {validation['status']}")
    console.print(f"Issues: {validation['issue_count']}")
    console.print(f"Warnings: {validation['warning_count']}")
    console.print(f"Top command: {validation['top_command']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'claim_signoff_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CLAIM_SIGNOFF_VALIDATION.md'}")
    if not validation["valid"]:
        raise typer.Exit(1)
    _success("Claim signoff validation passed.")


@app.command("validate-claim-evidence-report")
def validate_claim_evidence_report_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate claim evidence report freshness and consistency."""
    project_dir = require_project(project_name)
    validation = validate_claim_evidence_report(project_dir)
    table = Table(title=f"Claim Evidence Report Validation: {project_name}")
    table.add_column("Code")
    table.add_column("Message")
    rows = validation["issues"] or validation["warnings"]
    if rows:
        for item in rows:
            table.add_row(str(item["code"]), str(item["message"]))
    else:
        table.add_row("none", "No claim evidence report validation issues found.")
    console.print(table)
    console.print(f"Status: {validation['status']}")
    console.print(f"Issues: {validation['issue_count']}")
    console.print(f"Warnings: {validation['warning_count']}")
    console.print(f"Top command: {validation['top_command']}")
    console.print(f"JSON: {project_dir / 'reports' / 'claim_evidence_report_validation.json'}")
    console.print(f"Markdown: {project_dir / 'reports' / 'claim_evidence_report_validation.md'}")
    if not validation["valid"]:
        raise typer.Exit(1)
    _success("Claim evidence report validation passed.")


@app.command("reviewer-packet")
def reviewer_packet_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/reviewer_packet.zip."),
) -> None:
    """Generate a reviewer packet for human claim evidence review."""
    project_dir = require_project(project_name)
    packet = generate_reviewer_packet(project_dir, export_zip=export_zip)
    table = Table(title=f"Reviewer Packet: {project_name}")
    table.add_column("Claim")
    table.add_column("Evidence")
    table.add_column("Signoff")
    table.add_column("Risk")
    for item in packet["review_items"]:
        table.add_row(
            str(item.get("claim_id")),
            str(item.get("evidence_status")),
            str(item.get("signoff_decision")),
            ", ".join(item.get("risk_flags", [])),
        )
    if not packet["review_items"]:
        table.add_row("none", "needs_claims", "none", "needs_claims")
    console.print(table)
    console.print(f"Status: {packet['status']}")
    console.print(f"Claims: {packet['claim_count']}")
    console.print(f"Open actions: {packet['open_action_count']}")
    console.print(f"Validation issues: {packet['validation_issue_count']}")
    console.print(f"Top command: {packet['top_command']}")
    console.print(f"JSON: {project_dir / 'reports' / 'reviewer_packet.json'}")
    console.print(f"Markdown: {project_dir / 'reports' / 'reviewer_packet.md'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'reviewer_packet.zip'}")
    _success("Reviewer packet generated.")


@app.command("list-templates")
def list_templates_cmd() -> None:
    """List available experiment scaffold templates."""
    table = Table(title="OpenRepro Experiment Templates")
    table.add_column("Template", style="bold")
    table.add_column("Purpose")
    table.add_column("Required")
    table.add_column("Inputs")
    for template in list_experiment_templates():
        table.add_row(
            str(template["name"]),
            str(template["purpose"]),
            str(len(template["required"])),
            ", ".join(template["input_hints"]) or "none",
        )
    console.print(table)
    _success("Listed experiment templates.")


@app.command("validate-inputs")
def validate_inputs_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str = typer.Option(..., "--experiment-id", help="Experiment scaffold id under experiments/."),
) -> None:
    """Validate experiment input completeness for a scaffold."""
    project_dir = require_project(project_name)
    try:
        result = validate_experiment_inputs(project_dir, experiment_id)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Experiment Inputs: {experiment_id}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "required", "present", "missing", "source_counts"]:
        table.add_row(key, str(result[key]))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'experiment_input_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EXPERIMENT_INPUT_VALIDATION.md'}")
    if result["status"] != "complete":
        _warn("Experiment inputs need attention.")
        raise typer.Exit(1)
    _success("Experiment inputs are complete.")


@app.command("set-input")
def set_input_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str = typer.Option(..., "--experiment-id", help="Experiment scaffold id under experiments/."),
    name: str = typer.Option(..., "--name", help="Input name, e.g. noise_std or code_length."),
    value: str = typer.Option(..., "--value", help="Input value. JSON scalars/lists are accepted."),
    source: str = typer.Option("manual_override", "--source", help="Input source: manual_override, verified_candidate, or default."),
    note: str = typer.Option("", "--note", help="Optional note for the input override."),
) -> None:
    """Set or override a scaffold experiment input."""
    project_dir = require_project(project_name)
    try:
        result = set_experiment_input(project_dir, experiment_id, name=name, value=value, source=source, note=note)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success(f"Set input {name} for experiment {experiment_id}.")
    console.print(f"Status: {result['status']}")
    console.print(f"Missing: {result['missing']}")
    console.print(f"Inputs: {result['experiment_inputs_path']}")


@app.command("validate-experiment-spec")
def validate_experiment_spec_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str = typer.Option(..., "--experiment-id", help="Experiment scaffold id under experiments/."),
    strict: bool = typer.Option(False, "--strict", help="Fail on stale specs or warnings without refreshing the spec."),
) -> None:
    """Validate an experiment specification contract."""
    project_dir = require_project(project_name)
    try:
        result = validate_experiment_spec(project_dir, experiment_id, strict=strict)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Experiment Spec: {experiment_id}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["valid", "strict", "freshness_status", "spec_sha256", "errors", "warnings"]:
        table.add_row(key, str(result[key]))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'experiment_spec_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EXPERIMENT_SPEC_VALIDATION.md'}")
    if not result["valid"]:
        raise typer.Exit(1)
    _success("Experiment spec is valid.")


@app.command("register-data")
def register_data_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    path: Path = typer.Option(..., "--path", help="Local data file to register."),
    role: str = typer.Option("dataset", "--role", help="Data role, e.g. dataset, labels, split, or config."),
    source: str = typer.Option("manual", "--source", help="Registration source label."),
    note: str = typer.Option("", "--note", help="Optional note for the registered data file."),
) -> None:
    """Register a local data file with SHA-256 provenance."""
    project_dir = require_project(project_name)
    try:
        record = register_data(project_dir, path=path, role=role, source=source, note=note)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success(f"Registered data: {record['data_id']}")
    table = Table(title=f"Registered Data: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["data_id", "role", "path", "size_bytes", "sha256"]:
        table.add_row(key, str(record[key]))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'data_index.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'DATA_INDEX.md'}")


@app.command("validate-data")
def validate_data_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate registered data file presence and hashes."""
    project_dir = require_project(project_name)
    result = validate_data_index(project_dir)
    table = Table(title=f"Data Validation: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    summary = result["summary"]
    rows = {
        "valid": result["valid"],
        "registered_count": summary["registered_count"],
        "invalid_count": summary["invalid_count"],
        "status_counts": summary["status_counts"],
        "errors": result["errors"],
    }
    for key, value in rows.items():
        table.add_row(key, str(value))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'data_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'DATA_VALIDATION.md'}")
    if not result["valid"]:
        raise typer.Exit(1)
    _success("Registered data is valid.")


@app.command("scaffold-experiment")
def scaffold_experiment_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str | None = typer.Option(None, "--experiment-id", help="Experiment id. Defaults to a timestamp."),
    template: str = typer.Option(
        "basic",
        "--template",
        help="Experiment template: basic, boc-like, or numeric-sweep.",
    ),
    acknowledge_candidates: bool = typer.Option(
        False,
        "--acknowledge-candidates",
        help="Mark that candidate formulas/parameters are acknowledged for scaffold work.",
    ),
) -> None:
    """Create a human-gated experiment scaffold from candidate evidence."""
    project_dir = require_project(project_name)
    try:
        summary = scaffold_experiment(
            project_dir,
            experiment_id=experiment_id,
            acknowledge_candidates=acknowledge_candidates,
            template=template,
        )
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success(f"Experiment scaffold created: {summary['experiment_dir']}")
    console.print(f"Status: {summary['status']}")
    console.print(f"Template: {summary['template']}")
    console.print(f"Next step: {summary['next_step']}")


@app.command("approve-candidates")
def approve_candidates_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    formula_id: list[str] | None = typer.Option(
        None,
        "--formula-id",
        help="Formula candidate id to approve. Repeat to approve multiple formulas.",
    ),
    parameter_id: list[str] | None = typer.Option(
        None,
        "--parameter-id",
        help="Parameter candidate id to approve. Repeat to approve multiple parameters.",
    ),
    approve_all: bool = typer.Option(False, "--all", help="Approve all currently detected candidates."),
    reviewer: str = typer.Option("human", "--reviewer", help="Reviewer label recorded in the approval artifact."),
    note: str = typer.Option("", "--note", help="Verification note recorded in the approval artifact."),
) -> None:
    """Promote human-reviewed candidates into verified input artifacts."""
    project_dir = require_project(project_name)
    try:
        result = approve_candidates(
            project_dir,
            formula_ids=formula_id,
            parameter_ids=parameter_id,
            approve_all=approve_all,
            reviewer=reviewer,
            verification_note=note,
        )
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success("Verified candidate artifacts written.")
    console.print(f"Status: {result['status']}")
    console.print(f"Formulas: {result['formula_candidate_count']}")
    console.print(f"Parameters: {result['parameter_candidate_count']}")
    console.print(f"JSON: {project_dir / 'workspace' / 'verified_candidates.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'VERIFIED_CANDIDATES.md'}")


@app.command("list-candidates")
def list_candidates_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    status: str | None = typer.Option(None, "--status", help="Optional review status filter."),
) -> None:
    """List formula and parameter candidates with review state."""
    project_dir = require_project(project_name)
    result = list_candidates(project_dir, status=status)
    table = Table(title=f"Candidates: {project_name}")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Review Status")
    table.add_column("Source")
    table.add_column("Evidence")
    for item in result["candidates"]:
        table.add_row(
            str(item.get("candidate_id")),
            str(item.get("candidate_type")),
            str(item.get("review_status")),
            str(item.get("source_name")),
            str(item.get("evidence") or item.get("name") or "")[:80],
        )
    console.print(table)
    _success(f"Listed {result['candidate_count']} candidates.")


@app.command("review-candidates")
def review_candidates_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    candidate_id: list[str] | None = typer.Option(
        None,
        "--candidate-id",
        help="Candidate id to review. Repeat to review multiple candidates.",
    ),
    status: str = typer.Option(..., "--status", help="verified_by_human, rejected_by_human, or needs_more_evidence."),
    reviewer: str = typer.Option("human", "--reviewer", help="Reviewer label."),
    note: str = typer.Option("", "--note", help="Review note."),
) -> None:
    """Record a human review decision for selected candidates."""
    project_dir = require_project(project_name)
    try:
        result = review_candidates(
            project_dir,
            candidate_ids=candidate_id or [],
            status=status,
            reviewer=reviewer,
            note=note,
        )
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success(f"Recorded {result['latest_review_count']} candidate reviews.")
    console.print(f"JSON: {project_dir / 'workspace' / 'candidate_reviews.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CANDIDATE_REVIEWS.md'}")
    if status == "verified_by_human":
        console.print(f"Verified candidates: {project_dir / 'workspace' / 'verified_candidates.json'}")


@app.command("validate")
def validate_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    run_dir: Path | None = typer.Option(
        None,
        "--run-dir",
        help="Run directory to validate. Defaults to the latest project run.",
    ),
    all_runs: bool = typer.Option(False, "--all", help="Validate every run under project outputs."),
) -> None:
    """Validate a run manifest and required artifacts."""
    project_dir = require_project(project_name)
    if all_runs:
        if run_dir is not None:
            _warn("--all cannot be combined with --run-dir.")
            raise typer.Exit(1)
        results = validate_all_run_manifests(project_dir)
        if not results:
            _warn("No run directories found to validate.")
            raise typer.Exit(1)
        table = Table(title=f"OpenRepro Validation: {project_name}")
        table.add_column("Run")
        table.add_column("Command")
        table.add_column("Valid")
        table.add_column("Checked")
        table.add_column("Errors")
        for result in results:
            table.add_row(
                str(Path(result["run_dir"]).name),
                str(result.get("command") or "unknown"),
                str(result.get("valid")),
                str(result.get("checked_artifacts", 0)),
                str(len(result.get("errors", []))),
            )
        console.print(table)
        failed = [result for result in results if not result.get("valid")]
        if failed:
            console.print("\nDiagnosis:")
            for result in failed:
                console.print(f"  {result['run_dir']}")
                for item in diagnose_validation_result(result):
                    console.print(f"    - {item['code']}: {item['repair_suggestion']}")
            raise typer.Exit(1)
        _success(f"Validated {len(results)} run directories.")
        return

    target = run_dir
    if target is None:
        target = latest_run_dir(project_dir)
    elif not target.is_absolute() and not target.exists():
        target = project_dir / target

    if target is None:
        _warn("No run directory found to validate.")
        raise typer.Exit(1)

    result = validate_run_manifest(target)
    if result["valid"]:
        _success(f"Validated {result['checked_artifacts']} artifacts in {target}")
        for warning in result.get("warnings", []):
            _warn(warning)
        return

    _warn(f"Validation failed for {target}")
    for error in result.get("errors", []):
        console.print(f"  - {error}")
    for warning in result.get("warnings", []):
        _warn(warning)
    diagnosis = diagnose_validation_result(result)
    if diagnosis:
        console.print("\nDiagnosis:")
        for item in diagnosis:
            console.print(f"  - {item['code']}: {item['repair_suggestion']}")
    raise typer.Exit(1)


@app.command("inspect")
def inspect_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Inspect project sources, candidates, runs, benchmarks, and diagnosis health."""
    project_dir = require_project(project_name)
    summary = inspect_project(project_dir)
    table = Table(title=f"OpenRepro Inspect: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    rows = {
        "Sources": summary["source_count"],
        "PDF sources": summary["pdf_source_count"],
        "PDF extraction": summary["pdf_extraction_statuses"],
        "Formula candidates": summary["formula_candidate_count"],
        "Parameter candidates": summary["parameter_candidate_count"],
        "High-risk candidates": summary["candidate_high_risk_count"],
        "Candidate risk levels": summary["candidate_risk_level_counts"],
        "Verified formulas": summary["verified_formula_candidate_count"],
        "Verified parameters": summary["verified_parameter_candidate_count"],
        "Verified status": summary["verified_candidates_status"],
        "Candidate reviews": summary["candidate_review_count"],
        "Review status counts": summary["candidate_review_status_counts"],
        "Experiment scaffolds": summary["experiment_scaffold_count"],
        "Experiment templates": summary["experiment_template_counts"],
        "Input completeness": summary["experiment_input_completeness_counts"],
        "Missing required inputs": summary["experiment_missing_required_input_count"],
        "Expected artifacts attention": summary["experiment_expected_artifacts_attention_count"],
        "Spec status counts": summary["experiment_spec_status_counts"],
        "Stale specs": summary["experiment_spec_stale_count"],
        "Invalid specs": summary["experiment_spec_invalid_count"],
        "Missing specs": summary["experiment_spec_missing_count"],
        "Registered data": summary["data_registered_count"],
        "Invalid data": summary["data_invalid_count"],
        "Missing data": summary["data_missing_count"],
        "Data hash mismatches": summary["data_hash_mismatch_count"],
        "Experiment runs": summary["experiment_run_count"],
        "Latest quality gate": summary["quality_gate_status"],
        "Quality gate failed checks": summary["quality_gate_failed_check_count"],
        "Latest experiment gate": summary["experiment_quality_gate_status"],
        "Experiment gate failed checks": summary["experiment_quality_gate_failed_check_count"],
        "Failed gate check names": summary["failed_quality_gate_check_names"],
        "Claim trace": summary["claim_trace_status"],
        "Traced claims": summary["claim_trace_claim_count"],
        "Traced experiment links": summary["claim_trace_experiment_count"],
        "Claim trace validation": summary["claim_trace_validation_status"],
        "Claim trace validation issues": summary["claim_trace_validation_issue_count"],
        "Readiness score": summary["scorecard_overall_score"],
        "Scorecard status": summary["scorecard_status"],
        "Open gaps": summary["gaps_open_count"],
        "Gap status": summary["gaps_status"],
        "Checkpoint status": summary["checkpoint_status"],
        "Next checkpoint": summary["checkpoint_next_checkpoint"],
        "Advance plan": summary["advance_status"],
        "Advance actions": summary["advance_action_count"],
        "Review board": summary["review_board_status"],
        "Review items": summary["review_board_item_count"],
        "Review decisions": summary["review_decision_status"],
        "Review unresolved": summary["review_decision_unresolved_item_count"],
        "Protocol": summary["protocol_status"],
        "Protocol blockers": summary["protocol_blocking_criterion_count"],
        "Protocol coverage": summary["protocol_coverage_status"],
        "Protocol uncovered": summary["protocol_coverage_uncovered_count"],
        "Protocol plan": summary["protocol_plan_status"],
        "Protocol actions": summary["protocol_plan_action_count"],
        "Protocol preflight": summary["protocol_preflight_status"],
        "Preflight blockers": summary["protocol_preflight_blocking_count"],
        "Evidence binder": summary["claim_evidence_binder_status"],
        "Incomplete claims": summary["claim_evidence_binder_incomplete_claim_count"],
        "Binder validation": summary["claim_evidence_binder_validation_status"],
        "Binder validation issues": summary["claim_evidence_binder_validation_issue_count"],
        "Claim signoffs": summary["claim_signoff_status"],
        "Signed claims": summary["claim_signoff_signed_claim_count"],
        "Open signoff claims": summary["claim_signoff_open_claim_count"],
        "Signoff validation": summary["claim_signoff_validation_status"],
        "Signoff validation issues": summary["claim_signoff_validation_issue_count"],
        "Claim evidence report": summary["claim_evidence_report_status"],
        "Claim report actions": summary["claim_evidence_report_open_action_count"],
        "Claim report validation": summary["claim_evidence_report_validation_status"],
        "Claim report validation issues": summary["claim_evidence_report_validation_issue_count"],
        "Reviewer packet": summary["reviewer_packet_status"],
        "Reviewer packet actions": summary["reviewer_packet_open_action_count"],
        "Review site": summary["review_site_status"],
        "Review site actions": summary["review_site_open_action_count"],
        "Review site blockers": summary["review_site_blocker_count"],
        "Project timeline": summary["project_timeline_status"],
        "Timeline events": summary["project_timeline_event_count"],
        "Timeline decisions": summary["project_timeline_human_decision_count"],
        "Collaboration pack": summary["collaboration_pack_status"],
        "Collab unresolved": summary["collaboration_pack_unresolved_decision_count"],
        "Collab commands": summary["collaboration_pack_next_safe_command_count"],
        "Refresh run": summary["refresh_run_status"],
        "Refresh steps": summary["refresh_run_step_count"],
        "Refresh failures": summary["refresh_run_failed_step_count"],
        "Freshness": summary["artifact_freshness_status"],
        "Freshness stale": summary["artifact_freshness_stale_node_count"],
        "Dashboard": summary["dashboard_status"],
        "Project profile": summary["project_profile_status"],
        "Profile target claims": summary["project_profile_target_claim_count"],
        "Profile experiments": summary["project_profile_required_experiment_count"],
        "Acceptance": summary["acceptance_criteria_status"],
        "Acceptance criteria": summary["acceptance_criteria_count"],
        "Acceptance needs work": summary["acceptance_criteria_needs_work_count"],
        "Readiness review": summary["readiness_review_status"],
        "Readiness blockers": summary["readiness_review_blocker_count"],
        "Readiness validation": summary["readiness_review_validation_status"],
        "Readiness validation issues": summary["readiness_review_validation_issue_count"],
        "Review action plan": summary["review_action_plan_status"],
        "Review actions": summary["review_action_plan_open_action_count"],
        "Delivery bundle": summary["delivery_bundle_status"],
        "Delivery missing": summary["delivery_bundle_missing_file_count"],
        "Multi-agent plan": summary["multi_agent_plan_status"],
        "Multi-agent tasks": summary["multi_agent_plan_open_task_count"],
        "Multi-agent validation": summary["multi_agent_plan_validation_status"],
        "Multi-agent validation issues": summary["multi_agent_plan_validation_issue_count"],
        "Agent board": summary["agent_board_status"],
        "Agent board tasks": summary["agent_board_open_task_count"],
        "Runs": summary["run_count"],
        "Latest manifest status": summary["latest_manifest_status"],
        "Benchmark runs": summary["benchmark_run_count"],
        "Diagnosis healthy": summary["diagnosis_healthy"],
        "Diagnosis issues": summary["diagnosis_issue_count"],
        "Repair dry-run": summary["latest_repair_dry_run_status"],
        "Repair dry-run actions": summary["latest_repair_dry_run_action_count"],
        "Lineage": summary["lineage_status"],
        "Lineage runs": summary["lineage_run_count"],
        "Next step": summary["next_step"],
    }
    for key, value in rows.items():
        table.add_row(key, str(value))
    console.print(table)
    _success(f"Inspect summary written: {project_dir / 'workspace' / 'inspect_summary.json'}")


@app.command("diagnose")
def diagnose_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    run_dir: Path | None = typer.Option(
        None,
        "--run-dir",
        help="Run directory to diagnose. Defaults to the latest project run.",
    ),
) -> None:
    """Classify project/run failures and suggest repairs."""
    project_dir = require_project(project_name)
    target = run_dir
    if target is not None and not target.is_absolute() and not target.exists():
        target = project_dir / target
    result = diagnose_project(project_dir, target)
    if result["healthy"]:
        _success("No diagnosis issues found.")
        return
    _warn("Diagnosis found issues.")
    for item in result["issues"]:
        console.print(f"  - {item['code']}: {item['message']}")
        console.print(f"    repair: {item['repair_suggestion']}")


@app.command("repair-plan")
def repair_plan_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    run_dir: Path | None = typer.Option(
        None,
        "--run-dir",
        help="Run directory to plan repairs for. Defaults to the latest project run.",
    ),
) -> None:
    """Write an advisory repair plan from diagnosis output."""
    project_dir = require_project(project_name)
    target = run_dir
    if target is not None and not target.is_absolute() and not target.exists():
        target = project_dir / target
    plan = create_repair_plan(project_dir, target)
    _success(f"Repair plan written with {plan['issue_count']} issues.")
    console.print(f"JSON: {project_dir / 'workspace' / 'repair_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REPAIR_PLAN.md'}")


@app.command("repair")
def repair_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    run_dir: Path | None = typer.Option(
        None,
        "--run-dir",
        help="Run directory to preview repairs for. Defaults to the latest project run.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview controlled repair actions without changing files."),
    apply: bool = typer.Option(False, "--apply", help="Apply explicitly confirmed low-risk repairs."),
    only: str = typer.Option("manifest", "--only", help="Repair scope. v0.6.1 supports only 'manifest'."),
    confirm: bool = typer.Option(False, "--confirm", help="Required when applying repairs."),
) -> None:
    """Preview or apply controlled repair actions."""
    if dry_run and apply:
        _warn("--dry-run and --apply cannot be combined.")
        raise typer.Exit(1)
    if not dry_run and not apply:
        _warn("Use --dry-run to preview or --apply --only manifest --confirm to apply.")
        raise typer.Exit(1)
    project_dir = require_project(project_name)
    target = run_dir
    if target is not None and not target.is_absolute() and not target.exists():
        target = project_dir / target
    if dry_run:
        preview = preview_repair_actions(project_dir, target)
        _success(f"Repair dry-run written with {preview['action_count']} actions.")
        console.print(f"JSON: {project_dir / 'workspace' / 'repair_dry_run.json'}")
        console.print(f"Markdown: {project_dir / 'workspace' / 'REPAIR_DRY_RUN.md'}")
        return
    try:
        result = apply_repair_actions(project_dir, target, only=only, confirm=confirm)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success(f"Repair apply completed with {result['modified_file_count']} modified files.")
    console.print(f"JSON: {project_dir / 'workspace' / 'repair_apply.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REPAIR_APPLY.md'}")


@app.command("compare-runs")
def compare_runs_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    left_run: Path | None = typer.Option(None, "--left-run", help="Older run directory. Defaults to second-latest."),
    right_run: Path | None = typer.Option(None, "--right-run", help="Newer run directory. Defaults to latest."),
) -> None:
    """Compare two project run directories."""
    project_dir = require_project(project_name)
    try:
        comparison = compare_runs(project_dir, left_run=left_run, right_run=right_run)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _success("Run comparison written.")
    table = Table(title=f"Run Comparison: {project_name}")
    table.add_column("Metric")
    table.add_column("Left")
    table.add_column("Right")
    table.add_column("Delta")
    for item in comparison["metric_deltas"]:
        table.add_row(str(item["metric"]), str(item["left"]), str(item["right"]), str(item["delta"]))
    console.print(table)


@app.command("lineage")
def lineage_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate run lineage hashes for project runs."""
    project_dir = require_project(project_name)
    lineage = generate_run_lineage(project_dir)
    _success(f"Run lineage written with {lineage['run_count']} runs.")
    console.print(f"JSON: {project_dir / 'workspace' / 'run_lineage.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'RUN_LINEAGE.md'}")


@app.command("doctor")
def doctor_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Check local dependencies, project structure, config, and provider readiness."""
    project_dir = require_project(project_name)
    result = run_doctor(project_dir)
    if result["healthy"]:
        _success(f"Doctor passed with {result['warn_count']} warnings.")
    else:
        _warn(f"Doctor found {result['fail_count']} failures and {result['warn_count']} warnings.")
    table = Table(title=f"OpenRepro Doctor: {project_name}")
    table.add_column("Status")
    table.add_column("Code")
    table.add_column("Message")
    for check in result["checks"]:
        table.add_row(check["status"], check["code"], check["message"])
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'doctor.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'DOCTOR.md'}")


@app.command("benchmark")
def benchmark_cmd(
    task: Path = typer.Option(..., "--task", help="Benchmark task JSON file."),
    project: str | None = typer.Option(None, "--project", help="Project directory. Defaults to task_id."),
) -> None:
    """Run a workflow-compliance benchmark task."""
    try:
        result = run_benchmark(task, project_name=project)
    except Exception as exc:
        diagnosis = diagnose_error(str(exc), source="benchmark")
        _warn(str(exc))
        console.print(f"Diagnosis: {diagnosis['code']}")
        console.print(f"Repair: {diagnosis['repair_suggestion']}")
        raise typer.Exit(1) from exc

    if result["status"] == "passed":
        _success(f"Benchmark completed: {result['benchmark_dir']}")
    else:
        _warn(f"Benchmark completed with review needed: {result['benchmark_dir']}")
        for item in result.get("diagnosis", []):
            console.print(f"  - {item['code']}: {item['repair_suggestion']}")


@app.command("benchmark-suite")
def benchmark_suite_cmd(
    suite: Path = typer.Option(..., "--suite", help="Benchmark suite JSON file."),
    project_prefix: str | None = typer.Option(None, "--project-prefix", help="Prefix for generated benchmark projects."),
) -> None:
    """Run a workflow-compliance benchmark suite."""
    try:
        result = run_benchmark_suite(suite, project_prefix=project_prefix)
    except Exception as exc:
        diagnosis = diagnose_error(str(exc), source="benchmark_suite")
        _warn(str(exc))
        console.print(f"Diagnosis: {diagnosis['code']}")
        console.print(f"Repair: {diagnosis['repair_suggestion']}")
        raise typer.Exit(1) from exc
    if result["status"] == "passed":
        _success(f"Benchmark suite completed: {result['suite_dir']}")
    else:
        _warn(f"Benchmark suite completed with review needed: {result['suite_dir']}")


@app.command("benchmark-index")
def benchmark_index_cmd(
    runs_dir: Path | None = typer.Option(
        None,
        "--runs-dir",
        help="Benchmark runs directory. Defaults to benchmarks/runs under the current directory.",
    ),
) -> None:
    """Rebuild benchmark_index.json and benchmark_index.md."""
    index = generate_benchmark_index(runs_dir)
    _success(f"Benchmark index rebuilt with {index['run_count']} runs.")
    console.print(f"JSON: {Path(index['runs_dir']) / 'benchmark_index.json'}")
    console.print(f"Markdown: {Path(index['runs_dir']) / 'benchmark_index.md'}")


@app.command("report")
def report_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate project-level reports/report.md."""
    project_dir = require_project(project_name)
    path = generate_report(project_dir)
    _success(f"Project report generated: {path}")


@app.command("handoff")
def handoff_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate multi-agent handoff files."""
    project_dir = require_project(project_name)
    files = generate_handoff(project_dir)
    _success("Handoff files generated.")
    for path in files:
        console.print(f"  - {path}")


@app.command("evidence-package")
def evidence_package_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/evidence_package.zip."),
) -> None:
    """Generate project-level evidence package JSON and Markdown."""
    project_dir = require_project(project_name)
    package = generate_evidence_package(project_dir, export_zip=export_zip)
    _success("Evidence package generated.")
    console.print(f"Schema: {package['schema_version']}")
    console.print(f"Freshness: {package['freshness']['status']}")
    console.print(f"Runs: {len(package['runs'])}")
    console.print(f"Experiments: {len(package['experiments'])}")
    console.print(f"JSON: {project_dir / 'reports' / 'evidence_package.json'}")
    console.print(f"Markdown: {project_dir / 'reports' / 'evidence_package.md'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'evidence_package.zip'}")


@app.command("review-site")
def review_site_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/review_site.zip."),
) -> None:
    """Generate a static human review site."""
    project_dir = require_project(project_name)
    site = generate_review_site(project_dir, export_zip=export_zip)
    table = Table(title=f"Review Site: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "open_action_count", "blocker_count", "top_command"]:
        table.add_row(key, str(site.get(key)))
    console.print(table)
    console.print(f"Index: {project_dir / 'reports' / 'review_site' / 'index.html'}")
    console.print(f"Manifest: {project_dir / 'reports' / 'review_site_manifest.json'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'review_site.zip'}")
    _success("Review site generated.")


@app.command("timeline")
def timeline_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a project timeline and decision log."""
    project_dir = require_project(project_name)
    timeline = generate_project_timeline(project_dir)
    table = Table(title=f"Project Timeline: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "event_count", "human_decision_count", "run_event_count", "latest_event_title"]:
        table.add_row(key, str(timeline.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'project_timeline.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PROJECT_TIMELINE.md'}")
    _success("Project timeline generated.")


@app.command("collaboration-pack")
def collaboration_pack_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export handoff/collaboration_pack.zip."),
) -> None:
    """Generate a role-based collaboration handoff pack."""
    project_dir = require_project(project_name)
    pack = generate_collaboration_pack(project_dir, export_zip=export_zip)
    table = Table(title=f"Collaboration Pack: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "role_count", "unresolved_decision_count", "next_safe_command_count", "top_command"]:
        table.add_row(key, str(pack.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'handoff' / 'collaboration_pack.json'}")
    console.print(f"Markdown: {project_dir / 'handoff' / 'COLLABORATION_PACK.md'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'handoff' / 'collaboration_pack.zip'}")
    _success("Collaboration pack generated.")


@app.command("refresh")
def refresh_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export downstream zip artifacts and workspace/refresh_run.zip."),
) -> None:
    """Refresh derived workflow and handoff artifacts without running experiments."""
    project_dir = require_project(project_name)
    run = generate_refresh_run(project_dir, export_zip=export_zip)
    table = Table(title=f"Refresh Run: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "step_count", "passed_step_count", "failed_step_count", "top_failed_step", "top_command"]:
        table.add_row(key, str(run.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'refresh_run.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REFRESH_RUN.md'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'workspace' / 'refresh_run.zip'}")
    if run["status"] != "complete":
        _warn("Refresh completed with failed steps.")
        raise typer.Exit(1)
    _success("Refresh run completed.")


@app.command("freshness")
def freshness_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Explain stale or missing derived artifacts with a dependency graph."""
    project_dir = require_project(project_name)
    graph = generate_artifact_freshness(project_dir)
    table = Table(title=f"Artifact Freshness: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "node_count", "stale_node_count", "top_stale_node", "top_stale_reason", "top_command"]:
        table.add_row(key, str(graph.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'artifact_freshness.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ARTIFACT_FRESHNESS.md'}")
    _success("Artifact freshness graph generated.")


@app.command("dashboard")
def dashboard_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/dashboard.zip."),
) -> None:
    """Generate a static project dashboard."""
    project_dir = require_project(project_name)
    dashboard = generate_dashboard(project_dir, export_zip=export_zip)
    table = Table(title=f"Dashboard: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "top_command"]:
        table.add_row(key, str(dashboard.get(key)))
    table.add_row("readiness_score", str(dashboard.get("readiness", {}).get("score")))
    table.add_row("stale_node_count", str(dashboard.get("freshness", {}).get("stale_node_count")))
    console.print(table)
    console.print(f"Index: {project_dir / 'reports' / 'dashboard' / 'index.html'}")
    console.print(f"Manifest: {project_dir / 'reports' / 'dashboard_manifest.json'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'dashboard.zip'}")
    _success("Dashboard generated.")


@app.command("readiness-review")
def readiness_review_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/readiness_review.zip."),
) -> None:
    """Generate a final readiness review report."""
    project_dir = require_project(project_name)
    review = generate_readiness_review(project_dir, export_zip=export_zip)
    table = Table(title="Readiness Review")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "top_command", "check_count", "passed_check_count", "blocker_count", "open_action_count"]:
        table.add_row(key, str(review.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'reports' / 'readiness_review.json'}")
    console.print(f"Markdown: {project_dir / 'reports' / 'READINESS_REVIEW.md'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'readiness_review.zip'}")
    _success("Readiness review generated.")


@app.command("validate-readiness-review")
def validate_readiness_review_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate readiness review freshness and consistency."""
    project_dir = require_project(project_name)
    validation = validate_readiness_review(project_dir)
    table = Table(title="Readiness Review Validation")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "valid", "issue_count", "warning_count", "top_command"]:
        table.add_row(key, str(validation.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'reports' / 'readiness_review_validation.json'}")
    console.print(f"Markdown: {project_dir / 'reports' / 'READINESS_REVIEW_VALIDATION.md'}")
    if validation["status"] == "passed":
        _success("Readiness review validation passed.")
    else:
        _warn("Readiness review validation failed.")


@app.command("review-action-plan")
def review_action_plan_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a role-based action plan from readiness review blockers."""
    project_dir = require_project(project_name)
    plan = generate_review_action_plan(project_dir)
    table = Table(title="Review Action Plan")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "action_count", "open_action_count", "top_role", "top_command"]:
        table.add_row(key, str(plan.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'review_action_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REVIEW_ACTION_PLAN.md'}")
    _success("Review action plan generated.")


@app.command("delivery-bundle")
def delivery_bundle_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/delivery_bundle.zip."),
) -> None:
    """Generate the final workflow delivery bundle."""
    project_dir = require_project(project_name)
    bundle = generate_delivery_bundle(project_dir, export_zip=export_zip)
    table = Table(title="Delivery Bundle")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "top_command", "required_file_count", "present_file_count", "missing_file_count"]:
        table.add_row(key, str(bundle.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'reports' / 'delivery_bundle.json'}")
    console.print(f"Markdown: {project_dir / 'reports' / 'DELIVERY_BUNDLE.md'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'delivery_bundle.zip'}")
    _success("Delivery bundle generated.")


@app.command("multi-agent-plan")
def multi_agent_plan_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a guarded multi-agent coordination plan."""
    project_dir = require_project(project_name)
    plan = generate_multi_agent_plan(project_dir)
    table = Table(title="Multi-Agent Plan")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "agent_count", "task_count", "open_task_count", "top_agent", "top_command"]:
        table.add_row(key, str(plan.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'multi_agent_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'MULTI_AGENT_PLAN.md'}")
    _success("Multi-agent plan generated.")


@app.command("validate-multi-agent-plan")
def validate_multi_agent_plan_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate the guarded multi-agent coordination plan."""
    project_dir = require_project(project_name)
    validation = validate_multi_agent_plan(project_dir)
    table = Table(title="Multi-Agent Plan Validation")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "valid", "issue_count", "warning_count", "top_command"]:
        table.add_row(key, str(validation.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'multi_agent_plan_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'MULTI_AGENT_PLAN_VALIDATION.md'}")
    if validation["valid"]:
        _success("Multi-agent plan validation passed.")
    else:
        _warn("Multi-agent plan validation failed.")


@app.command("agent-board")
def agent_board_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/agent_board.zip."),
) -> None:
    """Generate a static multi-agent task board."""
    project_dir = require_project(project_name)
    board = generate_agent_board(project_dir, export_zip=export_zip)
    table = Table(title="Agent Board")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "agent_count", "task_count", "open_task_count", "human_input_task_count", "top_command"]:
        table.add_row(key, str(board.get(key)))
    console.print(table)
    console.print(f"Index: {project_dir / 'reports' / 'agent_board' / 'index.html'}")
    console.print(f"Manifest: {project_dir / 'reports' / 'agent_board_manifest.json'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'agent_board.zip'}")
    _success("Agent board generated.")


@app.command("profile")
def profile_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a project reproduction profile."""
    project_dir = require_project(project_name)
    profile = generate_project_profile(project_dir)
    table = Table(title="Project Profile")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "top_command", "target_claim_count", "required_data_count", "required_experiment_count", "acceptance_dimension_count"]:
        table.add_row(key, str(profile.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'project_profile.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PROJECT_PROFILE.md'}")
    _success("Project profile generated.")


@app.command("acceptance")
def acceptance_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate project acceptance criteria."""
    project_dir = require_project(project_name)
    criteria = generate_acceptance_criteria(project_dir)
    table = Table(title="Acceptance Criteria")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "top_command", "criteria_count", "passed_count", "needs_work_count", "required_failed_count"]:
        table.add_row(key, str(criteria.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'acceptance_criteria.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ACCEPTANCE_CRITERIA.md'}")
    _success("Acceptance criteria generated.")


@app.command("status")
def status_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show current project workflow status."""
    status = get_status(project_name)
    table = Table(title=f"OpenRepro Status: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    rows = {
        "Project exists": status.exists,
        "Initialized": status.initialized,
        "Ingested": status.ingested,
        "Analyzed": status.analyzed,
        "Planned": status.planned,
        "Candidate reviews": status.candidate_review_count,
        "Experiment scaffolds": status.experiment_scaffold_count,
        "Experiment templates": status.experiment_template_counts,
        "Missing required inputs": status.experiment_missing_required_input_count,
        "Expected artifacts attention": status.experiment_expected_artifacts_attention_count,
        "Spec status counts": status.experiment_spec_status_counts,
        "Stale specs": status.experiment_spec_stale_count,
        "Invalid specs": status.experiment_spec_invalid_count,
        "Missing specs": status.experiment_spec_missing_count,
        "Registered data": status.data_registered_count,
        "Invalid data": status.data_invalid_count,
        "Missing data": status.data_missing_count,
        "Data hash mismatches": status.data_hash_mismatch_count,
        "Experiment runs": status.experiment_run_count,
        "Latest quality gate": status.latest_quality_gate_status,
        "Quality gate failed checks": status.latest_quality_gate_failed_check_count,
        "Latest experiment gate": status.latest_experiment_quality_gate_status,
        "Experiment gate failed checks": status.latest_experiment_quality_gate_failed_check_count,
        "Claim trace exists": status.claim_trace_exists,
        "Traced claims": status.claim_trace_claim_count,
        "Claim trace validation": status.claim_trace_validation_status,
        "Claim trace validation issues": status.claim_trace_validation_issue_count,
        "Readiness score": status.scorecard_overall_score,
        "Scorecard status": status.scorecard_status,
        "Open gaps": status.gaps_open_count,
        "Gap status": status.gaps_status,
        "Checkpoint status": status.checkpoint_status,
        "Next checkpoint": status.checkpoint_next_checkpoint,
        "Advance plan": status.advance_status,
        "Advance actions": status.advance_action_count,
        "Review board": status.review_board_status,
        "Review items": status.review_board_item_count,
        "Review decisions": status.review_decision_status,
        "Review unresolved": status.review_decision_unresolved_item_count,
        "Protocol": status.protocol_status,
        "Protocol blockers": status.protocol_blocking_criterion_count,
        "Protocol coverage": status.protocol_coverage_status,
        "Protocol uncovered": status.protocol_coverage_uncovered_count,
        "Protocol plan": status.protocol_plan_status,
        "Protocol actions": status.protocol_plan_action_count,
        "Protocol preflight": status.protocol_preflight_status,
        "Preflight blockers": status.protocol_preflight_blocking_count,
        "Evidence binder": status.claim_evidence_binder_status,
        "Incomplete claims": status.claim_evidence_binder_incomplete_claim_count,
        "Binder validation": status.claim_evidence_binder_validation_status,
        "Binder validation issues": status.claim_evidence_binder_validation_issue_count,
        "Claim signoffs": status.claim_signoff_status,
        "Signed claims": status.claim_signoff_signed_claim_count,
        "Open signoff claims": status.claim_signoff_open_claim_count,
        "Signoff validation": status.claim_signoff_validation_status,
        "Signoff validation issues": status.claim_signoff_validation_issue_count,
        "Claim evidence report": status.claim_evidence_report_status,
        "Claim report actions": status.claim_evidence_report_open_action_count,
        "Claim report validation": status.claim_evidence_report_validation_status,
        "Claim report validation issues": status.claim_evidence_report_validation_issue_count,
        "Reviewer packet": status.reviewer_packet_status,
        "Reviewer packet actions": status.reviewer_packet_open_action_count,
        "Review site": status.review_site_status,
        "Review site actions": status.review_site_open_action_count,
        "Review site blockers": status.review_site_blocker_count,
        "Project timeline": status.project_timeline_status,
        "Timeline events": status.project_timeline_event_count,
        "Timeline decisions": status.project_timeline_human_decision_count,
        "Collaboration pack": status.collaboration_pack_status,
        "Collab unresolved": status.collaboration_pack_unresolved_decision_count,
        "Collab commands": status.collaboration_pack_next_safe_command_count,
        "Refresh run": status.refresh_run_status,
        "Refresh steps": status.refresh_run_step_count,
        "Refresh failures": status.refresh_run_failed_step_count,
        "Artifact freshness": status.artifact_freshness_status,
        "Freshness stale nodes": status.artifact_freshness_stale_node_count,
        "Dashboard": status.dashboard_status,
        "Project profile": status.project_profile_status,
        "Profile target claims": status.project_profile_target_claim_count,
        "Profile experiments": status.project_profile_required_experiment_count,
        "Profile dimensions": status.project_profile_acceptance_dimension_count,
        "Acceptance": status.acceptance_criteria_status,
        "Acceptance criteria": status.acceptance_criteria_count,
        "Acceptance needs work": status.acceptance_criteria_needs_work_count,
        "Readiness review": status.readiness_review_status,
        "Readiness blockers": status.readiness_review_blocker_count,
        "Readiness validation": status.readiness_review_validation_status,
        "Readiness validation issues": status.readiness_review_validation_issue_count,
        "Review action plan": status.review_action_plan_status,
        "Review actions": status.review_action_plan_open_action_count,
        "Delivery bundle": status.delivery_bundle_status,
        "Delivery missing": status.delivery_bundle_missing_file_count,
        "Multi-agent plan": status.multi_agent_plan_status,
        "Multi-agent tasks": status.multi_agent_plan_open_task_count,
        "Multi-agent validation": status.multi_agent_plan_validation_status,
        "Multi-agent validation issues": status.multi_agent_plan_validation_issue_count,
        "Agent board": status.agent_board_status,
        "Agent board tasks": status.agent_board_open_task_count,
        "Latest run dir": status.latest_run_dir or "None",
        "Lineage exists": status.lineage_exists,
        "Report exists": status.report_exists,
        "Handoff complete": status.handoff_complete,
        "Evidence package exists": status.evidence_package_exists,
        "Evidence package status": status.evidence_package_status,
        "Evidence package stale": status.evidence_package_stale,
        "Next step": status.next_step,
    }
    for key, value in rows.items():
        table.add_row(key, str(value))
    console.print(table)


if __name__ == "__main__":
    app()
