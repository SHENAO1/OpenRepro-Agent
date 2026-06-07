"""Safe derived-artifact refresh pipeline."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

REFRESH_RUN_SCHEMA_VERSION = "1.26.0"


def generate_refresh_run(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Refresh derived workflow artifacts without running experiments or closing human decisions."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    from .advance import generate_advance_plan
    from .agent_adapter import generate_agent_adapter, validate_agent_adapter
    from .agent_board import generate_agent_board
    from .agent_dispatch import generate_agent_dispatch
    from .agent_exec_plan import generate_agent_exec_plan
    from .acceptance_criteria import generate_acceptance_criteria
    from .checkpoints import generate_workflow_checkpoints
    from .claim_evidence_binder import generate_claim_evidence_binder, validate_claim_evidence_binder
    from .claim_evidence_report import generate_claim_evidence_report
    from .claim_evidence_report_validation import validate_claim_evidence_report
    from .claim_signoff import generate_claim_signoffs
    from .claim_signoff_validation import validate_claim_signoffs
    from .claim_trace import generate_claim_trace, validate_claim_trace
    from .collaboration_pack import generate_collaboration_pack
    from .dashboard import generate_dashboard
    from .data_registry import validate_data_index
    from .data_profile import generate_data_profile
    from .delivery_bundle import generate_delivery_bundle
    from .evidence_explorer import generate_evidence_explorer
    from .evidence_query import query_evidence
    from .evidence_package import generate_evidence_package
    from .freshness import generate_artifact_freshness
    from .gaps import generate_reproduction_gaps
    from .handoff_generator import generate_handoff
    from .inspector import inspect_project
    from .lineage import generate_run_lineage
    from .multi_agent_plan import generate_multi_agent_plan
    from .multi_agent_plan_validation import validate_multi_agent_plan
    from .paper_lineage import generate_paper_lineage
    from .protocol_coverage import generate_protocol_coverage
    from .protocol_plan import generate_protocol_plan
    from .protocol_preflight import generate_protocol_preflight
    from .project_profile import generate_project_profile
    from .quality_gate import evaluate_all_quality_gates
    from .readiness_review import generate_readiness_review
    from .readiness_review_validation import validate_readiness_review
    from .report_generator import generate_report
    from .repro_lock import generate_repro_lock, validate_repro_lock
    from .reproduction_protocol import generate_reproduction_protocol
    from .review_board import generate_review_board
    from .review_action_plan import generate_review_action_plan
    from .review_decisions import generate_review_decisions
    from .review_site import generate_review_site
    from .reviewer_packet import generate_reviewer_packet
    from .run_index import generate_run_index
    from .scorecard import generate_reproduction_scorecard
    from .timeline import generate_project_timeline

    steps: list[tuple[str, str, Callable[[], Any]]] = [
        ("data_validation", "Validate registered data before refreshing run evidence.", lambda: validate_data_index(project_dir)),
        ("data_profile", "Profile registered data structure and schema warnings.", lambda: generate_data_profile(project_dir)),
        ("repro_lock", "Refresh project reproducibility lockfile.", lambda: generate_repro_lock(project_dir)),
        ("repro_lock_validation", "Validate project reproducibility lockfile.", lambda: validate_repro_lock(project_dir)),
        ("quality_gates", "Evaluate quality gates for existing runs.", lambda: evaluate_all_quality_gates(project_dir)),
        ("run_index", "Refresh run index and static run explorer.", lambda: generate_run_index(project_dir, export_zip=export_zip)),
        ("lineage", "Refresh run lineage.", lambda: generate_run_lineage(project_dir)),
        ("claim_trace", "Refresh claim trace.", lambda: generate_claim_trace(project_dir)),
        ("claim_trace_validation", "Validate claim trace.", lambda: validate_claim_trace(project_dir)),
        ("scorecard", "Refresh readiness scorecard.", lambda: generate_reproduction_scorecard(project_dir)),
        ("gaps", "Refresh reproduction gaps.", lambda: generate_reproduction_gaps(project_dir)),
        ("checkpoints", "Refresh workflow checkpoints.", lambda: generate_workflow_checkpoints(project_dir)),
        ("advance_plan", "Refresh guided advance dry-run.", lambda: generate_advance_plan(project_dir, dry_run=True)),
        ("review_board", "Refresh review board.", lambda: generate_review_board(project_dir)),
        ("review_decisions", "Refresh review decision summary without closing items.", lambda: generate_review_decisions(project_dir)),
        ("protocol", "Refresh reproduction protocol.", lambda: generate_reproduction_protocol(project_dir)),
        ("protocol_coverage", "Refresh protocol coverage.", lambda: generate_protocol_coverage(project_dir)),
        ("protocol_plan", "Refresh protocol action plan.", lambda: generate_protocol_plan(project_dir)),
        ("protocol_preflight", "Refresh protocol preflight.", lambda: generate_protocol_preflight(project_dir)),
        ("claim_evidence_binder", "Refresh claim evidence binder.", lambda: generate_claim_evidence_binder(project_dir)),
        ("claim_evidence_binder_validation", "Validate claim evidence binder.", lambda: validate_claim_evidence_binder(project_dir)),
        ("claim_signoffs", "Refresh claim signoff summary without adding signoffs.", lambda: generate_claim_signoffs(project_dir)),
        ("claim_signoff_validation", "Validate claim signoffs.", lambda: validate_claim_signoffs(project_dir)),
        ("claim_evidence_report", "Refresh claim evidence report.", lambda: generate_claim_evidence_report(project_dir)),
        ("claim_evidence_report_validation", "Validate claim evidence report.", lambda: validate_claim_evidence_report(project_dir)),
        ("reviewer_packet", "Refresh reviewer packet.", lambda: generate_reviewer_packet(project_dir, export_zip=export_zip)),
        ("timeline", "Refresh project timeline.", lambda: generate_project_timeline(project_dir)),
        ("project_profile", "Refresh project reproduction profile.", lambda: generate_project_profile(project_dir)),
        ("acceptance_criteria", "Refresh acceptance criteria.", lambda: generate_acceptance_criteria(project_dir)),
        ("inspect", "Refresh inspect summary.", lambda: inspect_project(project_dir)),
        ("report", "Refresh project report.", lambda: generate_report(project_dir)),
        ("handoff", "Refresh handoff files.", lambda: generate_handoff(project_dir)),
        ("evidence_package", "Refresh evidence package.", lambda: generate_evidence_package(project_dir, export_zip=export_zip)),
        ("review_site", "Refresh static review site.", lambda: generate_review_site(project_dir, export_zip=export_zip)),
    ]

    records = [_run_step(name, description, action) for name, description, action in steps]
    result = _build_result(project_dir, export_zip, records)
    workspace = project_dir / "workspace"
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "collaboration_pack",
            "Refresh collaboration pack after refresh status is available.",
            lambda: generate_collaboration_pack(project_dir, export_zip=export_zip),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "artifact_freshness",
            "Refresh artifact freshness graph after handoff artifacts are current.",
            lambda: generate_artifact_freshness(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "dashboard",
            "Refresh static project dashboard.",
            lambda: generate_dashboard(project_dir, export_zip=export_zip),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "readiness_review",
            "Refresh final readiness review.",
            lambda: generate_readiness_review(project_dir, export_zip=export_zip),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "readiness_review_validation",
            "Validate final readiness review.",
            lambda: validate_readiness_review(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "review_action_plan",
            "Refresh role-based review action plan.",
            lambda: generate_review_action_plan(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "delivery_bundle",
            "Refresh final workflow delivery bundle.",
            lambda: generate_delivery_bundle(project_dir, export_zip=export_zip),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "multi_agent_plan",
            "Refresh guarded multi-agent coordination plan.",
            lambda: generate_multi_agent_plan(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "multi_agent_plan_validation",
            "Validate guarded multi-agent coordination plan.",
            lambda: validate_multi_agent_plan(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "agent_board",
            "Refresh static multi-agent task board.",
            lambda: generate_agent_board(project_dir, export_zip=export_zip),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "agent_dispatch",
            "Refresh per-agent task dispatch pack.",
            lambda: generate_agent_dispatch(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "agent_exec_plan",
            "Refresh safe agent execution dry-run plan.",
            lambda: generate_agent_exec_plan(project_dir, dry_run=True),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "agent_adapter",
            "Refresh supervised external-agent adapter.",
            lambda: generate_agent_adapter(project_dir),
        )
    )
    records.append(
        _run_step(
            "agent_adapter_validation",
            "Validate supervised external-agent adapter.",
            lambda: validate_agent_adapter(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "paper_lineage",
            "Refresh paper-level lineage graph.",
            lambda: generate_paper_lineage(project_dir),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "evidence_explorer",
            "Refresh static paper evidence explorer.",
            lambda: generate_evidence_explorer(project_dir, export_zip=export_zip),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    records.append(
        _run_step(
            "evidence_query",
            "Refresh default evidence query artifacts.",
            lambda: query_evidence(project_dir, kind="all", limit=50),
        )
    )
    result = _build_result(project_dir, export_zip, records)
    write_json(workspace / "refresh_run.json", result)
    safe_write_text(workspace / "REFRESH_RUN.md", _render_markdown(result))
    if export_zip:
        result["zip_path"] = str(_export_zip(project_dir, result))
        write_json(workspace / "refresh_run.json", result)
    else:
        zip_path = workspace / "refresh_run.zip"
        result["zip_path"] = str(zip_path) if zip_path.exists() else None
    return result


def refresh_run_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing refresh run summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "refresh_run.json"
    markdown_path = project_dir / "workspace" / "REFRESH_RUN.md"
    zip_path = project_dir / "workspace" / "refresh_run.zip"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "step_count": int(data.get("step_count", 0) or 0),
        "passed_step_count": int(data.get("passed_step_count", 0) or 0),
        "failed_step_count": int(data.get("failed_step_count", 0) or 0),
        "top_failed_step": data.get("top_failed_step"),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _build_result(project_dir: Path, export_zip: bool, records: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [item for item in records if item["status"] != "passed"]
    return {
        "schema_version": REFRESH_RUN_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "complete" if not failed else "failed",
        "export_zip": export_zip,
        "step_count": len(records),
        "passed_step_count": sum(1 for item in records if item["status"] == "passed"),
        "failed_step_count": len(failed),
        "top_failed_step": failed[0]["name"] if failed else None,
        "top_command": f"openrepro refresh {project_dir} --zip" if failed and export_zip else f"openrepro refresh {project_dir}" if failed else None,
        "steps": records,
        "guardrails": [
            "Does not run experiments.",
            "Does not create or edit human claim signoffs.",
            "Does not resolve review decisions.",
            "Does not fabricate missing scientific artifacts.",
        ],
        "policy": "Refresh runs regenerate derived workflow and handoff artifacts only; they do not prove scientific reproduction.",
    }


def _run_step(name: str, description: str, action: Callable[[], Any]) -> dict[str, Any]:
    started = perf_counter()
    try:
        output = action()
    except Exception as exc:
        return {
            "name": name,
            "description": description,
            "status": "failed",
            "duration_seconds": round(perf_counter() - started, 4),
            "error": str(exc),
            "summary": {},
        }
    return {
        "name": name,
        "description": description,
        "status": "passed",
        "duration_seconds": round(perf_counter() - started, 4),
        "error": None,
        "summary": _summary(output),
    }


def _summary(output: Any) -> dict[str, Any]:
    if isinstance(output, Path):
        return {"path": str(output)}
    if isinstance(output, list):
        return {"item_count": len(output)}
    if not isinstance(output, dict):
        return {"type": type(output).__name__}
    keys = [
        "schema_version",
        "status",
        "overall_status",
        "valid",
        "healthy",
        "run_count",
        "claim_count",
        "event_count",
        "open_count",
        "action_count",
        "open_task_count",
        "issue_count",
        "warning_count",
        "safe_step_count",
        "blocked_task_count",
        "node_count",
        "edge_count",
        "item_count",
        "step_count",
        "failed_step_count",
        "missing_file_count",
        "top_command",
        "top_suggested_command",
    ]
    return {key: output.get(key) for key in keys if key in output}


def _export_zip(project_dir: Path, result: dict[str, Any]) -> Path:
    zip_path = project_dir / "workspace" / "refresh_run.zip"
    files = [
        project_dir / "workspace" / "refresh_run.json",
        project_dir / "workspace" / "REFRESH_RUN.md",
    ]
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Refresh Run",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- step_count: {result['step_count']}",
        f"- passed_step_count: {result['passed_step_count']}",
        f"- failed_step_count: {result['failed_step_count']}",
        f"- top_failed_step: {result['top_failed_step']}",
        f"- top_command: {result['top_command']}",
        "",
        "## Steps",
        "",
        "| Step | Status | Seconds | Summary | Error |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in result["steps"]:
        lines.append(
            "| {name} | {status} | {duration} | {summary} | {error} |".format(
                name=_cell(step["name"]),
                status=_cell(step["status"]),
                duration=_cell(step["duration_seconds"]),
                summary=_cell(step.get("summary", {})),
                error=_cell(step.get("error") or ""),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    for item in result["guardrails"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
