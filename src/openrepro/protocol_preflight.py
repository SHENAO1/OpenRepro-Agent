"""Preflight checks before protocol execution or handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .data_registry import data_index_summary
from .evidence_fingerprint import evidence_package_status
from .experiment_spec import inspect_experiment_specs
from .protocol_coverage import protocol_coverage_summary
from .protocol_plan import generate_protocol_plan, protocol_plan_summary
from .quality_gate import quality_gate_summaries
from .reproduction_protocol import protocol_summary
from .review_decisions import review_decision_summary
from .utils import iso_now, read_json, safe_write_text, write_json

PROTOCOL_PREFLIGHT_SCHEMA_VERSION = "1.11.1"


def generate_protocol_preflight(project_dir: Path) -> dict[str, Any]:
    """Write workspace/protocol_preflight.json and Markdown."""
    project_dir = Path(project_dir)
    plan_path = project_dir / "workspace" / "protocol_plan.json"
    if not plan_path.exists():
        generate_protocol_plan(project_dir)

    checks = _preflight_checks(project_dir)
    blocking = [item for item in checks if item["severity"] == "blocking" and item["status"] != "passed"]
    warnings = [item for item in checks if item["severity"] == "warning" and item["status"] != "passed"]
    result = {
        "schema_version": PROTOCOL_PREFLIGHT_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "ready" if not blocking else "blocked",
        "check_count": len(checks),
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "top_command": blocking[0]["suggested_command"] if blocking else None,
        "checks": checks,
        "policy": "Protocol preflight checks workflow readiness only; it does not execute experiments or verify scientific correctness.",
    }
    write_json(project_dir / "workspace" / "protocol_preflight.json", result)
    safe_write_text(project_dir / "workspace" / "PROTOCOL_PREFLIGHT.md", _render_protocol_preflight_markdown(result))
    return result


def protocol_preflight_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing protocol preflight summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "protocol_preflight.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    plan = protocol_plan_summary(project_dir)
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "check_count": int(data.get("check_count", 0) or 0),
        "blocking_count": int(data.get("blocking_count", plan["action_count"]) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "top_command": data.get("top_command") or plan.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _preflight_checks(project_dir: Path) -> list[dict[str, Any]]:
    protocol = protocol_summary(project_dir)
    coverage = protocol_coverage_summary(project_dir)
    plan = protocol_plan_summary(project_dir)
    data = data_index_summary(project_dir)
    specs = inspect_experiment_specs(project_dir)
    gates = quality_gate_summaries(project_dir)
    review_decisions = review_decision_summary(project_dir)
    evidence_status = evidence_package_status(project_dir)
    all_gates_passed = bool(gates) and all(item.get("status") == "passed" for item in gates)

    return [
        _check(
            "protocol_ready",
            "Reproduction protocol is ready.",
            protocol["present"] and protocol["status"] == "ready" and protocol["blocking_criterion_count"] == 0,
            "blocking",
            str(protocol.get("top_command") or f"openrepro protocol {project_dir}"),
            protocol,
        ),
        _check(
            "coverage_complete",
            "Protocol coverage is complete.",
            coverage["present"] and coverage["status"] == "complete" and coverage["uncovered_count"] == 0,
            "blocking",
            str(coverage.get("top_command") or f"openrepro protocol-coverage {project_dir}"),
            coverage,
        ),
        _check(
            "plan_clear",
            "Protocol plan has no open actions.",
            plan["present"] and plan["status"] == "complete" and plan["action_count"] == 0,
            "blocking",
            str(plan.get("top_command") or f"openrepro protocol-plan {project_dir}"),
            plan,
        ),
        _check(
            "data_current",
            "Registered data provenance is current.",
            data["registered_count"] > 0 and data["invalid_count"] == 0,
            "blocking",
            f"openrepro validate-data {project_dir}",
            data,
        ),
        _check(
            "specs_current",
            "Experiment specs exist and are current.",
            bool(specs["specs"]) and specs["missing_count"] == 0 and specs["invalid_count"] == 0 and specs["stale_count"] == 0,
            "blocking",
            f"openrepro validate-experiment-spec {project_dir} --experiment-id <id>",
            specs,
        ),
        _check(
            "quality_gates_passed",
            "All available quality gates passed.",
            all_gates_passed,
            "blocking",
            f"openrepro quality-gate {project_dir} --all",
            {"quality_gate_count": len(gates), "failed_count": sum(1 for item in gates if item.get("status") == "failed")},
        ),
        _check(
            "review_decisions_clear",
            "Review decisions have no unresolved items.",
            review_decisions["unresolved_item_count"] == 0,
            "blocking",
            str(review_decisions.get("top_command") or f"openrepro review-board {project_dir}"),
            review_decisions,
        ),
        _check(
            "evidence_package_current",
            "Evidence package is current.",
            evidence_status["status"] == "current" and not evidence_status["stale"],
            "warning",
            f"openrepro evidence-package {project_dir}",
            evidence_status,
        ),
    ]


def _check(
    check_id: str,
    label: str,
    passed: bool,
    severity: str,
    suggested_command: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "label": label,
        "status": "passed" if passed else ("warning" if severity == "warning" else "blocked"),
        "severity": severity,
        "suggested_command": None if passed else suggested_command,
        "details": details,
    }


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_protocol_preflight_markdown(preflight: dict[str, Any]) -> str:
    lines = [
        "# Protocol Preflight",
        "",
        f"- schema_version: {preflight['schema_version']}",
        f"- status: {preflight['status']}",
        f"- check_count: {preflight['check_count']}",
        f"- blocking_count: {preflight['blocking_count']}",
        f"- warning_count: {preflight['warning_count']}",
        f"- top_command: {preflight['top_command']}",
        "",
        "## Checks",
        "",
        "| Check | Severity | Status | Suggested command |",
        "| --- | --- | --- | --- |",
    ]
    for check in preflight["checks"]:
        lines.append(
            "| {label} | {severity} | {status} | `{command}` |".format(
                label=_cell(check["label"]),
                severity=_cell(check["severity"]),
                status=_cell(check["status"]),
                command=_cell(check.get("suggested_command") or ""),
            )
        )
    lines.extend(["", "## Policy", "", preflight["policy"], ""])
    return "\n".join(lines)
