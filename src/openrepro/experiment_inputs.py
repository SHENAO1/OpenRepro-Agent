"""Experiment input mapping from verified candidate evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .approval import load_verified_candidates
from .experiment_templates import template_input_requirements
from .utils import iso_now, read_json, safe_write_text, write_json

EXPERIMENT_INPUTS_SCHEMA_VERSION = "0.9.2"


def _input_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def _parameter_value(candidate: dict[str, Any]) -> Any:
    if candidate.get("value_numeric") is not None:
        numeric = candidate["value_numeric"]
        return int(numeric) if isinstance(numeric, float) and numeric.is_integer() else numeric
    value = candidate.get("value")
    if isinstance(value, str):
        try:
            numeric = float(value)
            return int(numeric) if numeric.is_integer() else numeric
        except ValueError:
            return value
    return value


def _parse_input_value(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    if "," in stripped:
        return [_parse_input_value(item) for item in stripped.split(",")]
    try:
        numeric = float(stripped)
        return int(numeric) if numeric.is_integer() else numeric
    except ValueError:
        return stripped


def _formula_record(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "source_name": candidate.get("source_name"),
        "evidence": candidate.get("evidence"),
        "provenance": candidate.get("provenance"),
        "reviewer": candidate.get("reviewer"),
        "verification_note": candidate.get("verification_note"),
    }


def _parameter_record(candidate: dict[str, Any]) -> dict[str, Any]:
    name = str(candidate.get("name") or candidate.get("candidate_id") or "")
    input_name = _input_name(name)
    return {
        "candidate_id": candidate.get("candidate_id"),
        "input_name": input_name,
        "source_name": candidate.get("source_name"),
        "name": name,
        "value": candidate.get("value"),
        "value_numeric": candidate.get("value_numeric"),
        "unit": candidate.get("unit"),
        "unit_normalized": candidate.get("unit_normalized"),
        "mapped_value": _parameter_value(candidate),
        "provenance": candidate.get("provenance"),
        "reviewer": candidate.get("reviewer"),
        "verification_note": candidate.get("verification_note"),
    }


def build_experiment_inputs(project_dir: Path, experiment_id: str, template: str) -> dict[str, Any]:
    """Build structured experiment inputs from verified candidate artifacts."""
    verified = load_verified_candidates(project_dir)
    formulas = [_formula_record(item) for item in verified.get("formula_candidates", []) if isinstance(item, dict)]
    parameters = [
        _parameter_record(item) for item in verified.get("parameter_candidates", []) if isinstance(item, dict)
    ]
    parameter_values = {
        item["input_name"]: item["mapped_value"]
        for item in parameters
        if item.get("input_name") and item.get("mapped_value") is not None
    }
    input_sources = {
        item["input_name"]: {
            "source": "verified_candidate",
            "candidate_id": item.get("candidate_id"),
            "source_name": item.get("source_name"),
            "reviewer": item.get("reviewer"),
            "verification_note": item.get("verification_note"),
        }
        for item in parameters
        if item.get("input_name") and item.get("mapped_value") is not None
    }
    completeness = _input_completeness(template, parameter_values)
    return {
        "schema_version": EXPERIMENT_INPUTS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "updated_at": iso_now(),
        "experiment_id": experiment_id,
        "template": template,
        "verified_candidates_path": "workspace/verified_candidates.json" if verified else None,
        "formula_candidate_ids": [item.get("candidate_id") for item in formulas],
        "parameter_candidate_ids": [item.get("candidate_id") for item in parameters],
        "formulas": formulas,
        "parameters": parameters,
        "parameter_values": parameter_values,
        "input_sources": input_sources,
        "manual_overrides": [],
        "input_completeness": completeness,
        "policy": "Experiment inputs map human-verified candidates into implementation inputs; they do not prove reproduction success.",
    }


def write_experiment_inputs(project_dir: Path, experiment_id: str, exp_dir: Path, template: str) -> dict[str, Any]:
    """Write experiments/<id>/experiment_inputs.json and return the mapping."""
    inputs = build_experiment_inputs(project_dir, experiment_id, template)
    write_json(exp_dir / "experiment_inputs.json", inputs)
    return inputs


def _experiment_dir(project_dir: Path, experiment_id: str) -> Path:
    return Path(project_dir) / "experiments" / experiment_id


def _input_completeness(template: str, parameter_values: dict[str, Any]) -> dict[str, Any]:
    requirements = template_input_requirements(template)
    present = sorted(name for name in requirements["required"] if parameter_values.get(name) is not None)
    missing = sorted(set(requirements["required"]) - set(present))
    return {
        "status": "complete" if not missing else "needs_attention",
        "required": requirements["required"],
        "optional": requirements["optional"],
        "present": present,
        "missing": missing,
        "warning": (
            "Missing required template inputs; generated runner will use documented defaults."
            if missing
            else None
        ),
    }


def _load_or_create_inputs(project_dir: Path, experiment_id: str) -> tuple[Path, dict[str, Any]]:
    project_dir = Path(project_dir)
    exp_dir = _experiment_dir(project_dir, experiment_id)
    if not exp_dir.exists():
        raise FileNotFoundError(f"Experiment directory not found: {exp_dir}")
    config = read_json(exp_dir / "experiment_config.json", default={}) or {}
    template = str(config.get("template") or "basic") if isinstance(config, dict) else "basic"
    inputs_path = exp_dir / "experiment_inputs.json"
    inputs = read_json(inputs_path, default={}) or {}
    if not isinstance(inputs, dict) or not inputs:
        inputs = write_experiment_inputs(project_dir, experiment_id, exp_dir, template)
    return exp_dir, inputs


def refresh_experiment_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Refresh schema, timestamps, and completeness fields."""
    refreshed = dict(inputs)
    template = str(refreshed.get("template") or "basic")
    parameter_values = refreshed.get("parameter_values", {})
    if not isinstance(parameter_values, dict):
        parameter_values = {}
    refreshed["schema_version"] = EXPERIMENT_INPUTS_SCHEMA_VERSION
    refreshed["updated_at"] = iso_now()
    refreshed["parameter_values"] = parameter_values
    refreshed["input_sources"] = refreshed.get("input_sources", {}) if isinstance(refreshed.get("input_sources"), dict) else {}
    refreshed["manual_overrides"] = (
        refreshed.get("manual_overrides", []) if isinstance(refreshed.get("manual_overrides"), list) else []
    )
    refreshed["input_completeness"] = _input_completeness(template, parameter_values)
    return refreshed


