"""Coverage checks for reproduction protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .reproduction_protocol import generate_reproduction_protocol, protocol_summary
from .utils import iso_now, read_json, safe_write_text, write_json

PROTOCOL_COVERAGE_SCHEMA_VERSION = "1.10.1"


def generate_protocol_coverage(project_dir: Path) -> dict[str, Any]:
    """Write workspace/protocol_coverage.json and Markdown."""
    project_dir = Path(project_dir)
    protocol_path = project_dir / "workspace" / "reproduction_protocol.json"
    protocol = read_json(protocol_path, default={}) or {}
    if not isinstance(protocol, dict) or not protocol_path.exists():
        protocol = generate_reproduction_protocol(project_dir)
    trace = read_json(project_dir / "workspace" / "claim_trace.json", default={}) or {}
    trace = trace if isinstance(trace, dict) else {}
    dimensions = _coverage_dimensions(protocol, trace)
    uncovered_count = sum(item["uncovered_count"] for item in dimensions)
    score = round(sum(item["coverage_percent"] for item in dimensions) / len(dimensions), 2) if dimensions else 0.0
    result = {
        "schema_version": PROTOCOL_COVERAGE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "protocol_schema_version": protocol.get("schema_version"),
        "protocol_status": protocol.get("status"),
        "status": _coverage_status(score, uncovered_count, str(protocol.get("status"))),
        "coverage_score": score,
        "dimension_count": len(dimensions),
        "uncovered_count": uncovered_count,
        "top_command": _top_command(dimensions, protocol),
        "dimensions": dimensions,
        "policy": "Protocol coverage checks workflow evidence coverage only; it is not a scientific reproduction score.",
    }
    write_json(project_dir / "workspace" / "protocol_coverage.json", result)
    safe_write_text(project_dir / "workspace" / "PROTOCOL_COVERAGE.md", _render_protocol_coverage_markdown(result))
    return result


def protocol_coverage_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing protocol coverage summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "protocol_coverage.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    protocol = protocol_summary(project_dir)
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "coverage_score": float(data.get("coverage_score", 0.0) or 0.0),
        "dimension_count": int(data.get("dimension_count", 0) or 0),
        "uncovered_count": int(data.get("uncovered_count", protocol["blocking_criterion_count"]) or 0),
        "top_command": data.get("top_command") or protocol.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _coverage_dimensions(protocol: dict[str, Any], trace: dict[str, Any]) -> list[dict[str, Any]]:
    claims = _claim_coverage(protocol, trace)
    data = _data_coverage(protocol)
    experiments = _experiment_coverage(protocol)
    runs = _run_coverage(protocol)
    criteria = _criteria_coverage(protocol)
    return [
        _dimension("target_claims", "Target claims linked to verified experiment/run evidence.", claims, "openrepro trace-claims <project> --validate"),
        _dimension("required_data", "Required data sources are current.", data, "openrepro validate-data <project>"),
        _dimension("required_experiments", "Required experiments have run evidence.", experiments, "openrepro run-experiment <project> --experiment-id <id> --confirm"),
        _dimension("required_runs", "Required runs passed quality gates.", runs, "openrepro quality-gate <project> --all"),
        _dimension("acceptance_criteria", "Protocol acceptance criteria passed.", criteria, str(protocol.get("top_command") or "openrepro protocol <project>")),
    ]


def _claim_coverage(protocol: dict[str, Any], trace: dict[str, Any]) -> list[dict[str, Any]]:
    experiments = [item for item in trace.get("experiments", []) if isinstance(item, dict)]
    runs = [item for item in trace.get("runs", []) if isinstance(item, dict)]
    items: list[dict[str, Any]] = []
    for claim in protocol.get("target_claims", []):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "")
        linked_experiments = [
            str(item.get("experiment_id"))
            for item in experiments
            if claim_id in {str(value) for value in item.get("claim_ids", [])}
        ]
        linked_runs = [
            str(item.get("run_id"))
            for item in runs
            if str(item.get("experiment_id")) in set(linked_experiments)
        ]
        gate_passed = any(
            str(item.get("experiment_id")) in set(linked_experiments) and item.get("quality_gate_status") == "passed"
            for item in runs
        )
        covered = bool(claim.get("verified_by_human")) and bool(linked_experiments) and bool(linked_runs) and gate_passed
        items.append(
            {
                "id": claim_id,
                "covered": covered,
                "verified_by_human": bool(claim.get("verified_by_human")),
                "linked_experiments": linked_experiments,
                "linked_runs": linked_runs,
                "quality_gate_passed": gate_passed,
            }
        )
    return items


def _data_coverage(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for source in protocol.get("required_data", []):
        if not isinstance(source, dict):
            continue
        items.append(
            {
                "id": source.get("data_id") or source.get("path"),
                "covered": bool(source.get("valid")),
                "status": source.get("status"),
                "path": source.get("path"),
            }
        )
    return items


def _experiment_coverage(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    runs = [item for item in protocol.get("required_runs", []) if isinstance(item, dict)]
    run_experiment_ids = {str(item.get("experiment_id")) for item in runs if item.get("experiment_id")}
    items = []
    for experiment in protocol.get("required_experiments", []):
        if not isinstance(experiment, dict):
            continue
        experiment_id = str(experiment.get("experiment_id") or "")
        items.append(
            {
                "id": experiment_id,
                "covered": bool(experiment_id and experiment_id in run_experiment_ids),
                "status": experiment.get("status"),
                "template": experiment.get("template"),
            }
        )
    return items


def _run_coverage(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for run in protocol.get("required_runs", []):
        if not isinstance(run, dict):
            continue
        items.append(
            {
                "id": run.get("run_id"),
                "covered": run.get("quality_gate_status") == "passed",
                "command": run.get("command"),
                "experiment_id": run.get("experiment_id"),
                "quality_gate_status": run.get("quality_gate_status"),
            }
        )
    return items


def _criteria_coverage(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for criterion in protocol.get("acceptance_criteria", []):
        if not isinstance(criterion, dict):
            continue
        items.append(
            {
                "id": criterion.get("criterion_id"),
                "covered": criterion.get("status") == "passed",
                "status": criterion.get("status"),
                "suggested_command": criterion.get("suggested_command"),
            }
        )
    return items


def _dimension(key: str, label: str, items: list[dict[str, Any]], suggested_command: str) -> dict[str, Any]:
    total = len(items)
    covered = sum(1 for item in items if item.get("covered"))
    if total <= 0:
        status = "missing"
        coverage = 0.0
        uncovered = 1
    else:
        coverage = round((covered / total) * 100, 2)
        uncovered = total - covered
        if covered == total:
            status = "complete"
        elif covered > 0:
            status = "partial"
        else:
            status = "blocked"
    return {
        "key": key,
        "label": label,
        "status": status,
        "total_count": total,
        "covered_count": covered,
        "uncovered_count": uncovered,
        "coverage_percent": coverage,
        "top_command": None if status == "complete" else suggested_command,
        "items": items,
    }


def _coverage_status(score: float, uncovered_count: int, protocol_status: str) -> str:
    if uncovered_count == 0 and protocol_status == "ready":
        return "complete"
    if score > 0:
        return "partial"
    return "blocked"


def _top_command(dimensions: list[dict[str, Any]], protocol: dict[str, Any]) -> str | None:
    for dimension in dimensions:
        if dimension["status"] != "complete":
            command = str(dimension.get("top_command") or "")
            return command.replace("<project>", str(protocol.get("project_dir")))
    return None


def _render_protocol_coverage_markdown(coverage: dict[str, Any]) -> str:
    lines = [
        "# Protocol Coverage",
        "",
        f"- schema_version: {coverage['schema_version']}",
        f"- status: {coverage['status']}",
        f"- coverage_score: {coverage['coverage_score']}",
        f"- uncovered_count: {coverage['uncovered_count']}",
        f"- top_command: {coverage['top_command']}",
        "",
        "## Dimensions",
        "",
        "| Dimension | Status | Covered | Total | Coverage |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in coverage["dimensions"]:
        lines.append(
            f"| {item['label']} | {item['status']} | {item['covered_count']} | {item['total_count']} | {item['coverage_percent']} |"
        )
    lines.extend(["", "## Policy", "", coverage["policy"], ""])
    return "\n".join(lines)
