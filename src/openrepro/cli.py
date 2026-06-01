"""Typer command-line interface for OpenRepro-Agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import analyze_project
from .artifact_manager import latest_run_dir, validate_all_run_manifests, validate_run_manifest
from .benchmark_runner import generate_benchmark_index, run_benchmark, run_benchmark_suite
from .config import configure_api_provider, provider_status
from .diagnostics import diagnose_error, diagnose_project, diagnose_validation_result
from .demo_runner import run_demo, run_sweep
from .document_loader import ingest_source
from .experiment_scaffold import scaffold_experiment
from .handoff_generator import generate_handoff
from .inspector import inspect_project
from .planner import generate_experiment_plan
from .project_manager import get_status, init_project, require_project
from .repair import create_repair_plan
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
) -> None:
    """Configure provider settings without storing secrets."""
    if enable_real_api and disable_real_api:
        _warn("--enable-real-api and --disable-real-api cannot be combined.")
        raise typer.Exit(1)
    project_dir = require_project(project_name)
    real_api_setting = True if enable_real_api else False if disable_real_api else None
    config = configure_api_provider(
        project_dir,
        provider=provider,
        model=model,
        enable_real_api=real_api_setting,
        api_key_env=api_key_env,
        endpoint=endpoint,
    )
    status = provider_status(project_dir)
    _success("Provider configuration updated.")
    table = Table(title=f"Provider: {project_name}")
    table.add_column("Item", style="bold")
    table.add_column("Value")
    for key in ["default_provider", "default_model", "enable_real_api", "api_key_env", "api_key_present", "ready_for_real_calls"]:
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


@app.command("scaffold-experiment")
def scaffold_experiment_cmd(
    project_name: str = typer.Argument(..., help="Project directory."),
    experiment_id: str | None = typer.Option(None, "--experiment-id", help="Experiment id. Defaults to a timestamp."),
    acknowledge_candidates: bool = typer.Option(
        False,
        "--acknowledge-candidates",
        help="Mark that candidate formulas/parameters are acknowledged for scaffold work.",
    ),
) -> None:
    """Create a human-gated experiment scaffold from candidate evidence."""
    project_dir = require_project(project_name)
    summary = scaffold_experiment(project_dir, experiment_id=experiment_id, acknowledge_candidates=acknowledge_candidates)
    _success(f"Experiment scaffold created: {summary['experiment_dir']}")
    console.print(f"Status: {summary['status']}")
    console.print(f"Next step: {summary['next_step']}")


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
        "Runs": summary["run_count"],
        "Latest manifest status": summary["latest_manifest_status"],
        "Benchmark runs": summary["benchmark_run_count"],
        "Diagnosis healthy": summary["diagnosis_healthy"],
        "Diagnosis issues": summary["diagnosis_issue_count"],
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
        "Latest run dir": status.latest_run_dir or "None",
        "Report exists": status.report_exists,
        "Handoff complete": status.handoff_complete,
        "Next step": status.next_step,
    }
    for key, value in rows.items():
        table.add_row(key, str(value))
    console.print(table)
