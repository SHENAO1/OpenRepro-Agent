"""Promotion and release gate records for OpenRepro artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, read_json, safe_write_text, write_json

PROMOTION_SCHEMA_VERSION = "1.48.0"
PROMOTION_TARGETS = {"experiment", "report", "delivery"}
PROMOTION_STATES = ("draft", "validated", "accepted", "released", "rejected")
STATE_ORDER = {state: index for index, state in enumerate(PROMOTION_STATES)}


def plan_promotion(
    project_dir: Path,
    *,
    target: str,
    candidate_id: str,
    to_state: str = "validated",
) -> dict[str, Any]:
    """Evaluate promotion gates for a target candidate."""
    project_dir = Path(project_dir)
    target = _normalize(target, PROMOTION_TARGETS, "target")
    to_state = _normalize(to_state, set(PROMOTION_STATES), "state")
    candidate_id = _candidate_id(candidate_id)
    current_state = _current_state(project_dir, target, candidate_id)
    gates = _gates(project_dir, target, to_state)
    failed = [gate for gate in gates if not gate["passed"] and gate["required"]]
    warnings = [gate for gate in gates if not gate["passed"] and not gate["required"]]
    transition_valid = _transition_valid(current_state, to_state)
    status = "ready" if not failed and transition_valid else "blocked"
    plan = {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "target": target,
        "candidate_id": candidate_id,
        "from_state": current_state,
        "to_state": to_state,
        "status": status,
        "transition_valid": transition_valid,
        "gate_count": len(gates),
        "passed_gate_count": sum(1 for gate in gates if gate["passed"]),
        "failed_gate_count": len(failed),
        "warning_gate_count": len(warnings),
        "gates": gates,
        "top_blocker": failed[0]["name"] if failed else None,
        "top_command": f"openrepro promote record {project_dir} --target {target} --candidate-id {candidate_id} --to {to_state} --confirm"
        if status == "ready"
        else _top_command(project_dir, target),
        "guardrails": [
            "Promotion plans evaluate workflow evidence gates only.",
            "Recording a promotion requires --confirm and all required gates passing.",
            "Promotion records do not assert scientific reproduction success.",
        ],
        "policy": "Promotion gates manage engineering release state for artifacts; they do not validate scientific correctness.",
    }
    write_json(project_dir / "workspace" / "promotion_plan.json", plan)
    safe_write_text(project_dir / "workspace" / "PROMOTION_PLAN.md", _render_plan_markdown(plan))
    return plan


def record_promotion(
    project_dir: Path,
    *,
    target: str,
    candidate_id: str,
    to_state: str = "validated",
    reviewer: str = "",
    note: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    """Record a promotion decision when gates pass and confirmation is explicit."""
    project_dir = Path(project_dir)
    plan = plan_promotion(project_dir, target=target, candidate_id=candidate_id, to_state=to_state)
    records = _records(project_dir)
    recorded = False
    status = "dry_run"
    if not confirm:
        status = "dry_run"
    elif plan["status"] != "ready":
        status = "blocked"
    else:
        record = {
            "schema_version": PROMOTION_SCHEMA_VERSION,
            "created_at": iso_now(),
            "target": plan["target"],
            "candidate_id": plan["candidate_id"],
            "from_state": plan["from_state"],
            "to_state": plan["to_state"],
            "reviewer": reviewer,
            "note": note,
            "gate_count": plan["gate_count"],
            "passed_gate_count": plan["passed_gate_count"],
            "plan_sha256": sha256_file(project_dir / "workspace" / "promotion_plan.json"),
        }
        records.append(record)
        _write_registry(project_dir, records)
        recorded = True
        status = "recorded"
    result = {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "target": plan["target"],
        "candidate_id": plan["candidate_id"],
        "to_state": plan["to_state"],
        "confirmed": confirm,
        "recorded": recorded,
        "status": status,
        "plan_status": plan["status"],
        "top_blocker": plan.get("top_blocker"),
        "registry_path": str(project_dir / "workspace" / "promotion_registry.json"),
        "policy": "Promotion recording is an explicit workflow state change, not a scientific validation result.",
    }
    write_json(project_dir / "workspace" / "promotion_record.json", result)
    safe_write_text(project_dir / "workspace" / "PROMOTION_RECORD.md", _render_record_markdown(result))
    return result


def promotion_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing promotion summary without mutating files."""
    project_dir = Path(project_dir)
    registry_path = project_dir / "workspace" / "promotion_registry.json"
    plan_path = project_dir / "workspace" / "promotion_plan.json"
    record_path = project_dir / "workspace" / "promotion_record.json"
    registry = read_json(registry_path, default={}) or {}
    registry = registry if isinstance(registry, dict) else {}
    plan = read_json(plan_path, default={}) or {}
    plan = plan if isinstance(plan, dict) else {}
    record = read_json(record_path, default={}) or {}
    record = record if isinstance(record, dict) else {}
    return {
        "present": registry_path.exists(),
        "path": str(registry_path) if registry_path.exists() else None,
        "markdown_path": str(project_dir / "workspace" / "PROMOTION_REGISTRY.md") if registry_path.exists() else None,
        "plan_path": str(plan_path) if plan_path.exists() else None,
        "record_path": str(record_path) if record_path.exists() else None,
        "schema_version": registry.get("schema_version") or plan.get("schema_version"),
        "status": registry.get("status", "present" if registry_path.exists() else plan.get("status", "missing")),
        "promotion_count": int(registry.get("promotion_count", 0) or 0),
        "latest_target": registry.get("latest_target") or plan.get("target"),
        "latest_candidate_id": registry.get("latest_candidate_id") or plan.get("candidate_id"),
        "latest_state": registry.get("latest_state") or record.get("to_state") or plan.get("to_state"),
        "latest_plan_status": plan.get("status"),
        "last_record_status": record.get("status"),
        "sha256": sha256_file(registry_path) if registry_path.exists() else None,
    }