def validate_experiment_inputs(project_dir: Path, experiment_id: str) -> dict[str, Any]:
    """Validate and refresh experiment input completeness."""
    project_dir = Path(project_dir)
    exp_dir, inputs = _load_or_create_inputs(project_dir, experiment_id)
    refreshed = refresh_experiment_inputs(inputs)
    write_json(exp_dir / "experiment_inputs.json", refreshed)
    completeness = refreshed["input_completeness"]
    source_counts: dict[str, int] = {}
    for source in refreshed.get("input_sources", {}).values():
        if isinstance(source, dict):
            label = str(source.get("source") or "unknown")
            source_counts[label] = source_counts.get(label, 0) + 1
    result = {
        "schema_version": EXPERIMENT_INPUTS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "experiment_id": experiment_id,
        "experiment_inputs_path": str(exp_dir / "experiment_inputs.json"),
        "template": refreshed.get("template"),
        "status": completeness["status"],
        "required": completeness["required"],
        "optional": completeness["optional"],
        "present": completeness["present"],
        "missing": completeness["missing"],
        "source_counts": source_counts,
        "parameter_values": refreshed.get("parameter_values", {}),
        "policy": "Input validation checks engineering completeness only; it does not verify scientific correctness.",
    }
    write_json(project_dir / "workspace" / "experiment_input_validation.json", result)
    safe_write_text(project_dir / "workspace" / "EXPERIMENT_INPUT_VALIDATION.md", _render_validation_markdown(result))
    return result


def set_experiment_input(
    project_dir: Path,
    experiment_id: str,
    name: str,
    value: str,
    source: str = "manual_override",
    note: str = "",
) -> dict[str, Any]:
    """Set or override an experiment input value."""
    if source not in {"manual_override", "verified_candidate", "default"}:
        raise ValueError("Input source must be manual_override, verified_candidate, or default.")
    project_dir = Path(project_dir)
    exp_dir, inputs = _load_or_create_inputs(project_dir, experiment_id)
    refreshed = refresh_experiment_inputs(inputs)
    input_name = _input_name(name)
    parsed_value = _parse_input_value(value)
    refreshed["parameter_values"][input_name] = parsed_value
    refreshed["input_sources"][input_name] = {
        "source": source,
        "set_at": iso_now(),
        "note": note,
    }
    if source == "manual_override":
        refreshed["manual_overrides"].append(
            {
                "name": input_name,
                "value": parsed_value,
                "set_at": iso_now(),
                "note": note,
            }
        )
    refreshed = refresh_experiment_inputs(refreshed)
    write_json(exp_dir / "experiment_inputs.json", refreshed)
    return validate_experiment_inputs(project_dir, experiment_id)


def _render_validation_markdown(result: dict[str, Any]) -> str:
    return f"""# Experiment Input Validation

- experiment_id: {result['experiment_id']}
- status: {result['status']}
- required: {result['required']}
- present: {result['present']}
- missing: {result['missing']}
- source_counts: {result['source_counts']}

## Parameter Values

```json
{json.dumps(result['parameter_values'], indent=2, ensure_ascii=False)}
```

## Policy

{result['policy']}
"""
