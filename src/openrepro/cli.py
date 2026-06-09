"""Typer command-line interface for OpenRepro-Agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .acceptance_criteria import generate_acceptance_criteria
from .advance import generate_advance_plan
from .agent_adapter import generate_agent_adapter, validate_agent_adapter
from .agent_board import generate_agent_board
from .agent_dispatch import generate_agent_dispatch
from .agent_exec_plan import generate_agent_exec_plan
from .agent_sandbox import run_agent_sandbox
from .analyzer import analyze_project
from .approval import approve_candidates
from .asset_build import asset_build_summary, materialize_assets, plan_asset_build
from .asset_catalog import generate_asset_catalog, generate_asset_catalog_graph, get_catalog_asset, list_catalog_assets
from .artifact_cache import add_artifact_cache, gc_artifact_cache, list_artifact_cache, verify_artifact_cache
from .artifact_cache_remote import configure_cache_remote, list_cache_remotes, pull_artifact_cache, push_artifact_cache, restore_artifact_cache
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
from .ci_integration import ci_summary, init_ci_config, validate_ci_config
from .collaboration_pack import generate_collaboration_pack
from .config import configure_api_provider, provider_status
from .data_expectations import init_data_expectations, run_data_expectations
from .data_registry import register_data, validate_data_index
from .data_profile import generate_data_profile
from .dashboard import generate_dashboard
from .delivery_bundle import generate_delivery_bundle
from .diagnostics import diagnose_error, diagnose_project, diagnose_validation_result
from .demo_runner import run_demo, run_sweep
from .document_loader import ingest_source
from .doctor import run_doctor
from .evidence_explorer import generate_evidence_explorer
from .evidence_query import query_evidence
from .evidence_package import generate_evidence_package
from .experiment_compare import compare_experiments, rerun_experiment
from .experiment_evaluation import define_evaluation_suite, generate_experiment_leaderboard, run_evaluation_suite
from .experiment_scaffold import scaffold_experiment
from .experiment_tracking import compare_tracked_experiments, generate_experiment_tracking, list_tracked_experiments, tracked_experiment
from .experiment_inputs import set_experiment_input, validate_experiment_inputs
from .experiment_runner import run_experiment
from .experiment_spec import validate_experiment_spec
from .experiment_templates import list_experiment_templates
from .freshness import generate_artifact_freshness
from .gaps import generate_reproduction_gaps
from .github_pr_summary import generate_github_pr_summary, github_pr_summary_status
from .golden_path import run_golden_path
from .handoff_generator import generate_handoff
from .inspector import inspect_project
from .integrations import export_integrations, integrations_summary, run_integration_execution
from .lineage import generate_run_lineage
from .local_ui import generate_local_ui, local_ui_summary
from .multi_agent_plan import generate_multi_agent_plan
from .multi_agent_plan_validation import validate_multi_agent_plan
from .openrepro_bench_lite import list_bench_lite_tasks, run_openrepro_bench_lite
from .paper_lineage import generate_paper_lineage
from .pipeline_spec import export_pipeline_spec, plan_pipeline, validate_pipeline_spec
from .plugin_registry import build_plugin_registry, plugin_registry_summary, register_plugin, validate_plugin_registry
from .planner import generate_experiment_plan
from .protocol_coverage import generate_protocol_coverage
from .protocol_plan import generate_protocol_plan
from .protocol_preflight import generate_protocol_preflight
from .project_profile import generate_project_profile
from .promotion import plan_promotion, promotion_summary, record_promotion
from .project_manager import get_status, init_project, require_project
from .quality_gate import evaluate_all_quality_gates, evaluate_run_quality
from .readiness_review import generate_readiness_review
from .readiness_review_validation import validate_readiness_review
from .refresh import generate_refresh_run
from .repair import apply_repair_actions, create_repair_plan, preview_repair_actions
from .report_generator import generate_report
from .repro_lock import generate_repro_lock, validate_repro_lock
from .reproduction_protocol import generate_reproduction_protocol
from .review_board import generate_review_board
from .review_action_plan import generate_review_action_plan
from .review_decisions import ALLOWED_REVIEW_DECISIONS, record_review_decision
from .review_site import generate_review_site
from .reviewer_packet import generate_reviewer_packet
from .run_compare import compare_runs
from .run_index import compare_indexed_runs, generate_run_index, indexed_run
from .scorecard import generate_reproduction_scorecard
from .security_policy import init_security_policy, run_security_audit, security_summary
from .timeline import generate_project_timeline
from .workflow_preset import generate_workflow_preset
from .workflow_executor import execute_workflow
from .workflow_registry import explain_workflow_step, generate_workflow_state, run_workflow

app = typer.Typer(
    name="openrepro",
    help="OpenRepro-Agent: minimal paper reproduction workflow CLI.",
    no_args_is_help=True,
    invoke_without_command=True,
)
workflow_app = typer.Typer(help="Inspect and run the registered OpenRepro workflow DAG.", no_args_is_help=True)
app.add_typer(workflow_app, name="workflow")
agent_app = typer.Typer(help="Run approved safe agent tasks in a local sandbox.", no_args_is_help=True)
app.add_typer(agent_app, name="agent")
ci_app = typer.Typer(help="Generate and validate local GitHub Actions CI scaffolding.", no_args_is_help=True)
app.add_typer(ci_app, name="ci")
serve_app = typer.Typer(help="Build static local project UI artifacts.", no_args_is_help=True)
app.add_typer(serve_app, name="serve")
runs_app = typer.Typer(help="Index, inspect, and compare run outputs.", no_args_is_help=True)
app.add_typer(runs_app, name="runs")
catalog_app = typer.Typer(help="Build and inspect the OpenRepro asset catalog.", no_args_is_help=True)
app.add_typer(catalog_app, name="catalog")
assets_app = typer.Typer(help="Plan and materialize safe asset builds.", no_args_is_help=True)
app.add_typer(assets_app, name="assets")
data_expectations_app = typer.Typer(help="Initialize and run lightweight data expectations.", no_args_is_help=True)
app.add_typer(data_expectations_app, name="data-expectations")
pipeline_app = typer.Typer(help="Export, plan, and validate declarative OpenRepro pipeline specs.", no_args_is_help=True)
app.add_typer(pipeline_app, name="pipeline")
experiments_app = typer.Typer(help="Track and compare experiment-level run evidence.", no_args_is_help=True)
app.add_typer(experiments_app, name="experiments")
eval_app = typer.Typer(help="Define and run experiment metric evaluations.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")
plugins_app = typer.Typer(help="Register and validate declarative project plugins.", no_args_is_help=True)
app.add_typer(plugins_app, name="plugins")
promote_app = typer.Typer(help="Plan and record promotion gate decisions.", no_args_is_help=True)
app.add_typer(promote_app, name="promote")
github_app = typer.Typer(help="Generate local GitHub review artifacts.", no_args_is_help=True)
app.add_typer(github_app, name="github")
security_app = typer.Typer(help="Initialize and run local security audits.", no_args_is_help=True)
app.add_typer(security_app, name="security")
integrations_app = typer.Typer(help="Export optional integration adapter artifacts.", no_args_is_help=True)
app.add_typer(integrations_app, name="integrations")
cache_app = typer.Typer(help="Manage the local content-addressed artifact cache.", no_args_is_help=True)
app.add_typer(cache_app, name="cache")
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


@app.command("start")
def start_cmd(
    project_name: str = typer.Argument(..., help="Project directory name for the golden path run."),
    source: Path | None = typer.Option(None, "--source", "-s", help="Markdown/txt/PDF source file. Defaults to the packaged random-search notes."),
    template: str = typer.Option("random-search-toy", "--template", help="Experiment template for the starter scaffold."),
    experiment_id: str = typer.Option("random_search_demo", "--experiment-id", help="Experiment id for the starter scaffold."),
    reviewer: str = typer.Option("openrepro-start", "--reviewer", help="Reviewer name recorded in demo candidate approval artifacts."),
    run: bool = typer.Option(True, "--run/--no-run", help="Run the generated starter experiment and quality gate."),
) -> None:
    """Run the smallest useful paper-to-evidence workflow."""
    result = run_golden_path(
        project_name,
        source=source,
        template=template,
        experiment_id=experiment_id,
        reviewer=reviewer,
        run=run,
    )
    table = Table(title="OpenRepro Golden Path")
    table.add_column("Step", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    for step in result["steps"]:
        table.add_row(
            str(step.get("step")),
            str(step.get("status")),
            str(step.get("run_dir") or step.get("path") or step.get("experiment_dir") or ""),
        )
    console.print(table)
    _success(f"Golden path status: {result['status']}")
    console.print(f"Project: {result['project_dir']}")
    if result.get("run_dir"):
        console.print(f"Run: {result['run_dir']}")
    console.print(f"Summary: {Path(result['project_dir']) / 'workspace' / 'GOLDEN_PATH.md'}")


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


@experiments_app.command("track")
def experiments_track_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/experiment_tracking.zip."),
) -> None:
    """Generate experiment-level tracking artifacts."""
    project_dir = require_project(project_name)
    tracking = generate_experiment_tracking(project_dir, export_zip=export_zip)
    table = Table(title=f"Experiment Tracking: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "experiment_count", "run_count"]:
        table.add_row(key, str(tracking.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'experiment_tracking.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EXPERIMENT_TRACKING.md'}")
    console.print(f"Index: {project_dir / 'reports' / 'experiments' / 'index.html'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'experiment_tracking.zip'}")
    _success("Experiment tracking generated.")


@experiments_app.command("list")
def experiments_list_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """List tracked experiments."""
    project_dir = require_project(project_name)
    result = list_tracked_experiments(project_dir)
    table = Table(title=f"Experiments: {project_name}")
    table.add_column("Experiment")
    table.add_column("Status")
    table.add_column("Runs")
    table.add_column("Latest run")
    table.add_column("Gate")
    for experiment in result["experiments"]:
        table.add_row(
            str(experiment.get("experiment_id")),
            str(experiment.get("status")),
            str(experiment.get("run_count")),
            str(experiment.get("latest_run_id")),
            str(experiment.get("latest_quality_gate_status")),
        )
    console.print(table)


@experiments_app.command("show")
def experiments_show_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str = typer.Argument(..., help="Experiment id."),
) -> None:
    """Show one tracked experiment."""
    project_dir = require_project(project_name)
    try:
        experiment = tracked_experiment(project_dir, experiment_id)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Experiment: {experiment_id}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "experiment_id",
        "status",
        "run_count",
        "latest_run_id",
        "latest_quality_gate_status",
        "quality_gate_status_counts",
        "metric_keys",
        "latest_metrics",
        "spec_present",
        "spec_sha256",
    ]:
        table.add_row(key, str(experiment.get(key)))
    console.print(table)


@experiments_app.command("compare")
def experiments_compare_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    left: str = typer.Option(..., "--left", help="Left experiment id."),
    right: str = typer.Option(..., "--right", help="Right experiment id."),
) -> None:
    """Compare latest tracked metrics for two experiments."""
    project_dir = require_project(project_name)
    try:
        comparison = compare_tracked_experiments(project_dir, left, right)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Experiment Tracking Comparison: {project_name}")
    table.add_column("Metric")
    table.add_column("Left")
    table.add_column("Right")
    table.add_column("Delta")
    table.add_column("Equal")
    for item in comparison["metric_deltas"]:
        table.add_row(str(item["metric"]), str(item["left"]), str(item["right"]), str(item["delta"]), str(item["equal"]))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'experiment_tracking_comparison.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EXPERIMENT_TRACKING_COMPARISON.md'}")
    _success("Experiment tracking comparison written.")


@experiments_app.command("leaderboard")
def experiments_leaderboard_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    suite: str = typer.Option("default", "--suite", help="Evaluation suite name."),
    metric: str | None = typer.Option(None, "--metric", help="Metric to rank. Defaults to the first suite criterion."),
) -> None:
    """Generate an experiment leaderboard from latest tracked metrics."""
    project_dir = require_project(project_name)
    try:
        leaderboard = generate_experiment_leaderboard(project_dir, suite=suite, metric=metric)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Experiment Leaderboard: {project_name}")
    table.add_column("Rank")
    table.add_column("Experiment")
    table.add_column("Run")
    table.add_column("Metric")
    table.add_column("Value")
    for row in leaderboard["experiments"]:
        table.add_row(str(row.get("rank")), str(row.get("experiment_id")), str(row.get("latest_run_id")), str(row.get("metric")), str(row.get("value")))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'experiment_leaderboard.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EXPERIMENT_LEADERBOARD.md'}")
    _success("Experiment leaderboard generated.")


@eval_app.command("define")
def eval_define_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    suite: str = typer.Option("default", "--suite", help="Evaluation suite name."),
    metric: str = typer.Option(..., "--metric", help="Metric key to evaluate."),
    threshold: float = typer.Option(..., "--threshold", help="Metric threshold."),
    operator: str = typer.Option(">=", "--operator", help="Comparison operator: >=, <=, >, <, ==, !="),
    higher_is_better: bool = typer.Option(True, "--higher-is-better/--lower-is-better", help="Leaderboard sort direction."),
    baseline_experiment: str | None = typer.Option(None, "--baseline-experiment", help="Optional baseline experiment id."),
) -> None:
    """Define or update an experiment evaluation suite."""
    project_dir = require_project(project_name)
    try:
        registry = define_evaluation_suite(
            project_dir,
            suite=suite,
            metric=metric,
            threshold=threshold,
            operator=operator,
            higher_is_better=higher_is_better,
            baseline_experiment=baseline_experiment,
        )
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Evaluation Registry: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "suite_count"]:
        table.add_row(key, str(registry.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'evaluation_registry.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EVALUATION_REGISTRY.md'}")
    _success("Evaluation suite defined.")


@eval_app.command("run")
def eval_run_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    suite: str = typer.Option("default", "--suite", help="Evaluation suite name."),
) -> None:
    """Run an experiment evaluation suite."""
    project_dir = require_project(project_name)
    try:
        result = run_evaluation_suite(project_dir, suite=suite)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Evaluation Results: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["suite", "status", "experiment_count", "passed_experiment_count", "failed_experiment_count", "missing_metric_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'evaluation_results.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EVALUATION_RESULTS.md'}")
    console.print(f"Leaderboard: {project_dir / 'workspace' / 'EXPERIMENT_LEADERBOARD.md'}")
    if result["status"] == "failed":
        raise typer.Exit(1)
    _success("Evaluation suite passed.")


@plugins_app.command("register")
def plugins_register_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    plugin_id: str = typer.Option(..., "--id", help="Plugin id."),
    kind: str = typer.Option("command", "--kind", help="Plugin kind: command, provider, reporter, or evaluator."),
    entrypoint: str = typer.Option(..., "--entrypoint", help="Command, provider label, or supervised entrypoint."),
    description: str = typer.Option("", "--description", help="Short plugin description."),
    capability: list[str] | None = typer.Option(None, "--capability", help="Capability label. Repeat to add more."),
    run_mode: str = typer.Option("declaration", "--run-mode", help="declaration, external_supervised, or safe_command."),
    disabled: bool = typer.Option(False, "--disabled", help="Register the plugin as disabled."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Update an existing plugin id."),
) -> None:
    """Register a declarative project plugin."""
    project_dir = require_project(project_name)
    try:
        registry = register_plugin(
            project_dir,
            plugin_id=plugin_id,
            kind=kind,
            entrypoint=entrypoint,
            description=description,
            capabilities=capability or [],
            run_mode=run_mode,
            enabled=not disabled,
            overwrite=overwrite,
        )
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Plugin Registry: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "plugin_count", "enabled_plugin_count", "kind_counts", "run_mode_counts"]:
        table.add_row(key, str(registry.get(key)))
    console.print(table)
    console.print(f"Config: {project_dir / 'openrepro.plugins.yaml'}")
    console.print(f"JSON: {project_dir / 'workspace' / 'plugin_registry.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PLUGIN_REGISTRY.md'}")
    console.print(f"Validation: {project_dir / 'workspace' / 'PLUGIN_VALIDATION.md'}")
    _success("Plugin registered.")


@plugins_app.command("list")
def plugins_list_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Build and list declarative project plugins."""
    project_dir = require_project(project_name)
    registry = build_plugin_registry(project_dir)
    table = Table(title=f"Plugins: {project_name}")
    table.add_column("Plugin")
    table.add_column("Kind")
    table.add_column("Enabled")
    table.add_column("Run mode")
    table.add_column("Entrypoint")
    for plugin in registry["plugins"]:
        table.add_row(str(plugin.get("plugin_id")), str(plugin.get("kind")), str(plugin.get("enabled")), str(plugin.get("run_mode")), str(plugin.get("entrypoint")))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'plugin_registry.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PLUGIN_REGISTRY.md'}")


