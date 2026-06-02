"""Typer command-line interface for OpenRepro-Agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import analyze_project
from .approval import approve_candidates
from .artifact_manager import latest_run_dir, validate_all_run_manifests, validate_run_manifest
from .benchmark_runner import generate_benchmark_index, run_benchmark, run_benchmark_suite
from .candidate_review import list_candidates, review_candidates
from .config import configure_api_provider, provider_status
from .data_registry import register_data, validate_data_index
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
from .handoff_generator import generate_handoff
from .inspector import inspect_project
from .lineage import generate_run_lineage
from .planner import generate_experiment_plan
from .project_manager import get_status, init_project, require_project
from .quality_gate import evaluate_all_quality_gates, evaluate_run_quality
from .repair import apply_repair_actions, create_repair_plan, preview_repair_actions
from .report_generator import generate_report
from .run_compare import compare_runs

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