def _write_registry(project_dir: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    latest = records[-1] if records else {}
    registry = {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if records else "empty",
        "promotion_count": len(records),
        "latest_target": latest.get("target"),
        "latest_candidate_id": latest.get("candidate_id"),
        "latest_state": latest.get("to_state"),
        "records": records,
        "policy": "Promotion registries record explicit engineering release decisions only.",
    }
    write_json(project_dir / "workspace" / "promotion_registry.json", registry)
    safe_write_text(project_dir / "workspace" / "PROMOTION_REGISTRY.md", _render_registry_markdown(registry))
    return registry


def _records(project_dir: Path) -> list[dict[str, Any]]:
    data = read_json(Path(project_dir) / "workspace" / "promotion_registry.json", default={}) or {}
    if not isinstance(data, dict):
        return []
    records = data.get("records", [])
    return [record for record in records if isinstance(record, dict)]


def _current_state(project_dir: Path, target: str, candidate_id: str) -> str:
    for record in reversed(_records(project_dir)):
        if record.get("target") == target and record.get("candidate_id") == candidate_id:
            return str(record.get("to_state") or "draft")
    return "draft"


def _gates(project_dir: Path, target: str, to_state: str) -> list[dict[str, Any]]:
    if to_state == "draft":
        return []
    gates = _target_gates(Path(project_dir), target)
    if to_state == "validated":
        return gates[:2] if len(gates) > 2 else gates
    if to_state == "accepted":
        return gates[:-1] if len(gates) > 2 else gates
    if to_state == "released":
        return gates
    if to_state == "rejected":
        return [_gate("reviewer_note_present", True, "Rejected promotions require an explicit record note at record time.", required=False)]
    return gates


def _target_gates(project_dir: Path, target: str) -> list[dict[str, Any]]:
    if target == "experiment":
        return [
            _file_gate(project_dir, "run_index_present", "workspace/run_index.json"),
            _file_gate(project_dir, "experiment_tracking_present", "workspace/experiment_tracking.json"),
            _json_status_gate(project_dir, "evaluation_results_passed", "workspace/evaluation_results.json", {"passed"}),
        ]
    if target == "report":
        return [
            _file_gate(project_dir, "evidence_package_present", "reports/evidence_package.md"),
            _file_gate(project_dir, "dashboard_present", "reports/dashboard/index.html"),
            _file_gate(project_dir, "local_ui_present", "reports/local_ui/index.html"),
        ]
    return [
        _json_status_gate(project_dir, "delivery_bundle_ready", "reports/delivery_bundle.json", {"ready"}),
        _json_status_gate(project_dir, "readiness_validation_passed", "reports/readiness_review_validation.json", {"passed"}),
        _file_gate(project_dir, "local_ui_present", "reports/local_ui/index.html"),
        _optional_json_status_gate(project_dir, "ci_validation_passed_if_present", "workspace/ci_validation.json", {"passed"}),
        _optional_json_status_gate(project_dir, "plugin_validation_passed_if_present", "workspace/plugin_validation.json", {"passed"}),
    ]


def _file_gate(project_dir: Path, name: str, relative: str, *, required: bool = True) -> dict[str, Any]:
    path = project_dir / relative
    return _gate(name, path.exists(), f"{relative} must exist.", required=required, path=str(path))


def _json_status_gate(project_dir: Path, name: str, relative: str, allowed: set[str], *, required: bool = True) -> dict[str, Any]:
    path = project_dir / relative
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    status = data.get("status")
    return _gate(name, path.exists() and status in allowed, f"{relative} status must be one of {sorted(allowed)}.", required=required, path=str(path), observed=status)


def _optional_json_status_gate(project_dir: Path, name: str, relative: str, allowed: set[str]) -> dict[str, Any]:
    path = project_dir / relative
    if not path.exists():
        return _gate(name, True, f"{relative} is optional when absent.", required=False, path=str(path), observed="absent")
    return _json_status_gate(project_dir, name, relative, allowed, required=False)


def _gate(
    name: str,
    passed: bool,
    message: str,
    *,
    required: bool = True,
    path: str | None = None,
    observed: Any | None = None,
) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "required": required, "message": message, "path": path, "observed": observed}


