"""Lightweight data expectation suites and validation results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .data_profile import _format, _read_rows, _value_type, generate_data_profile
from .data_registry import data_index_summary
from .utils import iso_now, read_json, safe_write_text, write_json

DATA_EXPECTATIONS_SCHEMA_VERSION = "1.36.0"
EXPECTATION_TYPES = {"row_count_min", "not_null", "type", "range", "allowed_values"}


def init_data_expectations(project_dir: Path, *, overwrite: bool = False, max_rows: int = 5000) -> dict[str, Any]:
    """Initialize a default expectation suite from the current data profile."""
    project_dir = Path(project_dir)
    suite_path = project_dir / "workspace" / "data_expectations.json"
    if suite_path.exists() and not overwrite:
        suite = read_json(suite_path, default={}) or {}
        return suite if isinstance(suite, dict) else {}
    profile = generate_data_profile(project_dir, max_rows=max_rows)
    expectations = _expectations_from_profile(profile)
    suite = {
        "schema_version": DATA_EXPECTATIONS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if expectations else "empty",
        "expectation_count": len(expectations),
        "expectations": expectations,
        "policy": "Data expectations validate lightweight structural contracts only; they do not verify dataset semantics, labels, provenance claims, or scientific data quality.",
    }
    write_json(suite_path, suite)
    safe_write_text(project_dir / "workspace" / "DATA_EXPECTATIONS.md", _render_suite_markdown(suite))
    return suite


def run_data_expectations(project_dir: Path, *, max_rows: int = 100000) -> dict[str, Any]:
    """Run the configured data expectation suite."""
    project_dir = Path(project_dir)
    suite = init_data_expectations(project_dir, overwrite=False)
    data = data_index_summary(project_dir)
    sources = {str(source.get("data_id")): source for source in data.get("sources", [])}
    records = [_evaluate_expectation(expectation, sources, max_rows=max_rows) for expectation in suite.get("expectations", [])]
    failed = [record for record in records if record["status"] == "failed"]
    result = {
        "schema_version": DATA_EXPECTATIONS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "passed" if not failed else "failed",
        "expectation_count": len(records),
        "passed_count": sum(1 for record in records if record["status"] == "passed"),
        "failed_count": len(failed),
        "top_failed_expectation": failed[0]["expectation_id"] if failed else None,
        "results": records,
        "policy": suite.get("policy") or "Data expectations validate lightweight structural contracts only.",
    }
    write_json(project_dir / "workspace" / "data_expectation_results.json", result)
    safe_write_text(project_dir / "workspace" / "DATA_EXPECTATION_RESULTS.md", _render_results_markdown(result))
    return result


def data_expectations_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing data expectation summary without mutating files."""
    project_dir = Path(project_dir)
    suite_path = project_dir / "workspace" / "data_expectations.json"
    result_path = project_dir / "workspace" / "data_expectation_results.json"
    suite = read_json(suite_path, default={}) or {}
    result = read_json(result_path, default={}) or {}
    suite = suite if isinstance(suite, dict) else {}
    result = result if isinstance(result, dict) else {}
    return {
        "present": suite_path.exists(),
        "path": str(suite_path) if suite_path.exists() else None,
        "results_path": str(result_path) if result_path.exists() else None,
        "schema_version": suite.get("schema_version") or result.get("schema_version"),
        "status": result.get("status", "present" if suite_path.exists() else "missing"),
        "expectation_count": int((result.get("expectation_count") or suite.get("expectation_count") or 0)),
        "passed_count": int(result.get("passed_count", 0) or 0),
        "failed_count": int(result.get("failed_count", 0) or 0),
        "top_failed_expectation": result.get("top_failed_expectation"),
    }


def _expectations_from_profile(profile: dict[str, Any]) -> list[dict[str, Any]]:
    expectations: list[dict[str, Any]] = []
    for source in profile.get("sources", []):
        if not source.get("profiled"):
            continue
        data_id = str(source.get("data_id"))
        expectations.append(
            _expectation(
                data_id=data_id,
                expectation_type="row_count_min",
                params={"min": 1},
            )
        )
        for column in source.get("columns", []):
            name = str(column.get("name"))
            dominant = str(column.get("dominant_type") or "")
            if dominant and dominant != "null":
                expectations.append(
                    _expectation(
                        data_id=data_id,
                        expectation_type="type",
                        column=name,
                        params={"type": dominant},
                    )
                )
            if int(column.get("null_count", 0) or 0) == 0:
                expectations.append(_expectation(data_id=data_id, expectation_type="not_null", column=name))
            numeric = column.get("numeric", {})
            if numeric and dominant in {"int", "float"}:
                expectations.append(
                    _expectation(
                        data_id=data_id,
                        expectation_type="range",
                        column=name,
                        params={"min": numeric.get("min"), "max": numeric.get("max")},
                    )
                )
    return expectations


