"""Typer command-line interface for OpenRepro-Agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import analyze_project
from .artifact_manager import latest_run_dir, validate_all_run_manifests, validate_run_manifest
from .benchmark_runner import generate_benchmark_index, run_benchmark
from .diagnostics import diagnose_error, diagnose_project, diagnose_validation_result
from .demo_runner import run_demo, run_sweep
from .document_loader import ingest_source
from .handoff_generator import generate_handoff
from .inspector import inspect_project
from .planner import generate_experiment_plan
from .project_manager import get_status, init_project, require_project
from .report_generator import generate_report

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