def _transition_valid(current_state: str, to_state: str) -> bool:
    if to_state == "rejected":
        return True
    return STATE_ORDER.get(to_state, 0) > STATE_ORDER.get(current_state, 0)


def _top_command(project_dir: Path, target: str) -> str:
    if target == "delivery":
        return f"openrepro refresh {project_dir} --zip"
    if target == "report":
        return f"openrepro evidence-package {project_dir} --zip"
    return f"openrepro experiments track {project_dir}"


def _normalize(value: str, allowed: set[str], label: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in allowed:
        raise ValueError(f"Promotion {label} must be one of: {', '.join(sorted(allowed))}")
    return normalized


def _candidate_id(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise ValueError("Promotion candidate id cannot be empty.")
    return candidate


def _render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Promotion Plan",
        "",
        f"- schema_version: {plan['schema_version']}",
        f"- target: {plan['target']}",
        f"- candidate_id: {plan['candidate_id']}",
        f"- from_state: {plan['from_state']}",
        f"- to_state: {plan['to_state']}",
        f"- status: {plan['status']}",
        f"- failed_gate_count: {plan['failed_gate_count']}",
        f"- top_command: `{plan.get('top_command') or ''}`",
        "",
        "| Gate | Required | Passed | Observed | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for gate in plan["gates"]:
        lines.append(
            "| {name} | {required} | {passed} | {observed} | {message} |".format(
                name=_cell(gate.get("name")),
                required=_cell(gate.get("required")),
                passed=_cell(gate.get("passed")),
                observed=_cell(gate.get("observed")),
                message=_cell(gate.get("message")),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in plan["guardrails"])
    lines.extend(["", "## Policy", "", plan["policy"], ""])
    return "\n".join(lines)


def _render_record_markdown(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Promotion Record",
            "",
            f"- schema_version: {result['schema_version']}",
            f"- target: {result['target']}",
            f"- candidate_id: {result['candidate_id']}",
            f"- to_state: {result['to_state']}",
            f"- confirmed: {result['confirmed']}",
            f"- recorded: {result['recorded']}",
            f"- status: {result['status']}",
            f"- top_blocker: {result['top_blocker']}",
            "",
            "## Policy",
            "",
            result["policy"],
            "",
        ]
    )


def _render_registry_markdown(registry: dict[str, Any]) -> str:
    lines = [
        "# Promotion Registry",
        "",
        f"- schema_version: {registry['schema_version']}",
        f"- status: {registry['status']}",
        f"- promotion_count: {registry['promotion_count']}",
        f"- latest_target: {registry['latest_target']}",
        f"- latest_state: {registry['latest_state']}",
        "",
        "| Time | Target | Candidate | From | To | Reviewer | Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in registry["records"]:
        lines.append(
            "| {time} | {target} | {candidate} | {from_state} | {to_state} | {reviewer} | {note} |".format(
                time=_cell(record.get("created_at")),
                target=_cell(record.get("target")),
                candidate=_cell(record.get("candidate_id")),
                from_state=_cell(record.get("from_state")),
                to_state=_cell(record.get("to_state")),
                reviewer=_cell(record.get("reviewer")),
                note=_cell(record.get("note")),
            )
        )
    lines.extend(["", "## Policy", "", registry["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
