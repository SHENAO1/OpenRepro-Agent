"""Experiment specification contracts for scaffolded runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .experiment_templates import normalize_artifact_paths, template_input_requirements
from .utils import iso_now, read_json, safe_write_text, write_json

EXPERIMENT_SPEC_SCHEMA_VERSION = "1.2.0"

TEMPLATE_METRICS = {
    "basic": [],
    "boc-like": ["template", "seed", "code_length", "noise_std", "mean_correlation", "signal_energy"],
    "numeric-sweep": ["template", "sweep_count", "best_noise_std", "best_stability_score"],
}


def _experiment_dir(project_dir: Path, experiment_id: str) -> Path:
    return Path(project_dir) / "experiments" / experiment_id


def build_experiment_spec(
    project_dir: Path,
    experiment_id: str,
    config: dict[str, Any],
    inputs: dict[str, Any],
    expected_artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Build a stable experiment specification contract."""
    template = str(config.get("template") or inputs.get("template") or expected_artifacts.get("template") or "basic")
    requirements = template_input_requirements(template)
    return {
        "schema_version": EXPERIMENT_SPEC_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "experiment_id": experiment_id,
        "template": template,
        "status": "candidate_contract",
        "source_files": config.get("source_files", []),
        "candidate_ids": {
            "formula": config.get("formula_candidate_ids", []),
            "parameter": config.get("parameter_candidate_ids", []),
            "verified_formula": config.get("verified_formula_candidate_ids", []),
            "verified_parameter": config.get("verified_parameter_candidate_ids", []),
        },
        "input_contract": {
            "required": requirements["required"],
            "optional": requirements["optional"],
            "parameter_values": inputs.get("parameter_values", {}),
            "input_completeness": inputs.get("input_completeness", {}),
        },
        "runner_contract": {
            "runner": "runner.py",
            "required_status": "verified_inputs_ready",
            "requires_confirm": True,
        },
        "artifact_contract": {
            "required": normalize_artifact_paths(expected_artifacts.get("required")),
            "optional": normalize_artifact_paths(expected_artifacts.get("optional")),
        },
        "metric_contract": {
            "required_metrics": TEMPLATE_METRICS.get(template, []),
            "comparison_policy": "Metrics are compared as engineering evidence only.",
        },
        "policy": "Experiment specs define execution contracts only; they do not verify scientific correctness.",
    }


def write_experiment_spec(project_dir: Path, experiment_id: str, exp_dir: Path) -> dict[str, Any]:
    """Write experiments/<id>/experiment_spec.json."""
    config = read_json(exp_dir / "experiment_config.json", default={}) or {}
    inputs = read_json(exp_dir / "experiment_inputs.json", default={}) or {}
    expected = read_json(exp_dir / "expected_artifacts.json", default={}) or {}
    spec = build_experiment_spec(project_dir, experiment_id, config, inputs, expected)
    write_json(exp_dir / "experiment_spec.json", spec)
    return spec


def validate_experiment_spec(project_dir: Path, experiment_id: str) -> dict[str, Any]:
    """Validate an experiment spec against scaffold config, inputs, and expected artifacts."""
    project_dir = Path(project_dir)
    exp_dir = _experiment_dir(project_dir, experiment_id)
    spec_path = exp_dir / "experiment_spec.json"
    if not spec_path.exists():
        write_experiment_spec(project_dir, experiment_id, exp_dir)
    spec = read_json(spec_path, default={}) or {}
    config = read_json(exp_dir / "experiment_config.json", default={}) or {}
    inputs = read_json(exp_dir / "experiment_inputs.json", default={}) or {}
    expected = read_json(exp_dir / "expected_artifacts.json", default={}) or {}
    current_spec = build_experiment_spec(project_dir, experiment_id, config, inputs, expected)
    if (
        not isinstance(spec, dict)
        or spec.get("template") != current_spec.get("template")
        or spec.get("input_contract") != current_spec.get("input_contract")
        or spec.get("artifact_contract") != current_spec.get("artifact_contract")
    ):
        spec = current_spec
        write_json(spec_path, spec)
    errors: list[str] = []
    warnings: list[str] = []

    if spec.get("schema_version") != EXPERIMENT_SPEC_SCHEMA_VERSION:
        warnings.append(f"Spec schema is {spec.get('schema_version')!r}; expected {EXPERIMENT_SPEC_SCHEMA_VERSION!r}.")
    if spec.get("experiment_id") != experiment_id:
        errors.append("Spec experiment_id does not match requested experiment.")
    if spec.get("template") != config.get("template"):
        errors.append("Spec template does not match experiment_config.json.")
    if spec.get("runner_contract", {}).get("required_status") != config.get("status"):
        errors.append("Spec required_status does not match current experiment status.")

    input_contract = spec.get("input_contract", {}) if isinstance(spec.get("input_contract"), dict) else {}
    completeness = inputs.get("input_completeness", {}) if isinstance(inputs, dict) else {}
    missing = completeness.get("missing", []) if isinstance(completeness, dict) else []
    if missing:
        warnings.append(f"Experiment inputs are missing required values: {missing}")
    required_inputs = set(input_contract.get("required", []))
    actual_required_inputs = set(template_input_requirements(str(config.get("template") or "basic"))["required"])
    if required_inputs != actual_required_inputs:
        errors.append("Spec input requirements do not match template registry.")

    artifact_contract = spec.get("artifact_contract", {}) if isinstance(spec.get("artifact_contract"), dict) else {}
    expected_required = set(normalize_artifact_paths(expected.get("required")))
    spec_required = set(normalize_artifact_paths(artifact_contract.get("required")))
    if spec_required != expected_required:
        errors.append("Spec required artifacts do not match expected_artifacts.json.")

    result = {
        "schema_version": EXPERIMENT_SPEC_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "experiment_id": experiment_id,
        "experiment_spec_path": str(spec_path),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "spec_sha256": sha256_file(spec_path) if spec_path.exists() else None,
        "policy": "Spec validation checks engineering contracts only; it does not verify scientific correctness.",
    }
    write_json(project_dir / "workspace" / "experiment_spec_validation.json", result)
    safe_write_text(project_dir / "workspace" / "EXPERIMENT_SPEC_VALIDATION.md", _render_validation_markdown(result))
    return result


def _render_validation_markdown(result: dict[str, Any]) -> str:
    return f"""# Experiment Spec Validation

- experiment_id: {result['experiment_id']}
- valid: {result['valid']}
- spec_sha256: {result['spec_sha256']}
- errors: {result['errors']}
- warnings: {result['warnings']}

## Policy

{result['policy']}
"""