@plugins_app.command("validate")
def plugins_validate_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate declarative project plugins."""
    project_dir = require_project(project_name)
    result = validate_plugin_registry(project_dir)
    table = Table(title=f"Plugin Validation: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "valid", "plugin_count", "error_count", "warning_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'plugin_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PLUGIN_VALIDATION.md'}")
    if not result["valid"]:
        raise typer.Exit(1)
    _success("Plugin registry is valid.")


@plugins_app.command("summary")
def plugins_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show the existing plugin registry summary."""
    project_dir = require_project(project_name)
    summary = plugin_registry_summary(project_dir)
    table = Table(title=f"Plugin Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "plugin_count", "enabled_plugin_count", "validation_status", "validation_error_count", "config_path", "sha256"]:
        table.add_row(key, str(summary.get(key)))
    console.print(table)


@promote_app.command("plan")
def promote_plan_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    target: str = typer.Option(..., "--target", help="Promotion target: experiment, report, or delivery."),
    candidate_id: str = typer.Option(..., "--candidate-id", help="Candidate id to promote."),
    to_state: str = typer.Option("validated", "--to", help="Target state: validated, accepted, released, or rejected."),
) -> None:
    """Evaluate promotion gates without recording a decision."""
    project_dir = require_project(project_name)
    try:
        plan = plan_promotion(project_dir, target=target, candidate_id=candidate_id, to_state=to_state)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Promotion Plan: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "target", "candidate_id", "from_state", "to_state", "gate_count", "failed_gate_count", "top_blocker", "top_command"]:
        table.add_row(key, str(plan.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'promotion_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PROMOTION_PLAN.md'}")
    if plan["status"] == "ready":
        _success("Promotion gates passed.")
    else:
        _warn("Promotion gates are blocked.")


@promote_app.command("record")
def promote_record_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    target: str = typer.Option(..., "--target", help="Promotion target: experiment, report, or delivery."),
    candidate_id: str = typer.Option(..., "--candidate-id", help="Candidate id to promote."),
    to_state: str = typer.Option("validated", "--to", help="Target state: validated, accepted, released, or rejected."),
    reviewer: str = typer.Option("", "--reviewer", help="Reviewer or release owner."),
    note: str = typer.Option("", "--note", help="Promotion note."),
    confirm: bool = typer.Option(False, "--confirm", help="Record the promotion when required gates pass."),
) -> None:
    """Dry-run or record a promotion decision."""
    project_dir = require_project(project_name)
    try:
        result = record_promotion(
            project_dir,
            target=target,
            candidate_id=candidate_id,
            to_state=to_state,
            reviewer=reviewer,
            note=note,
            confirm=confirm,
        )
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Promotion Record: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "target", "candidate_id", "to_state", "confirmed", "recorded", "plan_status", "top_blocker"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'promotion_record.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PROMOTION_RECORD.md'}")
    console.print(f"Registry: {project_dir / 'workspace' / 'promotion_registry.json'}")
    if result["status"] == "dry_run":
        _warn("Promotion record was a dry run. Pass --confirm to write the registry.")
    elif result["status"] == "recorded":
        _success("Promotion recorded.")
    else:
        _warn("Promotion record is blocked.")


