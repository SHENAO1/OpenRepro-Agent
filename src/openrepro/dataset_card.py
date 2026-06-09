"""Dataset cards and data quality gates for registered project data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .data_expectations import data_expectations_summary, init_data_expectations, run_data_expectations
from .data_profile import _format, _read_rows, generate_data_profile
from .data_registry import data_index_summary, validate_data_index
from .utils import iso_now, read_json, safe_write_text, write_json

DATASET_CARD_SCHEMA_VERSION = "1.55.0"
DATA_QUALITY_GATE_SCHEMA_VERSION = "1.55.0"
LABEL_COLUMN_HINTS = {"label", "target", "class", "category", "outcome", "y"}
SPLIT_COLUMN_HINTS = {"split", "subset", "fold", "partition"}


def generate_dataset_card(project_dir: Path, *, max_rows: int = 5000) -> dict[str, Any]:
    """Generate a lightweight dataset card from registered data and profiles."""
    project_dir = Path(project_dir)
    data_validation = validate_data_index(project_dir)
    profile = generate_data_profile(project_dir, max_rows=max_rows)
    expectations = data_expectations_summary(project_dir)
    registry = data_index_summary(project_dir)
    profile_sources = {str(source.get("data_id")): source for source in profile.get("sources", [])}
    datasets = [
        _dataset_entry(source, profile_sources.get(str(source.get("data_id"))), max_rows=max_rows)
        for source in registry.get("sources", [])
    ]
    warning_count = sum(len(item.get("warnings", [])) for item in datasets)
    error_count = sum(len(item.get("errors", [])) for item in datasets)
    label_dataset_count = sum(1 for item in datasets if item.get("label_columns"))
    split_dataset_count = sum(1 for item in datasets if item.get("split_columns"))
    card = {
        "schema_version": DATASET_CARD_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "empty" if not datasets else "needs_review" if error_count else "ready_with_warnings" if warning_count else "ready",
        "dataset_count": len(datasets),
        "registered_count": registry.get("registered_count", 0),
        "valid_registered_count": registry.get("valid_count", 0),
        "invalid_registered_count": registry.get("invalid_count", 0),
        "profiled_dataset_count": sum(1 for item in datasets if item.get("profiled")),
        "label_dataset_count": label_dataset_count,
        "split_dataset_count": split_dataset_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "data_validation_status": "passed" if data_validation.get("valid") else "failed",
        "data_profile_status": profile.get("status"),
        "data_expectations_status": expectations.get("status"),
        "datasets": datasets,
        "policy": "Dataset cards describe registered file structure and lightweight statistics only; they do not verify dataset semantics, labels, provenance claims, or scientific data quality.",
    }
    write_json(project_dir / "workspace" / "dataset_card.json", card)
    safe_write_text(project_dir / "workspace" / "DATASET_CARD.md", _render_dataset_card(card))
    return card


def dataset_card_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing dataset card summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "dataset_card.json"
    markdown_path = project_dir / "workspace" / "DATASET_CARD.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "dataset_count": int(data.get("dataset_count", 0) or 0),
        "profiled_dataset_count": int(data.get("profiled_dataset_count", 0) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "error_count": int(data.get("error_count", 0) or 0),
    }


def run_data_quality_gate(
    project_dir: Path,
    *,
    max_rows: int = 100000,
    max_missing_ratio: float = 0.5,
    max_duplicate_ratio: float = 0.2,
) -> dict[str, Any]:
    """Run the project data quality gate and write JSON/Markdown artifacts."""
    project_dir = Path(project_dir)
    registry_validation = validate_data_index(project_dir)
    profile = generate_data_profile(project_dir, max_rows=max_rows)
    suite = init_data_expectations(project_dir, overwrite=False, max_rows=min(max_rows, 5000))
    expectation_results = run_data_expectations(project_dir, max_rows=max_rows)
    dataset_card = generate_dataset_card(project_dir, max_rows=min(max_rows, 5000))
    checks = _quality_checks(
        registry_validation,
        profile,
        suite,
        expectation_results,
        dataset_card,
        max_missing_ratio=max_missing_ratio,
        max_duplicate_ratio=max_duplicate_ratio,
    )
    failed = [check for check in checks if check["status"] == "failed"]
    warnings = [check for check in checks if check["status"] == "warning"]
    result = {
        "schema_version": DATA_QUALITY_GATE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "passed" if not failed else "failed",
        "valid": not failed,
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check["status"] == "passed"),
        "warning_count": len(warnings),
        "failed_count": len(failed),
        "top_failed_check": failed[0]["check_id"] if failed else None,
        "max_missing_ratio": max_missing_ratio,
        "max_duplicate_ratio": max_duplicate_ratio,
        "dataset_card_status": dataset_card.get("status"),
        "data_profile_status": profile.get("status"),
        "data_expectations_status": expectation_results.get("status"),
        "checks": checks,
        "policy": "Data quality gates are lightweight structural checks only; they do not verify dataset semantics, labels, provenance claims, or scientific correctness.",
    }
    write_json(project_dir / "workspace" / "data_quality_gate.json", result)
    safe_write_text(project_dir / "workspace" / "DATA_QUALITY_GATE.md", _render_data_quality_gate(result))
    return result


def data_quality_gate_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing data quality gate summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "data_quality_gate.json"
    markdown_path = project_dir / "workspace" / "DATA_QUALITY_GATE.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "valid": bool(data.get("valid")) if path.exists() else False,
        "check_count": int(data.get("check_count", 0) or 0),
        "failed_count": int(data.get("failed_count", 0) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "top_failed_check": data.get("top_failed_check"),
        "top_command": None if data.get("status") == "passed" else f"openrepro data-quality run {project_dir}",
    }


def _dataset_entry(source: dict[str, Any], profile_source: dict[str, Any] | None, *, max_rows: int) -> dict[str, Any]:
    profile_source = profile_source or {}
    columns = list(profile_source.get("columns", [])) if isinstance(profile_source.get("columns"), list) else []
    column_names = [str(column.get("name")) for column in columns]
    label_columns = [name for name in column_names if name.strip().lower() in LABEL_COLUMN_HINTS]
    split_columns = [name for name in column_names if name.strip().lower() in SPLIT_COLUMN_HINTS]
    duplicate = _duplicate_summary(source, profile_source, max_rows=max_rows)
    warnings = list(profile_source.get("warnings", [])) if isinstance(profile_source.get("warnings"), list) else []
    errors = list(profile_source.get("errors", [])) if isinstance(profile_source.get("errors"), list) else []
    max_null_ratio = max([float(column.get("null_ratio", 0) or 0) for column in columns], default=0.0)
    if duplicate.get("duplicate_ratio_sampled", 0) > 0:
        warnings.append(f"Sample contains duplicate rows: ratio={duplicate['duplicate_ratio_sampled']}")
    return {
        "data_id": source.get("data_id"),
        "role": source.get("role"),
        "status": source.get("status"),
        "path": source.get("registered_path") or source.get("path"),
        "resolved_path": source.get("path"),
        "path_mode": source.get("path_mode"),
        "size_bytes": source.get("size_bytes"),
        "sha256": source.get("sha256"),
        "format": profile_source.get("format"),
        "profiled": bool(profile_source.get("profiled")),
        "row_count": int(profile_source.get("row_count", 0) or 0),
        "sampled_row_count": int(profile_source.get("sampled_row_count", 0) or 0),
        "truncated": bool(profile_source.get("truncated")),
        "column_count": len(columns),
        "columns": [_column_card(column) for column in columns],
        "label_columns": label_columns,
        "split_columns": split_columns,
        "max_null_ratio": max_null_ratio,
        "duplicate_summary": duplicate,
        "warnings": warnings,
        "errors": errors,
    }


def _column_card(column: dict[str, Any]) -> dict[str, Any]:
    numeric = column.get("numeric", {}) if isinstance(column.get("numeric"), dict) else {}
    return {
        "name": column.get("name"),
        "dominant_type": column.get("dominant_type"),
        "null_count": column.get("null_count"),
        "null_ratio": column.get("null_ratio"),
        "distinct_count_sampled": column.get("distinct_count_sampled"),
        "numeric_min": numeric.get("min"),
        "numeric_max": numeric.get("max"),
        "numeric_mean": numeric.get("mean"),
    }


def _duplicate_summary(source: dict[str, Any], profile_source: dict[str, Any], *, max_rows: int) -> dict[str, Any]:
    path = Path(str(source.get("path") or ""))
    data_format = str(profile_source.get("format") or _format(path))
    if data_format not in {"csv", "tsv", "json", "jsonl"} or source.get("status") != "current":
        return {"checked": False, "sampled_row_count": 0, "duplicate_count_sampled": 0, "duplicate_ratio_sampled": 0.0}
    try:
        rows, _row_count, _truncated, warnings = _read_rows(path, data_format, max_rows=max_rows)
    except Exception:
        return {"checked": False, "sampled_row_count": 0, "duplicate_count_sampled": 0, "duplicate_ratio_sampled": 0.0}
    if warnings or not rows:
        return {"checked": not warnings, "sampled_row_count": len(rows), "duplicate_count_sampled": 0, "duplicate_ratio_sampled": 0.0}
    seen: set[str] = set()
    duplicate_count = 0
    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            duplicate_count += 1
        else:
            seen.add(key)
    return {
        "checked": True,
        "sampled_row_count": len(rows),
        "duplicate_count_sampled": duplicate_count,
        "duplicate_ratio_sampled": round(duplicate_count / len(rows), 4) if rows else 0.0,
    }


def _quality_checks(
    registry_validation: dict[str, Any],
    profile: dict[str, Any],
    suite: dict[str, Any],
    expectation_results: dict[str, Any],
    dataset_card: dict[str, Any],
    *,
    max_missing_ratio: float,
    max_duplicate_ratio: float,
) -> list[dict[str, Any]]:
    datasets = list(dataset_card.get("datasets", []))
    checks = [
        _check(
            "registry_current",
            "Registered data files exist and match recorded SHA-256 hashes.",
            "passed" if registry_validation.get("valid") and datasets else "failed",
            "blocking",
            {
                "registered_count": dataset_card.get("registered_count"),
                "invalid_registered_count": dataset_card.get("invalid_registered_count"),
                "errors": registry_validation.get("errors", []),
            },
        ),
        _check(
            "profile_generated",
            "Registered data profile generated without parser errors.",
            "passed" if profile.get("error_count", 0) == 0 and dataset_card.get("profiled_dataset_count", 0) > 0 else "failed",
            "blocking",
            {
                "profiled_dataset_count": dataset_card.get("profiled_dataset_count"),
                "error_count": profile.get("error_count"),
                "status": profile.get("status"),
            },
        ),
        _check(
            "expectations_passed",
            "Configured lightweight data expectations passed.",
            "passed" if expectation_results.get("status") == "passed" and expectation_results.get("expectation_count", 0) > 0 else "failed",
            "blocking",
            {
                "expectation_count": expectation_results.get("expectation_count"),
                "failed_count": expectation_results.get("failed_count"),
                "top_failed_expectation": expectation_results.get("top_failed_expectation"),
                "suite_status": suite.get("status"),
            },
        ),
    ]
    empty_datasets = [item.get("data_id") for item in datasets if item.get("profiled") and int(item.get("row_count", 0) or 0) == 0]
    checks.append(
        _check(
            "non_empty_datasets",
            "Profiled datasets have at least one row.",
            "passed" if not empty_datasets and datasets else "failed",
            "blocking",
            {"empty_datasets": empty_datasets},
        )
    )
    high_missing = [
        {
            "data_id": item.get("data_id"),
            "max_null_ratio": item.get("max_null_ratio"),
        }
        for item in datasets
        if float(item.get("max_null_ratio", 0) or 0) > max_missing_ratio
    ]
    checks.append(
        _check(
            "missingness_within_threshold",
            "No sampled column exceeds the configured missingness threshold.",
            "passed" if not high_missing else "failed",
            "blocking",
            {"max_missing_ratio": max_missing_ratio, "datasets": high_missing},
        )
    )
    high_duplicates = [
        {
            "data_id": item.get("data_id"),
            "duplicate_ratio_sampled": (item.get("duplicate_summary") or {}).get("duplicate_ratio_sampled"),
        }
        for item in datasets
        if float((item.get("duplicate_summary") or {}).get("duplicate_ratio_sampled", 0) or 0) > max_duplicate_ratio
    ]
    checks.append(
        _check(
            "duplicates_within_threshold",
            "No sampled dataset exceeds the configured duplicate-row threshold.",
            "passed" if not high_duplicates else "failed",
            "blocking",
            {"max_duplicate_ratio": max_duplicate_ratio, "datasets": high_duplicates},
        )
    )
    checks.append(
        _check(
            "label_column_detected",
            "At least one registered dataset has a label or target-like column.",
            "passed" if dataset_card.get("label_dataset_count", 0) > 0 else "warning",
            "warning",
            {"label_dataset_count": dataset_card.get("label_dataset_count")},
        )
    )
    checks.append(
        _check(
            "split_column_detected",
            "At least one registered dataset has a split, subset, fold, or partition column.",
            "passed" if dataset_card.get("split_dataset_count", 0) > 0 else "warning",
            "warning",
            {"split_dataset_count": dataset_card.get("split_dataset_count")},
        )
    )
    return checks


def _check(check_id: str, label: str, status: str, severity: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "label": label,
        "status": status,
        "severity": severity,
        "details": details,
    }


def _render_dataset_card(card: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {data_id} | {role} | {status} | {fmt} | {rows} | {cols} | {labels} | {splits} | {dupes} |".format(
            data_id=_cell(item.get("data_id")),
            role=_cell(item.get("role")),
            status=_cell(item.get("status")),
            fmt=_cell(item.get("format")),
            rows=_cell(item.get("row_count")),
            cols=_cell(item.get("column_count")),
            labels=_cell(", ".join(item.get("label_columns", []))),
            splits=_cell(", ".join(item.get("split_columns", []))),
            dupes=_cell((item.get("duplicate_summary") or {}).get("duplicate_ratio_sampled")),
        )
        for item in card["datasets"]
    )
    if not rows:
        rows = "| none |  |  |  | 0 | 0 |  |  |  |"
    column_sections = "\n".join(_render_dataset_columns(item) for item in card["datasets"])
    return f"""# Dataset Card

