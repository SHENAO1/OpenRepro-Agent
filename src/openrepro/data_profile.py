"""Registered data profiling and lightweight schema checks."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .data_registry import data_index_summary
from .utils import iso_now, read_json, safe_write_text, write_json

DATA_PROFILE_SCHEMA_VERSION = "1.33.0"
NULL_STRINGS = {"", "na", "n/a", "nan", "none", "null"}


def generate_data_profile(project_dir: Path, *, max_rows: int = 5000) -> dict[str, Any]:
    """Profile registered data files and write lightweight schema artifacts."""
    project_dir = Path(project_dir)
    limit = max(1, min(int(max_rows), 100000))
    data = data_index_summary(project_dir)
    sources = [_profile_source(source, max_rows=limit) for source in data.get("sources", [])]
    error_count = sum(len(source.get("errors", [])) for source in sources)
    warning_count = sum(len(source.get("warnings", [])) for source in sources)
    profiled_count = sum(1 for source in sources if source.get("profiled"))
    column_count = sum(len(source.get("columns", [])) for source in sources)
    profile = {
        "schema_version": DATA_PROFILE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "max_rows": limit,
        "status": "empty" if not sources else "failed" if error_count else "warning" if warning_count else "passed",
        "source_count": len(sources),
        "profiled_source_count": profiled_count,
        "column_count": column_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "sources": sources,
        "policy": "Data profiles inspect file structure and simple values only; they do not verify dataset semantics, labels, provenance claims, or scientific data quality.",
    }
    write_json(project_dir / "workspace" / "data_profile.json", profile)
    safe_write_text(project_dir / "workspace" / "DATA_PROFILE.md", _render_markdown(profile))
    return profile


def data_profile_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing data profile summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "data_profile.json"
    markdown_path = project_dir / "workspace" / "DATA_PROFILE.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "source_count": int(data.get("source_count", 0) or 0),
        "profiled_source_count": int(data.get("profiled_source_count", 0) or 0),
        "column_count": int(data.get("column_count", 0) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "error_count": int(data.get("error_count", 0) or 0),
    }


def _profile_source(source: dict[str, Any], *, max_rows: int) -> dict[str, Any]:
    path = Path(str(source.get("path") or ""))
    base = {
        "data_id": source.get("data_id"),
        "role": source.get("role"),
        "path": source.get("registered_path") or source.get("path"),
        "status": source.get("status"),
        "format": _format(path),
        "profiled": False,
        "row_count": 0,
        "sampled_row_count": 0,
        "truncated": False,
        "columns": [],
        "warnings": [],
        "errors": [],
    }
    if source.get("status") != "current":
        base["errors"].append(f"Registered data is not current: {source.get('status')}")
        return base
    try:
        rows, total_rows, truncated, warnings = _read_rows(path, base["format"], max_rows=max_rows)
    except Exception as exc:
        base["errors"].append(f"Could not profile data file: {exc}")
        return base
    base["warnings"].extend(warnings)
    base["profiled"] = base["format"] in {"csv", "tsv", "json", "jsonl"} and not base["errors"]
    base["row_count"] = total_rows
    base["sampled_row_count"] = len(rows)
    base["truncated"] = truncated
    base["columns"] = _columns(rows)
    if base["profiled"] and not base["columns"]:
        base["warnings"].append("No tabular columns were detected.")
    base["warnings"].extend(_schema_warnings(base))
    return base


def _format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".tsv":
        return "tsv"
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".json":
        return "json"
    return "unsupported"


def _read_rows(path: Path, data_format: str, *, max_rows: int) -> tuple[list[dict[str, Any]], int, bool, list[str]]:
    if data_format in {"csv", "tsv"}:
        return _read_delimited(path, delimiter="," if data_format == "csv" else "\t", max_rows=max_rows)
    if data_format == "json":
        return _read_json(path, max_rows=max_rows)
    if data_format == "jsonl":
        return _read_jsonl(path, max_rows=max_rows)
    return [], 0, False, [f"Unsupported data format for profiling: {path.suffix or 'no suffix'}"]


def _read_delimited(path: Path, *, delimiter: str, max_rows: int) -> tuple[list[dict[str, Any]], int, bool, list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return [], 0, False, ["Delimited file is empty."]
        duplicates = sorted({name for name in header if header.count(name) > 1 and name})
        if duplicates:
            warnings.append("Duplicate column names: " + ", ".join(duplicates))
        for total, values in enumerate(reader, start=1):
            if len(rows) < max_rows:
                rows.append(_zip_row(header, values))
        total_rows = total if "total" in locals() else 0
    return rows, total_rows, total_rows > len(rows), warnings


def _zip_row(header: list[str], values: list[str]) -> dict[str, Any]:
    row = {header[index] if header[index] else f"column_{index + 1}": values[index] if index < len(values) else "" for index in range(len(header))}
    if len(values) > len(header):
        for index, value in enumerate(values[len(header) :], start=1):
            row[f"extra_{index}"] = value
    return row


def _read_json(path: Path, *, max_rows: int) -> tuple[list[dict[str, Any]], int, bool, list[str]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = _json_rows(payload)
    return rows[:max_rows], len(rows), len(rows) > max_rows, []


def _read_jsonl(path: Path, *, max_rows: int) -> tuple[list[dict[str, Any]], int, bool, list[str]]:
    rows: list[dict[str, Any]] = []
    total = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            total += 1
            payload = json.loads(line)
            row = payload if isinstance(payload, dict) else {"value": payload}
            if len(rows) < max_rows:
                rows.append(row)
    return rows, total, total > len(rows), []


def _json_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item if isinstance(item, dict) else {"value": item} for item in payload]
    if isinstance(payload, dict):
        return [payload]
    return [{"value": payload}]


def _columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = sorted({str(name) for row in rows for name in row})
    return [_column_profile(name, [row.get(name) for row in rows], row_count=len(rows)) for name in names]


def _column_profile(name: str, values: list[Any], *, row_count: int) -> dict[str, Any]:
    type_counts: dict[str, int] = {}
    numeric_values: list[float] = []
    string_lengths: list[int] = []
    distinct_values: set[str] = set()
    for value in values:
        value_type = _value_type(value)
        type_counts[value_type] = type_counts.get(value_type, 0) + 1
        if value_type in {"int", "float"}:
            numeric_values.append(float(value))
        if value_type == "string":
            string_lengths.append(len(str(value)))
        if value_type != "null" and len(distinct_values) <= 100:
            distinct_values.add(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    null_count = type_counts.get("null", 0)
    non_null = row_count - null_count
    result: dict[str, Any] = {
        "name": name,
        "row_count": row_count,
        "null_count": null_count,
        "non_null_count": non_null,
        "null_ratio": round(null_count / row_count, 4) if row_count else 0.0,
        "types": type_counts,
        "dominant_type": _dominant_type(type_counts),
        "distinct_count_sampled": min(len(distinct_values), 101),
    }
    if numeric_values:
        result["numeric"] = {
            "min": min(numeric_values),
            "max": max(numeric_values),
            "mean": round(sum(numeric_values) / len(numeric_values), 6),
        }
    if string_lengths:
        result["string"] = {"min_length": min(string_lengths), "max_length": max(string_lengths)}
    return result


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in NULL_STRINGS:
            return "null"
        if stripped.lower() in {"true", "false"}:
            return "bool"
        try:
            int(stripped)
        except ValueError:
            try:
                float(stripped)
            except ValueError:
                return "string"
            return "float"
        return "int"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _dominant_type(type_counts: dict[str, int]) -> str:
    non_null = {key: value for key, value in type_counts.items() if key != "null"}
    if not non_null:
        return "null"
    return sorted(non_null.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _schema_warnings(source: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if source.get("truncated"):
        warnings.append(f"Profile sampled first {source.get('sampled_row_count')} rows.")
    for column in source.get("columns", []):
        type_names = [name for name in column.get("types", {}) if name != "null"]
        if len(type_names) > 1:
            warnings.append(f"Column {column['name']} has mixed non-null types: {', '.join(sorted(type_names))}.")
        if column.get("null_ratio", 0) > 0.5:
            warnings.append(f"Column {column['name']} is more than 50% null.")
        if column.get("non_null_count", 0) > 1 and column.get("distinct_count_sampled") == 1:
            warnings.append(f"Column {column['name']} is constant in the sampled rows.")
    return warnings


def _render_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# Data Profile",
        "",
        f"- schema_version: {profile['schema_version']}",
        f"- status: {profile['status']}",
        f"- source_count: {profile['source_count']}",
        f"- profiled_source_count: {profile['profiled_source_count']}",
        f"- column_count: {profile['column_count']}",
        f"- warning_count: {profile['warning_count']}",
        f"- error_count: {profile['error_count']}",
        "",
        "## Sources",
        "",
        "| Data ID | Format | Status | Rows | Columns | Warnings | Errors |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for source in profile["sources"]:
        lines.append(
            "| {data_id} | {fmt} | {status} | {rows} | {columns} | {warnings} | {errors} |".format(
                data_id=_cell(source.get("data_id")),
                fmt=_cell(source.get("format")),
                status=_cell(source.get("status")),
                rows=_cell(source.get("row_count")),
                columns=_cell(len(source.get("columns", []))),
                warnings=_cell(len(source.get("warnings", []))),
                errors=_cell(len(source.get("errors", []))),
            )
        )
    for source in profile["sources"]:
        lines.extend(["", f"## Columns: {source.get('data_id')}", ""])
        if source.get("warnings"):
            lines.append("Warnings: " + "; ".join(_cell(item) for item in source["warnings"]))
            lines.append("")
        if source.get("errors"):
            lines.append("Errors: " + "; ".join(_cell(item) for item in source["errors"]))
            lines.append("")
        lines.extend(["| Column | Dominant type | Nulls | Null ratio | Distinct sampled | Numeric range |", "| --- | --- | --- | --- | --- | --- |"])
        for column in source.get("columns", []):
            numeric = column.get("numeric", {})
            numeric_range = f"{numeric.get('min')}..{numeric.get('max')}" if numeric else ""
            lines.append(
                "| {name} | {kind} | {nulls} | {null_ratio} | {distinct} | {numeric_range} |".format(
                    name=_cell(column.get("name")),
                    kind=_cell(column.get("dominant_type")),
                    nulls=_cell(column.get("null_count")),
                    null_ratio=_cell(column.get("null_ratio")),
                    distinct=_cell(column.get("distinct_count_sampled")),
                    numeric_range=_cell(numeric_range),
                )
            )
    lines.extend(["", "## Policy", "", profile["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