def _expectation(
    *,
    data_id: str,
    expectation_type: str,
    column: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    suffix = f"{data_id}_{expectation_type}_{column or 'table'}"
    return {
        "expectation_id": suffix[:120],
        "data_id": data_id,
        "type": expectation_type,
        "column": column,
        "params": params or {},
        "enabled": True,
    }


def _evaluate_expectation(expectation: dict[str, Any], sources: dict[str, dict[str, Any]], *, max_rows: int) -> dict[str, Any]:
    expectation_type = str(expectation.get("type") or "")
    if expectation_type not in EXPECTATION_TYPES:
        return _record(expectation, "failed", "Unknown expectation type.")
    if not expectation.get("enabled", True):
        return _record(expectation, "skipped", "Expectation is disabled.")
    source = sources.get(str(expectation.get("data_id")))
    if not source:
        return _record(expectation, "failed", "Registered data source not found.")
    if source.get("status") != "current":
        return _record(expectation, "failed", f"Registered data source is not current: {source.get('status')}")
    path = Path(str(source.get("path") or ""))
    rows, row_count, truncated, warnings = _read_rows(path, _format(path), max_rows=max_rows)
    if warnings:
        return _record(expectation, "failed", "; ".join(warnings), observed={"row_count": row_count})
    column = expectation.get("column")
    params = expectation.get("params", {}) if isinstance(expectation.get("params"), dict) else {}
    if expectation_type == "row_count_min":
        minimum = int(params.get("min", 1) or 1)
        return _record(
            expectation,
            "passed" if row_count >= minimum else "failed",
            f"row_count={row_count}, min={minimum}",
            observed={"row_count": row_count, "truncated": truncated},
        )
    values = [row.get(str(column)) for row in rows]
    if expectation_type == "not_null":
        nulls = sum(1 for value in values if _value_type(value) == "null")
        return _record(expectation, "passed" if nulls == 0 else "failed", f"null_count={nulls}", observed={"null_count": nulls})
    if expectation_type == "type":
        expected = str(params.get("type") or "")
        failures = [_value_type(value) for value in values if _value_type(value) != "null" and not _type_matches(_value_type(value), expected)]
        return _record(expectation, "passed" if not failures else "failed", f"type_failures={len(failures)}", observed={"failure_count": len(failures)})
    if expectation_type == "range":
        minimum = params.get("min")
        maximum = params.get("max")
        failures = []
        for value in values:
            if _value_type(value) == "null":
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                failures.append(value)
                continue
            if minimum is not None and numeric < float(minimum):
                failures.append(value)
            elif maximum is not None and numeric > float(maximum):
                failures.append(value)
        return _record(expectation, "passed" if not failures else "failed", f"range_failures={len(failures)}", observed={"failure_count": len(failures)})
    allowed = set(params.get("values", []))
    failures = [value for value in values if _value_type(value) != "null" and value not in allowed]
    return _record(expectation, "passed" if not failures else "failed", f"allowed_value_failures={len(failures)}", observed={"failure_count": len(failures)})


def _type_matches(observed: str, expected: str) -> bool:
    if expected == "float" and observed in {"float", "int"}:
        return True
    return observed == expected


def _record(expectation: dict[str, Any], status: str, message: str, observed: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "expectation_id": expectation.get("expectation_id"),
        "data_id": expectation.get("data_id"),
        "type": expectation.get("type"),
        "column": expectation.get("column"),
        "status": status,
        "message": message,
        "observed": observed or {},
    }


def _render_suite_markdown(suite: dict[str, Any]) -> str:
    lines = [
        "# Data Expectations",
        "",
        f"- schema_version: {suite['schema_version']}",
        f"- status: {suite['status']}",
        f"- expectation_count: {suite['expectation_count']}",
        "",
        "| Expectation | Data | Type | Column | Params |",
        "| --- | --- | --- | --- | --- |",
    ]
    for expectation in suite["expectations"]:
        lines.append(
            "| {expectation_id} | {data_id} | {kind} | {column} | {params} |".format(
                expectation_id=_cell(expectation.get("expectation_id")),
                data_id=_cell(expectation.get("data_id")),
                kind=_cell(expectation.get("type")),
                column=_cell(expectation.get("column")),
                params=_cell(expectation.get("params")),
            )
        )
    lines.extend(["", "## Policy", "", suite["policy"], ""])
    return "\n".join(lines)


def _render_results_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Data Expectation Results",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- expectation_count: {result['expectation_count']}",
        f"- passed_count: {result['passed_count']}",
        f"- failed_count: {result['failed_count']}",
        f"- top_failed_expectation: {result['top_failed_expectation']}",
        "",
        "| Expectation | Data | Type | Column | Status | Message |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in result["results"]:
        lines.append(
            "| {expectation_id} | {data_id} | {kind} | {column} | {status} | {message} |".format(
                expectation_id=_cell(record.get("expectation_id")),
                data_id=_cell(record.get("data_id")),
                kind=_cell(record.get("type")),
                column=_cell(record.get("column")),
                status=_cell(record.get("status")),
                message=_cell(record.get("message")),
            )
        )
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