- schema_version: {card['schema_version']}
- status: {card['status']}
- dataset_count: {card['dataset_count']}
- profiled_dataset_count: {card['profiled_dataset_count']}
- label_dataset_count: {card['label_dataset_count']}
- split_dataset_count: {card['split_dataset_count']}
- warning_count: {card['warning_count']}
- error_count: {card['error_count']}

| Data ID | Role | Status | Format | Rows | Columns | Label columns | Split columns | Duplicate ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

{column_sections}

## Policy

{card['policy']}
"""


def _render_dataset_columns(dataset: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {name} | {kind} | {null_ratio} | {distinct} | {numeric} |".format(
            name=_cell(column.get("name")),
            kind=_cell(column.get("dominant_type")),
            null_ratio=_cell(column.get("null_ratio")),
            distinct=_cell(column.get("distinct_count_sampled")),
            numeric=_cell(_numeric_range(column)),
        )
        for column in dataset.get("columns", [])
    )
    if not rows:
        rows = "| none |  |  |  |  |"
    warnings = "; ".join(_cell(item) for item in dataset.get("warnings", [])) or "none"
    errors = "; ".join(_cell(item) for item in dataset.get("errors", [])) or "none"
    return f"""## Dataset: {dataset.get('data_id')}

- path: `{dataset.get('path')}`
- sha256: `{dataset.get('sha256')}`
- warnings: {warnings}
- errors: {errors}

