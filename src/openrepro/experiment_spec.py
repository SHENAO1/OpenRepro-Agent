"""Experiment specification contracts for scaffolded runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .data_registry import data_contract
from .experiment_templates import normalize_artifact_paths, template_input_requirements
from .utils import iso_now, read_json, safe_write_text, write_json

EXPERIMENT_SPEC_SCHEMA_VERSION = "1.6.0"

TEMPLATE_METRICS = {
    "basic": [],
    "boc-like": ["template", "seed", "code_length", "noise_std", "mean_correlation", "signal_energy"],
    "numeric-sweep": ["template", "sweep_count", "best_noise_std", "best_stability_score"],
    "random-search-toy": ["template", "trial_count", "dimension_count", "random_best_loss", "grid_best_loss", "random_better"],
}


def _stable_hash(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _experiment_dir(project_dir: Path, experiment_id: str) -> Path:
    return Path(project_dir) / "experiments" / experiment_id


def _spec_source_payload(
    experiment_id: str,
    config: dict[str, Any],
    inputs: dict[str, Any],
    expected_artifacts: dict[str, Any],
    data_sources: dict[str, Any],
) -> dict[str, Any]:
    template = str(config.get("template") or inputs.get("template") or expected_artifacts.get("template") or "basic")
    requirements = template_input_requirements(template)
    return {
        "experiment_id": experiment_id,
        "template": template,
        "status": config.get("status"),
        "runnable": config.get("runnable"),
        "source_files": config.get("source_files", []),
        "candidate_ids": {
            "formula": config.get("formula_candidate_ids", []),
            "parameter": config.get("parameter_candidate_ids", []),
            "verified_formula": config.get("verified_formula_candidate_ids", []),
            "verified_parameter": config.get("verified_parameter_candidate_ids", []),
        },
        "claim_contract": {
            "claim_ids": sorted(
                {
                    *(f"formula:{item}" for item in config.get("formula_candidate_ids", []) if item),
                    *(f"parameter:{item}" for item in config.get("parameter_candidate_ids", []) if item),
                }
            ),
            "verified_claim_ids": sorted(
                {
                    *(f"formula:{item}" for item in config.get("verified_formula_candidate_ids", []) if item),
                    *(f"parameter:{item}" for item in config.get("verified_parameter_candidate_ids", []) if item),
                }
            ),
        },
        "input_contract": {
            "required": requirements["required"],
            "optional": requirements["optional"],
            "parameter_values": inputs.get("parameter_values", {}),
            "input_completeness": inputs.get("input_completeness", {}),
        },
        "artifact_contract": {
            "required": normalize_artifact_paths(expected_artifacts.get("required")),
            "optional": normalize_artifact_paths(expected_artifacts.get("optional")),
        },
        "metric_contract": {
            "required_metrics": TEMPLATE_METRICS.get(template, []),
        },
        "data_contract": data_sources,
    }


def build_experiment_spec(
    project_dir: Path,
    experiment_id: str,
    config: dict[str, Any],
    inputs: dict[str, Any],
    expected_artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Build a stable experiment specification contract."""
    source_payload = _spec_source_payload(experiment_id, config, inputs, expected_artifacts, data_contract(project_dir))
    template = str(source_payload["template"])
    input_contract = source_payload["input_contract"]
    artifact_contract = source_payload["artifact_contract"]
    metric_contract = source_payload["metric_contract"]
    data_sources = source_payload["data_contract"]
    claim_contract = source_payload["claim_contract"]
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
        "input_contract": input_contract,
        "runner_contract": {
            "runner": "runner.py",
            "required_status": "verified_inputs_ready",
            "requires_confirm": True,
        },
        "artifact_contract": artifact_contract,
        "metric_contract": {
            "required_metrics": metric_contract["required_metrics"],
            "comparison_policy": "Metrics are compared as engineering evidence only.",
        },
        "data_contract": data_sources,
        "claim_contract": claim_contract,
        "source_fingerprint": {
            "schema_version": EXPERIMENT_SPEC_SCHEMA_VERSION,
            "sha256": _stable_hash(source_payload),
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


def _load_spec_inputs(project_dir: Path, experiment_id: str) -> tuple[Path, Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    exp_dir = _experiment_dir(project_dir, experiment_id)
    spec_path = exp_dir / "experiment_spec.json"
    config = read_json(exp_dir / "experiment_config.json", default={}) or {}
    inputs = read_json(exp_dir / "experiment_inputs.json", default={}) or {}
    expected = read_json(exp_dir / "expected_artifacts.json", default={}) or {}
    return exp_dir, spec_path, config, inputs, expected


def inspect_experiment_specs(project_dir: Path) -> dict[str, Any]:
    """Inspect spec freshness without mutating project files."""
    project_dir = Path(project_dir)
    experiments_dir = project_dir / "experiments"
    entries: list[dict[str, Any]] = []
    if not experiments_dir.exists():
        return {"schema_version": EXPERIMENT_SPEC_SCHEMA_VERSION, "specs": entries, "status_counts": {}, "stale_count": 0, "invalid_count": 0, "missing_count": 0}
    for exp_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
        experiment_id = exp_dir.name
        _, spec_path, config, inputs, expected = _load_spec_inputs(project_dir, experiment_id)
        current_spec = build_experiment_spec(project_dir, experiment_id, config, inputs, expected)
        spec = read_json(spec_path, default={}) or {}
        current_hash = current_spec["source_fingerprint"]["sha256"]
        package_hash = spec.get("source_fingerprint", {}).get("sha256") if isinstance(spec, dict) else None
        errors: list[str] = []
        if not spec_path.exists():
            status = "missing"
        elif spec.get("experiment_id") != experiment_id:
            status = "invalid"
            errors.append("Spec experiment_id does not match directory name.")
        elif spec.get("template") != config.get("template"):
            status = "invalid"
            errors.append("Spec template does not match experiment config.")
        elif package_hash != current_hash:
            status = "stale"
        else:
            status = "current"
        entries.append(
            {
                "experiment_id": experiment_id,
                "path": str(spec_path),
                "status": status,
                "stale": status == "stale",
                "valid": status in {"current", "stale"},
                "spec_sha256": sha256_file(spec_path) if spec_path.exists() else None,
                "package_source_sha256": package_hash,
                "current_source_sha256": current_hash,
                "errors": errors,
            }
        )
    status_counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema_version": EXPERIMENT_SPEC_SCHEMA_VERSION,
        "specs": entries,
        "status_counts": status_counts,
        "stale_count": status_counts.get("stale", 0),
        "invalid_count": status_counts.get("invalid", 0),
        "missing_count": status_counts.get("missing", 0),
    }


def validate_experiment_spec(
    project_dir: Path,
    experiment_id: str,
    strict: bool = False,
    refresh: bool | None = None,
) -> dict[str, Any]:
    """Validate an experiment spec against scaffold config, inputs, and expected artifacts."""
    project_dir = Path(project_dir)
    refresh = not strict if refresh is None else refresh
    exp_dir, spec_path, config, inputs, expected = _load_spec_inputs(project_dir, experiment_id)
    if not spec_path.exists():
        if refresh:
            write_experiment_spec(project_dir, experiment_id, exp_dir)
    spec = read_json(spec_path, default={}) or {}
    current_spec = build_experiment_spec(project_dir, experiment_id, config, inputs, expected)
    current_source_hash = current_spec["source_fingerprint"]["sha256"]
    spec_source_hash = spec.get("source_fingerprint", {}).get("sha256") if isinstance(spec, dict) else None
    stale = bool(spec_path.exists() and spec_source_hash != current_source_hash)
    if (
        refresh
        and (
            not isinstance(spec, dict)
            or spec.get("schema_version") != EXPERIMENT_SPEC_SCHEMA_VERSION
            or stale
            or spec.get("template") != current_spec.get("template")
            or spec.get("input_contract") != current_spec.get("input_contract")
            or spec.get("artifact_contract") != current_spec.get("artifact_contract")
        )
    ):
        spec = current_spec
        write_json(spec_path, spec)
        spec_source_hash = current_source_hash
        stale = False
    errors: list[str] = []
    warnings: list[str] = []

    if not spec_path.exists():
        errors.append("Experiment spec is missing.")
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
    if stale:
        warnings.append("Experiment spec is stale relative to current config, inputs, or expected artifacts.")
    strict_failed = strict and bool(warnings)

    result = {
        "schema_version": EXPERIMENT_SPEC_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "experiment_id": experiment_id,
        "experiment_spec_path": str(spec_path),
        "valid": not errors and not strict_failed,
        "strict": strict,
        "stale": stale,
        "freshness_status": "stale" if stale else "current" if spec_path.exists() else "missing",
        "errors": errors,
        "warnings": warnings,
        "spec_sha256": sha256_file(spec_path) if spec_path.exists() else None,
        "source_fingerprint": {
            "package_sha256": spec_source_hash,
            "current_sha256": current_source_hash,
        },
        "policy": "Spec validation checks engineering contracts only; it does not verify scientific correctness.",
    }
    write_json(project_dir / "workspace" / "experiment_spec_validation.json", result)
    safe_write_text(project_dir / "workspace" / "EXPERIMENT_SPEC_VALIDATION.md", _render_validation_markdown(result))
    return result


def _render_validation_markdown(result: dict[str, Any]) -> str:
    return f"""# Experiment Spec Validation

- experiment_id: {result['experiment_id']}
- valid: {result['valid']}
- strict: {result['strict']}
- freshness_status: {result['freshness_status']}
- spec_sha256: {result['spec_sha256']}
- errors: {result['errors']}
- warnings: {result['warnings']}

## Policy

{result['policy']}
"""