@promote_app.command("summary")
def promote_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show promotion registry and latest plan state."""
    project_dir = require_project(project_name)
    summary = promotion_summary(project_dir)
    table = Table(title=f"Promotion Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "promotion_count", "latest_target", "latest_candidate_id", "latest_state", "latest_plan_status", "last_record_status", "sha256"]:
        table.add_row(key, str(summary.get(key)))
    console.print(table)


@github_app.command("pr-summary")
def github_pr_summary_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    pr_number: int | None = typer.Option(None, "--pr-number", help="GitHub pull request number for display only."),
    base_ref: str | None = typer.Option(None, "--base", help="Optional local git base ref for diff stats."),
    head_ref: str | None = typer.Option(None, "--head", help="Optional local git head ref for diff stats."),
    repo_dir: Path | None = typer.Option(None, "--repo-dir", help="Repository directory for local git metadata. Defaults to current directory."),
) -> None:
    """Generate a local GitHub PR comment summary."""
    project_dir = require_project(project_name)
    result = generate_github_pr_summary(
        project_dir,
        pr_number=pr_number,
        base_ref=base_ref,
        head_ref=head_ref,
        repo_dir=repo_dir,
    )
    table = Table(title=f"GitHub PR Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "pr_number", "check_count", "failed_check_count", "warning_count"]:
        table.add_row(key, str(result.get(key)))
    table.add_row("branch", str(result.get("git", {}).get("branch")))
    table.add_row("commit", str(result.get("git", {}).get("commit")))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'github_pr_summary.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'GITHUB_PR_SUMMARY.md'}")
    console.print(f"PR comment: {project_dir / 'reports' / 'pr_comment.md'}")
    if result["status"] == "ready":
        _success("GitHub PR summary generated.")
    else:
        _warn("GitHub PR summary has blocked checks.")


@github_app.command("summary")
def github_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show the existing local GitHub PR summary status."""
    project_dir = require_project(project_name)
    summary = github_pr_summary_status(project_dir)
    table = Table(title=f"GitHub PR Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "pr_number", "check_count", "failed_check_count", "warning_count", "comment_path", "sha256"]:
        table.add_row(key, str(summary.get(key)))
    console.print(table)


@security_app.command("init")
def security_init_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing security policy."),
) -> None:
    """Initialize the default local security policy."""
    project_dir = require_project(project_name)
    policy = init_security_policy(project_dir, overwrite=overwrite)
    table = Table(title=f"Security Policy: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["schema_version", "scan_roots", "exclude_dirs", "max_file_bytes"]:
        table.add_row(key, str(policy.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'security_policy.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'SECURITY_POLICY.md'}")
    _success("Security policy initialized.")


@security_app.command("audit")
def security_audit_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    strict: bool = typer.Option(False, "--strict", help="Treat medium findings as failing."),
) -> None:
    """Run the local security audit."""
    project_dir = require_project(project_name)
    result = run_security_audit(project_dir, strict=strict)
    table = Table(title=f"Security Audit: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "valid", "strict", "finding_count", "critical_count", "high_count", "medium_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'security_audit.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'SECURITY_AUDIT.md'}")
    if not result["valid"]:
        _warn("Security audit failed.")
        raise typer.Exit(1)
    _success("Security audit passed.")


@security_app.command("summary")
def security_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show the current security audit summary."""
    project_dir = require_project(project_name)
    summary = security_summary(project_dir)
    table = Table(title=f"Security Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "valid", "finding_count", "critical_count", "high_count", "medium_count", "sha256"]:
        table.add_row(key, str(summary.get(key)))
    console.print(table)


@integrations_app.command("export")
def integrations_export_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    target: list[str] | None = typer.Option(None, "--target", help="Integration target. Repeat for mlflow, aim, dvc, or hydra."),
) -> None:
    """Export declaration-only adapter artifacts for external tools."""
    project_dir = require_project(project_name)
    result = export_integrations(project_dir, targets=target)
    table = Table(title=f"Integration Exports: {project_name}")
    table.add_column("Target", style="bold")
    table.add_column("Status")
    table.add_column("Path")
    for artifact in result["artifacts"]:
        table.add_row(str(artifact["target"]), str(artifact["status"]), str(artifact["path"]))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'integrations.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'INTEGRATIONS.md'}")
    _success("Integration adapter artifacts exported.")


@integrations_app.command("summary")
def integrations_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show the existing integration export summary."""
    project_dir = require_project(project_name)
    summary = integrations_summary(project_dir)
    table = Table(title=f"Integration Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "target_count", "targets", "path", "markdown_path", "execution_present", "execution_status", "execution_path"]:
        table.add_row(key, str(summary.get(key)))
    console.print(table)


@integrations_app.command("run")
def integrations_run_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    target: list[str] | None = typer.Option(None, "--target", help="Integration target. Repeat for mlflow, aim, dvc, or hydra."),
    confirm: bool = typer.Option(False, "--confirm", help="Actually run adapter commands when optional dependencies are available."),
    timeout_seconds: int = typer.Option(120, "--timeout-seconds", help="Maximum seconds for each confirmed adapter command."),
) -> None:
    """Plan and optionally execute supervised integration adapter commands."""
    project_dir = require_project(project_name)
    result = run_integration_execution(project_dir, targets=target, confirm=confirm, timeout_seconds=timeout_seconds)
    table = Table(title=f"Integration Execution: {project_name}")
    table.add_column("Target", style="bold")
    table.add_column("Status")
    table.add_column("Dependency")
    table.add_column("Command")
    for item in result["executions"]:
        dependency = item.get("dependency") or {}
        table.add_row(
            str(item.get("target")),
            str(item.get("status")),
            str(dependency.get("name")),
            " ".join(str(part) for part in item.get("command", [])),
        )
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'integration_execution.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'INTEGRATION_EXECUTION.md'}")
    if result["status"] == "needs_review":
        _warn("Integration execution completed with failures.")
        raise typer.Exit(1)
    if result["status"] == "planned":
        _success("Integration execution plan written.")
    elif result["status"] == "skipped_missing_dependency":
        _warn("Integration execution skipped because optional dependencies are missing.")
    else:
        _success("Integration execution completed.")


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


@app.command("data-profile")
def data_profile_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    max_rows: int = typer.Option(5000, "--max-rows", help="Maximum rows sampled per data source."),
) -> None:
    """Profile registered data columns and lightweight schema warnings."""
    project_dir = require_project(project_name)
    profile = generate_data_profile(project_dir, max_rows=max_rows)
    table = Table(title=f"Data Profile: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "source_count", "profiled_source_count", "column_count", "warning_count", "error_count"]:
        table.add_row(key, str(profile.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'data_profile.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'DATA_PROFILE.md'}")
    if profile["status"] == "failed":
        raise typer.Exit(1)
    _success("Data profile generated.")


@data_expectations_app.command("init")
def data_expectations_init_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing expectation suite."),
    max_rows: int = typer.Option(5000, "--max-rows", help="Maximum rows sampled while deriving defaults."),
) -> None:
    """Initialize a lightweight data expectation suite from the current data profile."""
    project_dir = require_project(project_name)
    suite = init_data_expectations(project_dir, overwrite=overwrite, max_rows=max_rows)
    table = Table(title=f"Data Expectations: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "expectation_count"]:
        table.add_row(key, str(suite.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'data_expectations.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'DATA_EXPECTATIONS.md'}")
    _success("Data expectations initialized.")


@data_expectations_app.command("run")
def data_expectations_run_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    max_rows: int = typer.Option(100000, "--max-rows", help="Maximum rows validated per data source."),
) -> None:
    """Run lightweight data expectations."""
    project_dir = require_project(project_name)
    result = run_data_expectations(project_dir, max_rows=max_rows)
    table = Table(title=f"Data Expectation Results: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "expectation_count", "passed_count", "failed_count", "top_failed_expectation"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'data_expectation_results.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'DATA_EXPECTATION_RESULTS.md'}")
    if result["status"] == "failed":
        raise typer.Exit(1)
    _success("Data expectations passed.")


@app.command("lock")
def lock_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate the project reproducibility lockfile."""
    project_dir = require_project(project_name)
    lock = generate_repro_lock(project_dir)
    table = Table(title=f"Repro Lock: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    rows = {
        "status": lock["status"],
        "registered_data": lock["data"]["registered_count"],
        "data_invalid": lock["data"]["invalid_count"],
        "experiments": lock["experiment_count"],
        "python": lock["environment"]["python"]["version"],
    }
    for key, value in rows.items():
        table.add_row(key, str(value))
    console.print(table)
    console.print(f"Lockfile: {project_dir / 'openrepro.lock.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REPRO_LOCK.md'}")
    if lock["status"] != "locked":
        _warn("Repro lock generated with invalid data state.")
        raise typer.Exit(1)
    _success("Repro lock generated.")


@app.command("validate-lock")
def validate_lock_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    strict_dependencies: bool = typer.Option(False, "--strict-dependencies", help="Treat Python/dependency drift as errors."),
) -> None:
    """Validate the project reproducibility lockfile."""
    project_dir = require_project(project_name)
    result = validate_repro_lock(project_dir, strict_dependencies=strict_dependencies)
    table = Table(title=f"Repro Lock Validation: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["valid", "strict_dependencies", "error_count", "warning_count", "errors", "warnings"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'repro_lock_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'REPRO_LOCK_VALIDATION.md'}")
    if not result["valid"]:
        raise typer.Exit(1)
    _success("Repro lock is valid.")


@app.command("scaffold-experiment")
def scaffold_experiment_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str | None = typer.Option(None, "--experiment-id", help="Experiment id. Defaults to a timestamp."),
    template: str = typer.Option(
        "basic",
        "--template",
        help="Experiment template name.",
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
        "Agent dispatch": summary["agent_dispatch_status"],
        "Agent dispatch tasks": summary["agent_dispatch_open_task_count"],
        "Agent exec plan": summary["agent_exec_plan_status"],
        "Agent exec safe steps": summary["agent_exec_plan_safe_step_count"],
        "Paper lineage": summary["paper_lineage_status"],
        "Paper lineage nodes": summary["paper_lineage_node_count"],
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


@runs_app.command("index")
def runs_index_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/run_explorer.zip."),
) -> None:
    """Generate the run index and static run explorer."""
    project_dir = require_project(project_name)
    index = generate_run_index(project_dir, export_zip=export_zip)
    table = Table(title=f"Run Index: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "run_count", "valid_manifest_count", "quality_gate_passed_count"]:
        table.add_row(key, str(index.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'run_index.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'RUN_INDEX.md'}")
    console.print(f"Explorer: {project_dir / 'reports' / 'run_explorer' / 'index.html'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'run_explorer.zip'}")
    _success("Run index generated.")


@runs_app.command("list")
def runs_list_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """List indexed run outputs."""
    project_dir = require_project(project_name)
    index = generate_run_index(project_dir)
    table = Table(title=f"Runs: {project_name}")
    table.add_column("Run")
    table.add_column("Command")
    table.add_column("Experiment")
    table.add_column("Manifest")
    table.add_column("Gate")
    table.add_column("Metrics")
    for run in index["runs"]:
        metrics = ", ".join(f"{key}={value}" for key, value in list(run.get("metrics", {}).items())[:4])
        table.add_row(
            str(run.get("run_id")),
            str(run.get("command")),
            str(run.get("experiment_id")),
            str(run.get("manifest_valid")),
            str(run.get("quality_gate_status")),
            metrics,
        )
    console.print(table)


@runs_app.command("show")
def runs_show_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    run_id: str = typer.Argument(..., help="Run directory name."),
) -> None:
    """Show one indexed run record."""
    project_dir = require_project(project_name)
    try:
        run = indexed_run(project_dir, run_id)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Run: {run_id}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "run_id",
        "command",
        "created_at",
        "experiment_id",
        "template",
        "execution_status",
        "exit_code",
        "manifest_valid",
        "quality_gate_status",
        "quality_gate_failed_check_count",
        "metric_count",
        "run_dir",
    ]:
        table.add_row(key, str(run.get(key)))
    console.print(table)
    if run.get("metrics"):
        metric_table = Table(title="Metrics")
        metric_table.add_column("Metric")
        metric_table.add_column("Value")
        for key, value in run["metrics"].items():
            metric_table.add_row(str(key), str(value))
        console.print(metric_table)


@runs_app.command("compare")
def runs_compare_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    left_run: str = typer.Option(..., "--left", help="Left run id."),
    right_run: str = typer.Option(..., "--right", help="Right run id."),
) -> None:
    """Compare two indexed run records."""
    project_dir = require_project(project_name)
    try:
        comparison = compare_indexed_runs(project_dir, left_run_id=left_run, right_run_id=right_run)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Indexed Run Comparison: {project_name}")
    table.add_column("Metric")
    table.add_column("Left")
    table.add_column("Right")
    table.add_column("Delta")
    table.add_column("Equal")
    for item in comparison["metric_deltas"]:
        table.add_row(str(item["metric"]), str(item["left"]), str(item["right"]), str(item["delta"]), str(item["equal"]))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'run_index_comparison.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'RUN_INDEX_COMPARISON.md'}")
    _success("Indexed run comparison written.")


@catalog_app.command("build")
def catalog_build_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Build the unified project asset catalog."""
    project_dir = require_project(project_name)
    catalog = generate_asset_catalog(project_dir)
    table = Table(title=f"Asset Catalog: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "asset_count", "kind_counts"]:
        table.add_row(key, str(catalog.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'asset_catalog.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ASSET_CATALOG.md'}")
    console.print(f"Graph: {project_dir / 'workspace' / 'ASSET_CATALOG_GRAPH.md'}")
    _success("Asset catalog generated.")


@catalog_app.command("list")
def catalog_list_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    kind: str = typer.Option("all", "--kind", help="Asset kind filter, or all."),
) -> None:
    """List assets from the project asset catalog."""
    project_dir = require_project(project_name)
    result = list_catalog_assets(project_dir, kind=kind)
    table = Table(title=f"Assets: {project_name}")
    table.add_column("Asset")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Path")
    for asset in result["assets"]:
        table.add_row(str(asset.get("asset_id")), str(asset.get("kind")), str(asset.get("status")), str(asset.get("path")))
    console.print(table)


@catalog_app.command("show")
def catalog_show_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    asset_id: str = typer.Argument(..., help="Asset id to show."),
) -> None:
    """Show one asset catalog record."""
    project_dir = require_project(project_name)
    try:
        asset = get_catalog_asset(project_dir, asset_id)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Asset: {asset_id}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["asset_id", "kind", "label", "path", "present", "status", "size_bytes", "sha256", "metadata", "relations"]:
        table.add_row(key, str(asset.get(key)))
    console.print(table)


@catalog_app.command("graph")
def catalog_graph_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Regenerate the asset catalog graph markdown."""
    project_dir = require_project(project_name)
    graph = generate_asset_catalog_graph(project_dir)
    console.print(f"Graph: {graph['path']}")
    _success("Asset catalog graph generated.")


@assets_app.command("plan")
def assets_plan_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    target: str = typer.Option("all", "--target", help="Step id, stage, output, or all."),
    refresh_catalog: bool = typer.Option(False, "--refresh-catalog", help="Regenerate the asset catalog before planning."),
) -> None:
    """Plan safe incremental asset materialization."""
    project_dir = require_project(project_name)
    plan = plan_asset_build(project_dir, target=target, refresh_catalog=refresh_catalog)
    table = Table(title=f"Asset Build Plan: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "target", "step_count", "materialize_step_count", "blocked_step_count", "top_step_id", "top_command"]:
        table.add_row(key, str(plan.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'asset_build_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ASSET_BUILD_PLAN.md'}")
    _success("Asset build plan generated.")


@assets_app.command("materialize")
def assets_materialize_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    target: str = typer.Option("all", "--target", help="Step id, stage, output, or all."),
    step_id: str | None = typer.Option(None, "--step", help="Exact workflow step id to materialize."),
    confirm: bool = typer.Option(False, "--confirm", help="Execute safe materialization candidates through the workflow executor."),
    max_steps: int | None = typer.Option(None, "--max-steps", min=0, help="Maximum candidate steps to materialize."),
    export_zip: bool = typer.Option(False, "--zip", help="Pass zip export through to safe workflow actions."),
) -> None:
    """Dry-run or execute safe asset materialization candidates."""
    project_dir = require_project(project_name)
    result = materialize_assets(
        project_dir,
        target=target,
        step_id=step_id,
        confirm=confirm,
        max_steps=max_steps,
        export_zip=export_zip,
    )
    table = Table(title=f"Asset Materialization: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "target", "confirmed", "selected_step_count", "executed_step_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'asset_materialization.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ASSET_MATERIALIZATION.md'}")
    if result["status"] == "dry_run":
        _warn("Asset materialization was a dry run. Pass --confirm to execute safe candidates.")
    elif result["status"] == "complete":
        _success("Asset materialization completed.")
    elif result["status"] == "up_to_date":
        _success("Assets are up to date.")
    else:
        _warn("Asset materialization is blocked or failed.")


@assets_app.command("summary")
def assets_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show the current asset build plan summary."""
    project_dir = require_project(project_name)
    summary = asset_build_summary(project_dir)
    table = Table(title=f"Asset Build Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "target", "step_count", "materialize_step_count", "blocked_step_count", "top_step_id", "last_materialization_status", "sha256"]:
        table.add_row(key, str(summary.get(key)))
    console.print(table)


@cache_app.command("add")
def cache_add_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    path: Path | None = typer.Option(None, "--path", help="Specific file or directory to add. Defaults to standard project artifacts."),
) -> None:
    """Add project artifacts to the local content-addressed cache."""
    project_dir = require_project(project_name)
    try:
        cache = add_artifact_cache(project_dir, target=path)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Artifact Cache: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "cached_file_count", "blob_count", "total_size_bytes"]:
        table.add_row(key, str(cache.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'artifact_cache.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ARTIFACT_CACHE.md'}")
    _success("Artifact cache updated.")


@cache_app.command("list")
def cache_list_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """List local artifact cache entries."""
    project_dir = require_project(project_name)
    cache = list_artifact_cache(project_dir)
    table = Table(title=f"Cached Artifacts: {project_name}")
    table.add_column("Path")
    table.add_column("Size")
    table.add_column("SHA-256")
    table.add_column("Cache path")
    for entry in cache["entries"]:
        table.add_row(str(entry.get("path")), str(entry.get("size_bytes")), str(entry.get("sha256")), str(entry.get("cache_path")))
    console.print(table)
    console.print(f"Cached files: {cache['cached_file_count']}")


@cache_app.command("verify")
def cache_verify_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Verify cached blobs against their recorded hashes."""
    project_dir = require_project(project_name)
    result = verify_artifact_cache(project_dir)
    table = Table(title=f"Artifact Cache Validation: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "valid", "checked_file_count", "missing_blob_count", "corrupt_blob_count", "source_changed_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'artifact_cache_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ARTIFACT_CACHE_VALIDATION.md'}")
    if not result["valid"]:
        raise typer.Exit(1)
    _success("Artifact cache validation passed.")


@cache_app.command("gc")
def cache_gc_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Remove unreferenced local cache blobs."""
    project_dir = require_project(project_name)
    result = gc_artifact_cache(project_dir)
    table = Table(title=f"Artifact Cache GC: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "removed_blob_count", "retained_blob_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    _success("Artifact cache garbage collection completed.")


@cache_app.command("remote-add")
def cache_remote_add_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    name: str = typer.Option(..., "--name", help="Remote name."),
    uri: str = typer.Option(..., "--uri", help="Remote URI or local path."),
    remote_type: str = typer.Option("local", "--type", help="Remote type: local, s3, or ssh."),
    make_default: bool = typer.Option(False, "--default", help="Make this the default cache remote."),
) -> None:
    """Add or update an artifact cache remote."""
    project_dir = require_project(project_name)
    try:
        result = configure_cache_remote(project_dir, name=name, uri=uri, remote_type=remote_type, make_default=make_default)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Artifact Cache Remotes: {project_name}")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("URI")
    table.add_column("Default")
    table.add_column("Supported")
    for remote in result["remotes"]:
        table.add_row(str(remote.get("name")), str(remote.get("type")), str(remote.get("uri")), str(remote.get("default")), str(remote.get("supported")))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'artifact_cache_remotes.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'ARTIFACT_CACHE_REMOTES.md'}")
    _success("Artifact cache remote configured.")


@cache_app.command("remote-list")
def cache_remote_list_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """List artifact cache remotes."""
    project_dir = require_project(project_name)
    result = list_cache_remotes(project_dir)
    table = Table(title=f"Artifact Cache Remotes: {project_name}")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("URI")
    table.add_column("Default")
    table.add_column("Supported")
    for remote in result["remotes"]:
        table.add_row(str(remote.get("name")), str(remote.get("type")), str(remote.get("uri")), str(remote.get("default")), str(remote.get("supported")))
    console.print(table)


@cache_app.command("push")
def cache_push_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    remote: str | None = typer.Option(None, "--remote", help="Remote name. Defaults to the configured default remote."),
) -> None:
    """Push local artifact cache blobs to a configured remote."""
    project_dir = require_project(project_name)
    try:
        result = push_artifact_cache(project_dir, remote=remote)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _print_cache_transfer(project_dir, result, "Artifact cache pushed.")


@cache_app.command("pull")
def cache_pull_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    remote: str | None = typer.Option(None, "--remote", help="Remote name. Defaults to the configured default remote."),
) -> None:
    """Pull artifact cache blobs from a configured remote."""
    project_dir = require_project(project_name)
    try:
        result = pull_artifact_cache(project_dir, remote=remote)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _print_cache_transfer(project_dir, result, "Artifact cache pulled.")


@cache_app.command("restore")
def cache_restore_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    remote: str | None = typer.Option(None, "--remote", help="Remote name to pull before restore planning."),
    confirm: bool = typer.Option(False, "--confirm", help="Actually restore missing files from cached blobs."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Restore changed files as well as missing files."),
) -> None:
    """Plan or restore files from local or remote artifact cache blobs."""
    project_dir = require_project(project_name)
    try:
        result = restore_artifact_cache(project_dir, remote=remote, confirm=confirm, overwrite=overwrite)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Cache Restore: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "confirmed", "overwrite", "action_count", "restore_action_count", "restored_count", "skipped_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'cache_restore_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CACHE_RESTORE_PLAN.md'}")
    _success("Cache restore completed." if confirm else "Cache restore plan generated.")


def _print_cache_transfer(project_dir: Path, result: dict, success_message: str) -> None:
    table = Table(title=f"Artifact Cache Remote: {project_dir.name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "cached_file_count", "copied_blob_count", "skipped_blob_count", "remote_manifest_path"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"Remote: {result.get('remote', {}).get('name')}")
    _success(success_message)


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


@app.command("bench-lite")
def bench_lite_cmd(
    project_prefix: str = typer.Option("openrepro_bench_lite", "--project-prefix", help="Prefix for generated benchmark projects."),
    bench_dir: Path | None = typer.Option(None, "--bench-dir", help="Directory for the materialized built-in benchmark pack."),
    task_id: list[str] | None = typer.Option(None, "--task-id", help="Built-in task id to run. Repeat to run a subset."),
    list_tasks: bool = typer.Option(False, "--list-tasks", help="List built-in OpenRepro-Bench Lite tasks and exit."),
    materialize_only: bool = typer.Option(False, "--materialize-only", help="Write the built-in suite and tasks without running them."),
) -> None:
    """Run the built-in OpenRepro-Bench Lite workflow-compliance suite."""
    if list_tasks:
        table = Table(title="OpenRepro-Bench Lite Tasks")
        table.add_column("Task", style="bold")
        table.add_column("Title")
        table.add_column("Difficulty")
        table.add_column("Focus")
        for task in list_bench_lite_tasks():
            table.add_row(str(task["task_id"]), str(task["paper_title"]), str(task["difficulty"]), str(task["focus"]))
        console.print(table)
        console.print("Tasks: " + ", ".join(str(task["task_id"]) for task in list_bench_lite_tasks()))
        return
    try:
        result = run_openrepro_bench_lite(
            project_prefix=project_prefix,
            bench_dir=bench_dir,
            task_ids=task_id,
            materialize_only=materialize_only,
        )
    except Exception as exc:
        diagnosis = diagnose_error(str(exc), source="openrepro_bench_lite")
        _warn(str(exc))
        console.print(f"Diagnosis: {diagnosis['code']}")
        console.print(f"Repair: {diagnosis['repair_suggestion']}")
        raise typer.Exit(1) from exc

    table = Table(title="OpenRepro-Bench Lite")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "task_count", "tasks_passed", "project_prefix", "suite_dir"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"Suite: {result['suite_path']}")
    console.print(f"JSON: {result['summary_path']}")
    console.print(f"Markdown: {result['markdown_path']}")
    if result["status"] == "passed":
        _success("OpenRepro-Bench Lite completed.")
    elif materialize_only:
        _success("OpenRepro-Bench Lite materialized.")
    else:
        _warn("OpenRepro-Bench Lite completed with review needed.")


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


@app.command("evidence-explorer")
def evidence_explorer_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/evidence_explorer.zip."),
) -> None:
    """Generate a static paper evidence explorer."""
    project_dir = require_project(project_name)
    explorer = generate_evidence_explorer(project_dir, export_zip=export_zip)
    table = Table(title=f"Evidence Explorer: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "claim_count", "data_count", "experiment_count", "metric_count", "run_count"]:
        table.add_row(key, str(explorer.get(key)))
    console.print(table)
    console.print(f"Index: {project_dir / 'reports' / 'evidence_explorer' / 'index.html'}")
    console.print(f"Manifest: {project_dir / 'reports' / 'evidence_explorer_manifest.json'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'evidence_explorer.zip'}")
    _success("Evidence explorer generated.")


@app.command("evidence-query")
def evidence_query_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    kind: str = typer.Option("all", "--kind", help="Filter kind: all, claim, node, run, data, or artifact."),
    text: str | None = typer.Option(None, "--text", help="Case-insensitive text to search across evidence fields."),
    limit: int = typer.Option(50, "--limit", help="Maximum result count, capped at 200."),
) -> None:
    """Search paper evidence explorer records and write query artifacts."""
    project_dir = require_project(project_name)
    try:
        query = query_evidence(project_dir, kind=kind, text=text, limit=limit)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Evidence Query: {project_name}")
    table.add_column("Kind")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Source")
    for result in query["results"]:
        table.add_row(
            str(result.get("kind", "")),
            str(result.get("id", "")),
            str(result.get("title", ""))[:90],
            str(result.get("status", "")),
            str(result.get("source", ""))[:90],
        )
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'evidence_query.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'EVIDENCE_QUERY.md'}")
    _success(f"Evidence query generated with {query['result_count']} result(s).")


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


@pipeline_app.command("export")
def pipeline_export_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    preset: str = typer.Option("delivery", "--preset", help="Preset: data, review, delivery, agent, or full."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite openrepro.pipeline.yaml if it already exists."),
) -> None:
    """Export openrepro.pipeline.yaml from the registered workflow DAG."""
    project_dir = require_project(project_name)
    try:
        spec = export_pipeline_spec(project_dir, preset=preset, overwrite=overwrite)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Pipeline Spec: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["schema_version", "preset"]:
        table.add_row(key, str(spec.get(key)))
    table.add_row("step_count", str(len(spec.get("steps", []))))
    console.print(table)
    console.print(f"YAML: {project_dir / 'openrepro.pipeline.yaml'}")
    _success("Pipeline spec exported.")


@pipeline_app.command("plan")
def pipeline_plan_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Plan the current project against openrepro.pipeline.yaml."""
    project_dir = require_project(project_name)
    plan = plan_pipeline(project_dir)
    table = Table(title=f"Pipeline Plan: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "step_count", "complete_step_count", "pending_step_count", "blocked_step_count", "runnable_step_count", "top_command"]:
        table.add_row(key, str(plan.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'pipeline_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PIPELINE_PLAN.md'}")
    _success("Pipeline plan generated.")


@pipeline_app.command("validate")
def pipeline_validate_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate openrepro.pipeline.yaml against the registered workflow DAG."""
    project_dir = require_project(project_name)
    validation = validate_pipeline_spec(project_dir)
    table = Table(title=f"Pipeline Validation: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["valid", "step_count", "error_count", "warning_count", "errors", "warnings"]:
        table.add_row(key, str(validation.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'pipeline_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PIPELINE_VALIDATION.md'}")
    if not validation["valid"]:
        raise typer.Exit(1)
    _success("Pipeline spec is valid.")


@workflow_app.command("status")
def workflow_status_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Write and show the registered workflow DAG state."""
    project_dir = require_project(project_name)
    state = generate_workflow_state(project_dir)
    table = Table(title=f"Workflow State: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "status",
        "step_count",
        "complete_step_count",
        "pending_step_count",
        "blocked_step_count",
        "stale_step_count",
        "runnable_step_count",
        "top_command",
    ]:
        table.add_row(key, str(state.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'workflow_state.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'WORKFLOW_STATE.md'}")
    _success("Workflow state generated.")


@workflow_app.command("explain")
def workflow_explain_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    step_id: str = typer.Argument(..., help="Workflow step id to explain."),
) -> None:
    """Explain one registered workflow step and its current dependency state."""
    project_dir = require_project(project_name)
    explanation = explain_workflow_step(project_dir, step_id)
    step = explanation["step"]
    table = Table(title=f"Workflow Step: {step_id}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["title", "stage", "status", "safe", "execution", "command"]:
        table.add_row(key, str(step.get(key)))
    table.add_row("dependencies", ", ".join(step.get("dependencies", [])) or "None")
    table.add_row("missing dependencies", ", ".join(step.get("missing_dependencies", [])) or "None")
    table.add_row("missing outputs", ", ".join(step.get("missing_outputs", [])) or "None")
    console.print(table)


@workflow_app.command("preset")
def workflow_preset_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    preset: str = typer.Option("delivery", "--preset", help="Preset: data, review, delivery, agent, or full."),
    runnable_only: bool = typer.Option(False, "--runnable-only", help="Only include currently runnable safe steps."),
) -> None:
    """Write a goal-oriented workflow preset plan."""
    project_dir = require_project(project_name)
    try:
        plan = generate_workflow_preset(project_dir, preset=preset, runnable_only=runnable_only)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title=f"Workflow Preset: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "preset",
        "status",
        "selected_step_count",
        "complete_step_count",
        "pending_step_count",
        "blocked_step_count",
        "stale_step_count",
        "runnable_step_count",
        "top_command",
    ]:
        table.add_row(key, str(plan.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'workflow_preset.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'WORKFLOW_PRESET.md'}")
    _success("Workflow preset generated.")


@workflow_app.command("run")
def workflow_run_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    step_id: str | None = typer.Option(None, "--step", help="Specific workflow step id to run or dry-run."),
    confirm: bool = typer.Option(False, "--confirm", help="Execute instead of writing a dry-run plan."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export zip artifacts for steps that support it."),
) -> None:
    """Run or dry-run one safe registered workflow step."""
    project_dir = require_project(project_name)
    result = run_workflow(project_dir, step_id=step_id, confirm=confirm, resume=False, export_zip=export_zip)
    _print_workflow_run(project_dir, project_name, result)
    if confirm and result["status"] in {"blocked", "failed"}:
        raise typer.Exit(1)


@workflow_app.command("resume")
def workflow_resume_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    confirm: bool = typer.Option(False, "--confirm", help="Execute instead of writing a dry-run plan."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export zip artifacts for steps that support it."),
) -> None:
    """Run or dry-run all currently runnable safe workflow steps."""
    project_dir = require_project(project_name)
    result = run_workflow(project_dir, confirm=confirm, resume=True, export_zip=export_zip)
    _print_workflow_run(project_dir, project_name, result)
    if confirm and result["status"] in {"blocked", "failed"}:
        raise typer.Exit(1)


@workflow_app.command("execute")
def workflow_execute_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    preset: str = typer.Option("delivery", "--preset", help="Preset: data, review, delivery, agent, or full."),
    step_id: str | None = typer.Option(None, "--step", help="Specific workflow step id to execute or dry-run."),
    confirm: bool = typer.Option(False, "--confirm", help="Execute instead of writing a dry-run execution session."),
    retry_count: int = typer.Option(0, "--retry", min=0, help="Retries per failed safe step."),
    max_steps: int | None = typer.Option(None, "--max-steps", min=0, help="Limit selected steps for this execution."),
    continue_on_error: bool = typer.Option(False, "--continue-on-error", help="Continue after blocked or failed steps."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export zip artifacts for steps that support it."),
) -> None:
    """Execute a preset or step with durable events, logs, and output hashes."""
    project_dir = require_project(project_name)
    try:
        result = execute_workflow(
            project_dir,
            preset=preset,
            step_id=step_id,
            confirm=confirm,
            retry_count=retry_count,
            max_steps=max_steps,
            continue_on_error=continue_on_error,
            export_zip=export_zip,
        )
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    _print_workflow_execution(project_dir, project_name, result)
    if confirm and result["status"] in {"blocked", "failed"}:
        raise typer.Exit(1)


def _print_workflow_run(project_dir: Path, project_name: str, result: dict) -> None:
    table = Table(title=f"Workflow Run: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "mode",
        "confirmed",
        "status",
        "selected_step_count",
        "passed_step_count",
        "blocked_step_count",
        "failed_step_count",
        "top_blocked_step",
        "top_failed_step",
    ]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'workflow_run.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'WORKFLOW_RUN.md'}")
    if result["status"] == "dry_run":
        _warn("Workflow run was a dry run. Pass --confirm to execute safe derived steps.")
    elif result["status"] == "complete":
        _success("Workflow run completed.")
    elif result["status"] == "blocked":
        _warn("Workflow run is blocked.")
    else:
        _warn("Workflow run failed.")


def _print_workflow_execution(project_dir: Path, project_name: str, result: dict) -> None:
    table = Table(title=f"Workflow Execution: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "execution_id",
        "preset",
        "step_id",
        "confirmed",
        "status",
        "selected_step_count",
        "passed_step_count",
        "blocked_step_count",
        "failed_step_count",
        "dry_run_step_count",
        "skipped_step_count",
        "top_blocked_step",
        "top_failed_step",
    ]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'workflow_execution.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'WORKFLOW_EXECUTION.md'}")
    console.print(f"Events: {project_dir / 'workspace' / 'workflow_events.jsonl'}")
    console.print(f"Logs: {project_dir / result['logs_dir']}")
    if result["status"] == "dry_run":
        _warn("Workflow execution was a dry run. Pass --confirm to execute safe derived steps.")
    elif result["status"] == "complete":
        _success("Workflow execution completed.")
    elif result["status"] == "blocked":
        _warn("Workflow execution is blocked.")
    else:
        _warn("Workflow execution failed.")


@ci_app.command("init")
def ci_init_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    test_command: str = typer.Option("python -m pytest -q", "--test-command", help="Command for the CI test step."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing workflow file."),
) -> None:
    """Generate a local GitHub Actions workflow scaffold."""
    project_dir = require_project(project_name)
    result = init_ci_config(project_dir, test_command=test_command, overwrite=overwrite)
    table = Table(title=f"CI Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "workflow_relative_path", "test_command", "sha256"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"Workflow: {project_dir / '.github' / 'workflows' / 'openrepro-ci.yml'}")
    console.print(f"JSON: {project_dir / 'workspace' / 'ci_summary.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CI_SUMMARY.md'}")
    _success("CI workflow scaffold generated." if result["status"] == "written" else "CI workflow scaffold preserved.")


@ci_app.command("validate")
def ci_validate_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate the local GitHub Actions workflow scaffold."""
    project_dir = require_project(project_name)
    result = validate_ci_config(project_dir)
    table = Table(title=f"CI Validation: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "valid", "check_count", "failed_check_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'ci_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'CI_VALIDATION.md'}")
    if not result["valid"]:
        raise typer.Exit(1)
    _success("CI workflow scaffold is valid.")


@ci_app.command("summary")
def ci_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show the local CI scaffold summary."""
    project_dir = require_project(project_name)
    result = ci_summary(project_dir)
    table = Table(title=f"CI Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "workflow_path", "test_command", "sha256"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)


@serve_app.command("build")
def serve_build_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    export_zip: bool = typer.Option(False, "--zip", help="Also export reports/local_ui.zip."),
) -> None:
    """Build a static local UI for project artifact navigation."""
    project_dir = require_project(project_name)
    result = generate_local_ui(project_dir, export_zip=export_zip)
    table = Table(title=f"Local UI: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["status", "panel_count", "present_panel_count", "missing_panel_count", "artifact_link_count", "missing_artifact_link_count"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"Index: {project_dir / 'reports' / 'local_ui' / 'index.html'}")
    console.print(f"Manifest: {project_dir / 'reports' / 'local_ui_manifest.json'}")
    console.print(f"Summary: {project_dir / 'workspace' / 'local_ui_summary.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'LOCAL_UI_SUMMARY.md'}")
    if export_zip:
        console.print(f"Zip: {project_dir / 'reports' / 'local_ui.zip'}")
    _success("Local UI generated.")


@serve_app.command("summary")
def serve_summary_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Show the existing static local UI summary."""
    project_dir = require_project(project_name)
    result = local_ui_summary(project_dir)
    table = Table(title=f"Local UI Summary: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["present", "status", "path", "panel_count", "present_panel_count", "missing_panel_count", "missing_artifact_link_count", "sha256"]:
        table.add_row(key, str(result.get(key)))
    console.print(table)


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


@agent_app.command("run")
def agent_run_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    role: str | None = typer.Option(None, "--role", help="Agent role id to run, such as maintainer."),
    confirm: bool = typer.Option(False, "--confirm", help="Execute instead of dry-running sandbox steps."),
    approve: bool = typer.Option(False, "--approve", help="Required with --confirm to approve sandbox execution."),
    max_steps: int = typer.Option(1, "--max-steps", min=0, help="Maximum safe steps to run."),
    continue_on_error: bool = typer.Option(False, "--continue-on-error", help="Continue after blocked or failed sandbox steps."),
) -> None:
    """Run or dry-run approved safe agent tasks in a local sandbox."""
    project_dir = require_project(project_name)
    result = run_agent_sandbox(
        project_dir,
        role=role,
        confirm=confirm,
        approved=approve,
        max_steps=max_steps,
        continue_on_error=continue_on_error,
    )
    table = Table(title=f"Agent Sandbox: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in [
        "status",
        "role",
        "confirmed",
        "approved",
        "selected_step_count",
        "passed_step_count",
        "blocked_step_count",
        "failed_step_count",
        "dry_run_step_count",
    ]:
        table.add_row(key, str(result.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'agent_sandbox_run.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'AGENT_SANDBOX_RUN.md'}")
    console.print(f"Trajectory: {project_dir / 'workspace' / 'agent_sandbox_trajectory.jsonl'}")
    console.print(f"Logs: {project_dir / result['logs_dir']}")
    if result["status"] == "dry_run":
        _warn("Agent sandbox was a dry run. Pass --confirm --approve to execute safe steps.")
    elif result["status"] == "complete":
        _success("Agent sandbox completed.")
    elif result["status"] == "blocked":
        _warn("Agent sandbox is blocked.")
        raise typer.Exit(1)
    else:
        _warn("Agent sandbox failed.")
        raise typer.Exit(1)


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


@app.command("agent-dispatch")
def agent_dispatch_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate per-agent task dispatch files."""
    project_dir = require_project(project_name)
    dispatch = generate_agent_dispatch(project_dir)
    table = Table(title="Agent Dispatch Pack")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "agent_count", "task_count", "open_task_count", "human_input_task_count", "top_command"]:
        table.add_row(key, str(dispatch.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'agent_dispatch.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'AGENT_DISPATCH.md'}")
    console.print(f"Agent tasks: {project_dir / 'workspace' / 'agents'}")
    _success("Agent dispatch pack generated.")


@app.command("agent-exec-plan")
def agent_exec_plan_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    dry_run: bool = typer.Option(True, "--dry-run", help="Generate a dry-run execution plan only."),
) -> None:
    """Generate a safe dry-run execution plan for derived agent tasks."""
    project_dir = require_project(project_name)
    try:
        plan = generate_agent_exec_plan(project_dir, dry_run=dry_run)
    except Exception as exc:
        _warn(str(exc))
        raise typer.Exit(1) from exc
    table = Table(title="Agent Execution Plan")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "dry_run", "task_count", "safe_step_count", "blocked_task_count", "top_command"]:
        table.add_row(key, str(plan.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'agent_exec_plan.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'AGENT_EXEC_PLAN.md'}")
    _success("Agent execution dry-run plan generated.")


@app.command("agent-adapter")
def agent_adapter_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    runner: str = typer.Option("external-supervised", "--runner", help="External supervised runner label."),
    max_steps: int = typer.Option(20, "--max-steps", help="Maximum safe steps to include."),
) -> None:
    """Generate a supervised external-agent adapter spec without executing tasks."""
    project_dir = require_project(project_name)
    adapter = generate_agent_adapter(project_dir, runner=runner, max_steps=max_steps)
    table = Table(title="Agent Adapter")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "runner", "adapter_step_count", "blocked_task_count", "max_steps"]:
        table.add_row(key, str(adapter.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'agent_adapter.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'AGENT_ADAPTER.md'}")
    console.print(f"Trajectory: {project_dir / 'workspace' / 'agent_trajectory.jsonl'}")
    _success("Agent adapter generated.")


@app.command("validate-agent-adapter")
def validate_agent_adapter_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Validate the supervised external-agent adapter spec."""
    project_dir = require_project(project_name)
    validation = validate_agent_adapter(project_dir)
    table = Table(title="Agent Adapter Validation")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["valid", "error_count", "warning_count", "errors", "warnings"]:
        table.add_row(key, str(validation.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'agent_adapter_validation.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'AGENT_ADAPTER_VALIDATION.md'}")
    if not validation["valid"]:
        raise typer.Exit(1)
    _success("Agent adapter is valid.")


@app.command("paper-lineage")
def paper_lineage_cmd(project_name: str = typer.Argument(..., help="Project directory.")) -> None:
    """Generate a paper-level claim/method/data/experiment/metric lineage graph."""
    project_dir = require_project(project_name)
    lineage = generate_paper_lineage(project_dir)
    table = Table(title="Paper Lineage")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["status", "node_count", "edge_count", "claim_count", "method_count", "data_count", "experiment_count", "metric_count", "top_command"]:
        table.add_row(key, str(lineage.get(key)))
    console.print(table)
    console.print(f"JSON: {project_dir / 'workspace' / 'paper_lineage.json'}")
    console.print(f"Markdown: {project_dir / 'workspace' / 'PAPER_LINEAGE.md'}")
    _success("Paper lineage generated.")


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
        "Agent dispatch": status.agent_dispatch_status,
        "Agent dispatch tasks": status.agent_dispatch_open_task_count,
        "Agent exec plan": status.agent_exec_plan_status,
        "Agent exec safe steps": status.agent_exec_plan_safe_step_count,
        "Paper lineage": status.paper_lineage_status,
        "Paper lineage nodes": status.paper_lineage_node_count,
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
