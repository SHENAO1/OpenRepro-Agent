"""Typer command-line interface for OpenRepro-Agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import analyze_project
from .demo_runner import run_demo
from .document_loader import ingest_source
from .handoff_generator import generate_handoff
from .planner import generate_experiment_plan
from .project_manager import get_status, init_project, require_project
from .report_generator import generate_report

app = typer.Typer(
    name="openrepro",
    help="OpenRepro-Agent: minimal paper reproduction workflow CLI.",
    no_args_is_help=True,
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
    source: Path = typer.Option(..., "--source", "-s", help="Markdown/txt source file; PDF is placeholder only."),
) -> None:
    """Ingest Markdown/txt research notes or copy a PDF placeholder."""
    project_dir = require_project(project_name)
    record = ingest_source(project_dir, source)
    if record.status == "placeholder":
        _warn(record.note)
    else:
        _success(f"Ingested {record.source_name}")
    console.print(f"Copied path: {record.copied_path}")
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
