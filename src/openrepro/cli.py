"""Typer command-line interface for OpenRepro-Agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import analyze_project
from .artifact_manager import latest_run_dir, validate_run_manifest
from .demo_runner import run_demo, run_sweep
from .document_loader import ingest_source
from .handoff_generator import generate_handoff
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
) -> None:
    """Validate a run manifest and required artifacts."""
    project_dir = require_project(project_name)
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
    raise typer.Exit(1)


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
