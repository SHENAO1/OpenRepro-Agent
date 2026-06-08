"""Experiment evaluation registry and leaderboards."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .experiment_tracking import generate_experiment_tracking
from .utils import iso_now, read_json, safe_write_text, write_json

EXPERIMENT_EVALUATION_SCHEMA_VERSION = "1.42.0"
OPERATORS = {">=", "<=", ">", "<", "==", "!="}


def define_evaluation_suite(
    project_dir: Path,
    *,
    suite: str = "default",
    metric: str,
    threshold: float,
    operator: str = ">=",
    higher_is_better: bool = True,
    baseline_experiment: str | None = None,
) -> dict[str, Any]:
    """Create or update an experiment evaluation suite."""
    project_dir = Path(project_dir)
    operator = _normalize_operator(operator)
    registry = _registry(project_dir)
    suites = {item["suite"]: item for item in registry.get("suites", []) if isinstance(item, dict) and item.get("suite")}
    created_at = suites.get(suite, {}).get("created_at") or iso_now()
    suites[suite] = {
        "suite": suite,
        "created_at": created_at,
        "updated_at": iso_now(),
        "baseline_experiment": baseline_experiment,
        "criteria": [
            {
                "metric": metric,
                "operator": operator,
                "threshold": threshold,
                "higher_is_better": higher_is_better,
            }
        ],
    }
    result = _registry_doc(project_dir, list(suites.values()))
    write_json(project_dir / "workspace" / "evaluation_registry.json", result)
    safe_write_text(project_dir / "workspace" / "EVALUATION_REGISTRY.md", _render_registry_markdown(result))
    return result


def evaluation_registry_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing evaluation registry summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "evaluation_registry.json"
    markdown_path = project_dir / "workspace" / "EVALUATION_REGISTRY.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "suite_count": int(data.get("suite_count", 0) or 0),
    }


def run_evaluation_suite(project_dir: Path, *, suite: str = "default") -> dict[str, Any]:
    """Run an evaluation suite against latest tracked experiment metrics."""
    project_dir = Path(project_dir)
    registry = _registry(project_dir)
    suite_def = _suite(registry, suite)
    tracking = generate_experiment_tracking(project_dir, export_zip=False)
    experiments = tracking.get("experiments", []) if isinstance(tracking.get("experiments"), list) else []
    rows = [_experiment_eval(experiment, suite_def) for experiment in experiments if isinstance(experiment, dict)]
    result = {
        "schema_version": EXPERIMENT_EVALUATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "suite": suite,
        "status": "passed" if rows and all(row["status"] == "passed" for row in rows) else "failed" if rows else "empty",
        "experiment_count": len(rows),
        "passed_experiment_count": sum(1 for row in rows if row["status"] == "passed"),
        "failed_experiment_count": sum(1 for row in rows if row["status"] == "failed"),
        "missing_metric_count": sum(row["missing_metric_count"] for row in rows),
        "criteria": suite_def.get("criteria", []),
        "experiments": rows,
        "policy": "Experiment evaluations compare observed latest workflow metrics against declared thresholds only; they do not claim paper reproduction success.",
    }
    write_json(project_dir / "workspace" / "evaluation_results.json", result)
    safe_write_text(project_dir / "workspace" / "EVALUATION_RESULTS.md", _render_results_markdown(result))
    generate_experiment_leaderboard(project_dir, suite=suite)
    return result


def evaluation_results_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing evaluation result summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "evaluation_results.json"
    markdown_path = project_dir / "workspace" / "EVALUATION_RESULTS.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "experiment_count": int(data.get("experiment_count", 0) or 0),
        "passed_experiment_count": int(data.get("passed_experiment_count", 0) or 0),
        "failed_experiment_count": int(data.get("failed_experiment_count", 0) or 0),
    }


def generate_experiment_leaderboard(project_dir: Path, *, suite: str = "default", metric: str | None = None) -> dict[str, Any]:
    """Generate an experiment leaderboard from tracked latest metrics."""
    project_dir = Path(project_dir)
    registry = _registry(project_dir)
    suite_def = _suite(registry, suite)
    criterion = _criterion(suite_def, metric)
    metric_name = str(criterion.get("metric"))
    higher_is_better = bool(criterion.get("higher_is_better", True))
    tracking = generate_experiment_tracking(project_dir, export_zip=False)
    experiments = []
    for experiment in tracking.get("experiments", []):
        if not isinstance(experiment, dict):
            continue
        metrics = experiment.get("latest_metrics", {}) if isinstance(experiment.get("latest_metrics"), dict) else {}
        value = metrics.get(metric_name)
        experiments.append(
            {
                "experiment_id": experiment.get("experiment_id"),
                "latest_run_id": experiment.get("latest_run_id"),
                "metric": metric_name,
                "value": value,
                "rankable": isinstance(value, (int, float)),
                "quality_gate_status": experiment.get("latest_quality_gate_status"),
                "status": experiment.get("status"),
            }
        )
    ranked_values = sorted(
        [item for item in experiments if item["rankable"]],
        key=lambda item: item["value"],
        reverse=higher_is_better,
    )
    ranked = ranked_values + [item for item in experiments if not item["rankable"]]
    rank = 1
    for row in ranked:
        row["rank"] = rank if row["rankable"] else None
        if row["rankable"]:
            rank += 1
    result = {
        "schema_version": EXPERIMENT_EVALUATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "suite": suite,
        "metric": metric_name,
        "higher_is_better": higher_is_better,
        "status": "ready" if ranked else "empty",
        "experiment_count": len(ranked),
        "rankable_experiment_count": sum(1 for row in ranked if row["rankable"]),
        "experiments": ranked,
        "policy": "Leaderboards rank observed latest metrics only; they are engineering summaries, not scientific claims.",
    }
    write_json(project_dir / "workspace" / "experiment_leaderboard.json", result)
    safe_write_text(project_dir / "workspace" / "EXPERIMENT_LEADERBOARD.md", _render_leaderboard_markdown(result))
    return result


def _registry(project_dir: Path) -> dict[str, Any]:
    data = read_json(Path(project_dir) / "workspace" / "evaluation_registry.json", default={}) or {}
    if isinstance(data, dict) and data.get("suites"):
        return data
    return _registry_doc(Path(project_dir), [])


def _registry_doc(project_dir: Path, suites: list[dict[str, Any]]) -> dict[str, Any]:
    suites = sorted(suites, key=lambda item: str(item.get("suite") or ""))
    return {
        "schema_version": EXPERIMENT_EVALUATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if suites else "empty",
        "suite_count": len(suites),
        "suites": suites,
        "policy": "Evaluation suites declare thresholds for observed experiment metrics; they do not verify scientific correctness.",
    }


def _suite(registry: dict[str, Any], suite: str) -> dict[str, Any]:
    for item in registry.get("suites", []):
        if isinstance(item, dict) and item.get("suite") == suite:
            return item
    raise ValueError(f"Evaluation suite not found: {suite}")


def _criterion(suite_def: dict[str, Any], metric: str | None) -> dict[str, Any]:
    criteria = suite_def.get("criteria", []) if isinstance(suite_def.get("criteria"), list) else []
    if metric:
        for criterion in criteria:
            if criterion.get("metric") == metric:
                return criterion
        raise ValueError(f"Metric not found in evaluation suite: {metric}")
    if not criteria:
        raise ValueError("Evaluation suite has no criteria.")
    return criteria[0]


def _experiment_eval(experiment: dict[str, Any], suite_def: dict[str, Any]) -> dict[str, Any]:
    metrics = experiment.get("latest_metrics", {}) if isinstance(experiment.get("latest_metrics"), dict) else {}
    checks = []
    for criterion in suite_def.get("criteria", []):
        value = metrics.get(criterion.get("metric"))
        check = {
            "metric": criterion.get("metric"),
            "value": value,
            "operator": criterion.get("operator"),
            "threshold": criterion.get("threshold"),
            "status": _check_status(value, criterion),
        }
        checks.append(check)
    return {
        "experiment_id": experiment.get("experiment_id"),
        "latest_run_id": experiment.get("latest_run_id"),
        "status": "passed" if checks and all(check["status"] == "passed" for check in checks) else "failed",
        "missing_metric_count": sum(1 for check in checks if check["status"] == "missing"),
        "checks": checks,
    }


def _check_status(value: Any, criterion: dict[str, Any]) -> str:
    if not isinstance(value, (int, float)):
        return "missing"
    threshold = float(criterion.get("threshold"))
    operator = criterion.get("operator")
    passed = {
        ">=": value >= threshold,
        "<=": value <= threshold,
        ">": value > threshold,
        "<": value < threshold,
        "==": value == threshold,
        "!=": value != threshold,
    }[operator]
    return "passed" if passed else "failed"


def _normalize_operator(operator: str) -> str:
    value = (operator or ">=").strip()
    if value not in OPERATORS:
        raise ValueError(f"Operator must be one of: {', '.join(sorted(OPERATORS))}")
    return value


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_registry_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Registry",
        "",
        f"- status: {result['status']}",
        f"- suite_count: {result['suite_count']}",
        "",
        "| Suite | Baseline | Criteria |",
        "| --- | --- | --- |",
    ]
    for suite in result["suites"]:
        criteria = ", ".join(f"{item['metric']} {item['operator']} {item['threshold']}" for item in suite.get("criteria", []))
        lines.append(f"| {_cell(suite.get('suite'))} | {_cell(suite.get('baseline_experiment'))} | {_cell(criteria)} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _render_results_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Results",
        "",
        f"- suite: {result['suite']}",
        f"- status: {result['status']}",
        f"- experiment_count: {result['experiment_count']}",
        f"- passed_experiment_count: {result['passed_experiment_count']}",
        "",
        "| Experiment | Latest run | Status | Missing metrics |",
        "| --- | --- | --- | --- |",
    ]
    for row in result["experiments"]:
        lines.append(f"| {_cell(row.get('experiment_id'))} | {_cell(row.get('latest_run_id'))} | {_cell(row.get('status'))} | {_cell(row.get('missing_metric_count'))} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _render_leaderboard_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Experiment Leaderboard",
        "",
        f"- suite: {result['suite']}",
        f"- metric: {result['metric']}",
        f"- higher_is_better: {result['higher_is_better']}",
        "",
        "| Rank | Experiment | Latest run | Value | Gate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in result["experiments"]:
        lines.append(f"| {_cell(row.get('rank'))} | {_cell(row.get('experiment_id'))} | {_cell(row.get('latest_run_id'))} | {_cell(row.get('value'))} | {_cell(row.get('quality_gate_status'))} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
