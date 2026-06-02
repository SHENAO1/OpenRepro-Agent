"""Experiment input mapping from verified candidate evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .approval import load_verified_candidates
from .experiment_templates import template_input_requirements
from .utils import iso_now, write_json

EXPERIMENT_INPUTS_SCHEMA_VERSION = "0.9.0"


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
    requirements = template_input_requirements(template)
    present = sorted(name for name in requirements["required"] if parameter_values.get(name) is not None)
    missing = sorted(set(requirements["required"]) - set(present))
    completeness = {
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
    return {
        "schema_version": EXPERIMENT_INPUTS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "experiment_id": experiment_id,
        "template": template,
        "verified_candidates_path": "workspace/verified_candidates.json" if verified else None,
        "formula_candidate_ids": [item.get("candidate_id") for item in formulas],
        "parameter_candidate_ids": [item.get("candidate_id") for item in parameters],
        "formulas": formulas,
        "parameters": parameters,
        "parameter_values": parameter_values,
        "input_completeness": completeness,
        "policy": "Experiment inputs map human-verified candidates into implementation inputs; they do not prove reproduction success.",
    }


def write_experiment_inputs(project_dir: Path, experiment_id: str, exp_dir: Path, template: str) -> dict[str, Any]:
    """Write experiments/<id>/experiment_inputs.json and return the mapping."""
    inputs = build_experiment_inputs(project_dir, experiment_id, template)
    write_json(exp_dir / "experiment_inputs.json", inputs)
    return inputs
