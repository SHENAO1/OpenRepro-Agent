"""One-command golden path for a small reproducible-paper demo."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

from .analyzer import analyze_project
from .approval import approve_candidates
from .document_loader import ingest_source
from .experiment_inputs import validate_experiment_inputs
from .experiment_runner import run_experiment
from .experiment_scaffold import scaffold_experiment
from .experiment_spec import validate_experiment_spec
from .handoff_generator import generate_handoff
from .planner import generate_experiment_plan
from .project_manager import init_project
from .quality_gate import evaluate_run_quality
from .report_generator import generate_report
from .utils import iso_now, safe_write_text, write_json

GOLDEN_PATH_SCHEMA_VERSION = "1.51.0"
DEFAULT_EXAMPLE_NAME = "random_search_notes.md"


def run_golden_path(
    project_name: str,
    *,
    source: Path | None = None,
    base_dir: Path | None = None,
    template: str = "random-search-toy",
    experiment_id: str = "random_search_demo",
    reviewer: str = "openrepro-start",
    run: bool = True,
    report: bool = True,
    handoff: bool = True,
) -> dict[str, Any]:
    """Run the smallest useful paper-to-evidence workflow."""
    init_result = init_project(project_name, base_dir=base_dir)
    project_dir = init_result.project_dir
    steps: list[dict[str, Any]] = [
        {
            "step": "init",
            "status": "created" if init_result.created else "existing",
            "message": init_result.message,
            "path": str(project_dir),
        }
    ]

    if source is None:
        resource = files("openrepro").joinpath("examples", DEFAULT_EXAMPLE_NAME)
        with as_file(resource) as default_source:
            source_record = ingest_source(project_dir, default_source)
    else:
        source_record = ingest_source(project_dir, source)
    steps.append(
        {
            "step": "ingest",
            "status": source_record.status,
            "source_name": source_record.source_name,
            "copied_path": str(source_record.copied_path),
        }
    )

    analysis = analyze_project(project_dir)
    steps.append(
        {
            "step": "analyze",
            "status": "generated",
            "formula_candidate_count": analysis.get("formula_candidate_count", 0),
            "parameter_candidate_count": analysis.get("parameter_candidate_count", 0),
        }
    )

    plan_path = generate_experiment_plan(project_dir)
    steps.append({"step": "plan", "status": "generated", "path": str(plan_path)})

    approval = approve_candidates(
        project_dir,
        approve_all=True,
        reviewer=reviewer,
        verification_note=(
            "Golden path demo approval for scaffold readiness only. "
            "This does not verify scientific correctness or claim full paper reproduction."
        ),
    )
    steps.append(
        {
            "step": "approve-candidates",
            "status": approval["status"],
            "formula_candidate_count": approval["formula_candidate_count"],
            "parameter_candidate_count": approval["parameter_candidate_count"],
        }
    )

    scaffold = scaffold_experiment(project_dir, experiment_id=experiment_id, template=template)
    steps.append(
        {
            "step": "scaffold-experiment",
            "status": scaffold["status"],
            "experiment_id": scaffold["experiment_id"],
            "template": scaffold["template"],
            "experiment_dir": scaffold["experiment_dir"],
        }
    )

    input_validation = validate_experiment_inputs(project_dir, experiment_id)
    spec_validation = validate_experiment_spec(project_dir, experiment_id)
    input_valid = input_validation.get("status") == "complete"
    spec_valid = bool(spec_validation.get("valid"))
    steps.append(
        {
            "step": "validate-experiment",
            "status": "valid" if input_valid and spec_valid else "needs_attention",
            "input_valid": input_valid,
            "spec_valid": spec_valid,
        }
    )

    run_metadata: dict[str, Any] | None = None
    quality_gate: dict[str, Any] | None = None
    if run:
        run_metadata = run_experiment(project_dir, experiment_id, confirm=True)
        steps.append(
            {
                "step": "run-experiment",
                "status": run_metadata["status"],
                "run_dir": run_metadata["run_dir"],
                "template": run_metadata["template"],
            }
        )
        quality_gate = evaluate_run_quality(project_dir, Path(run_metadata["run_dir"]))
        steps.append(
            {
                "step": "quality-gate",
                "status": quality_gate["status"],
                "run_id": quality_gate["run_id"],
                "failed_check_count": quality_gate["failed_check_count"],
            }
        )

    report_path: Path | None = None
    if report:
        report_path = generate_report(project_dir)
        steps.append({"step": "report", "status": "generated", "path": str(report_path)})

    handoff_paths: list[Path] = []
    if handoff:
        handoff_paths = generate_handoff(project_dir)
        steps.append({"step": "handoff", "status": "generated", "file_count": len(handoff_paths)})

    result = {
        "schema_version": GOLDEN_PATH_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_name,
        "project_dir": str(project_dir),
        "template": template,
        "experiment_id": experiment_id,
        "source": str(source) if source is not None else f"package:{DEFAULT_EXAMPLE_NAME}",
        "ran_experiment": run,
        "status": _overall_status(steps),
        "steps": steps,
        "run_dir": run_metadata.get("run_dir") if run_metadata else None,
        "quality_gate_status": quality_gate.get("status") if quality_gate else None,
        "report_path": str(report_path) if report_path else None,
        "handoff_file_count": len(handoff_paths),
        "policy": (
            "Golden path output is workflow and toy execution evidence only; "
            "it does not claim scientific reproduction success."
        ),
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "golden_path.json", result)
    safe_write_text(workspace / "GOLDEN_PATH.md", _render_markdown(result))
    return result


def _overall_status(steps: list[dict[str, Any]]) -> str:
    bad_statuses = {"failed", "needs_attention"}
    if any(str(step.get("status")) in bad_statuses for step in steps):
        return "needs_attention"
    return "ready"


def _render_markdown(result: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {step} | {status} | {detail} |".format(
            step=item.get("step"),
            status=item.get("status"),
            detail=item.get("run_dir") or item.get("path") or item.get("experiment_dir") or "",
        )
        for item in result["steps"]
    )
    return f"""# Golden Path Run

- status: {result['status']}
- project_dir: `{result['project_dir']}`
- template: {result['template']}
- experiment_id: {result['experiment_id']}
- run_dir: `{result['run_dir']}`
- quality_gate_status: {result['quality_gate_status']}

| Step | Status | Detail |
| --- | --- | --- |
{rows}

## Policy

Golden path output is workflow and toy execution evidence only. It does not claim scientific reproduction success.
"""