| Column | Dominant type | Null ratio | Distinct sampled | Numeric range |
| --- | --- | --- | --- | --- |
{rows}
"""


def _render_data_quality_gate(result: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {check_id} | {status} | {severity} | {details} |".format(
            check_id=_cell(check.get("check_id")),
            status=_cell(check.get("status")),
            severity=_cell(check.get("severity")),
            details=_cell(check.get("details")),
        )
        for check in result["checks"]
    )
    return f"""# Data Quality Gate

- schema_version: {result['schema_version']}
- status: {result['status']}
- valid: {result['valid']}
- check_count: {result['check_count']}
- passed_count: {result['passed_count']}
- warning_count: {result['warning_count']}
- failed_count: {result['failed_count']}
- top_failed_check: {result['top_failed_check']}
- dataset_card_status: {result['dataset_card_status']}
- data_profile_status: {result['data_profile_status']}
- data_expectations_status: {result['data_expectations_status']}

| Check | Status | Severity | Details |
| --- | --- | --- | --- |
{rows}

## Policy

{result['policy']}
"""


def _numeric_range(column: dict[str, Any]) -> str:
    if column.get("numeric_min") is None and column.get("numeric_max") is None:
        return ""
    return f"{column.get('numeric_min')}..{column.get('numeric_max')}"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
