"""Experiment template metadata and scaffold inspection."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .utils import read_json

TEMPLATE_SCHEMA_VERSION = "0.9.2"
BASE_RUN_REQUIRED_ARTIFACTS = [
    "logs/run.log",
    "data/execution_result.json",
    "reports/experiment_report.md",
    "configs/experiment_config_snapshot.json",
    "configs/experiment_inputs_snapshot.json",
    "configs/environment_snapshot.json",
    "code/runner.py",
    "metadata.json",
]

EXPERIMENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "basic": {
        "name": "basic",
        "purpose": "Guarded placeholder runner for custom experiment implementation.",
        "use_case": "Use when the paper-specific implementation is not ready yet.",
        "required": [],
        "optional": ["data/metrics.json", "figures/result.png"],
        "input_hints": [],
        "required_inputs": [],
        "optional_inputs": [],
    },
    "boc-like": {
        "name": "boc-like",
        "purpose": "Starter runner for BOC-like signal traces and template metrics.",
        "use_case": "Use for GNSS/BOC-style notes after human-reviewed candidate inputs are available.",
        "required": ["data/metrics.json", "data/boc_trace.csv"],
        "optional": ["figures/result.png"],
        "input_hints": ["code_length", "noise_std", "seed"],
        "required_inputs": ["code_length", "noise_std"],
        "optional_inputs": ["seed"],
    },
    "numeric-sweep": {
        "name": "numeric-sweep",
        "purpose": "Starter runner for small numeric parameter sweeps.",
        "use_case": "Use when reviewed parameters should be explored across a small deterministic grid.",
        "required": ["data/metrics.json", "data/sweep.csv"],
        "optional": ["figures/result.png"],
        "input_hints": ["noise_std_values", "seed"],
        "required_inputs": [],
        "optional_inputs": ["noise_std", "noise_std_values", "seed"],
    },
}


def available_template_names() -> tuple[str, ...]:
    """Return supported experiment template names."""
    return tuple(EXPERIMENT_TEMPLATES)


def normalize_template(template: str) -> str:
    """Normalize and validate a user-supplied template name."""
    normalized = template.strip().lower().replace("_", "-")
    if normalized not in EXPERIMENT_TEMPLATES:
        supported = ", ".join(available_template_names())
        raise ValueError(f"Unsupported experiment template: {template}. Supported templates: {supported}.")
    return normalized


def normalize_artifact_paths(paths: Any) -> list[str]:
    """Normalize artifact paths for manifest and expected-artifact checks."""
    if not isinstance(paths, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for path in paths:
        item = str(path).strip().replace("\\", "/")
        if not item or item == "manifest.json" or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def template_expected_artifacts(template: str) -> dict[str, list[str]]:
    """Return required and optional artifacts for a template run."""
    template_name = normalize_template(template)
    metadata = EXPERIMENT_TEMPLATES[template_name]
    return {
        "required": normalize_artifact_paths(BASE_RUN_REQUIRED_ARTIFACTS + metadata["required"]),
        "optional": normalize_artifact_paths(metadata["optional"]),
    }


def template_input_requirements(template: str) -> dict[str, list[str]]:
    """Return required and optional input names for a template."""
    template_name = normalize_template(template)
    metadata = EXPERIMENT_TEMPLATES[template_name]
    return {
        "required": list(metadata["required_inputs"]),
        "optional": list(metadata["optional_inputs"]),
    }


def list_experiment_templates() -> list[dict[str, Any]]:
    """Return human-facing metadata for all supported experiment templates."""
    templates: list[dict[str, Any]] = []
    for name in available_template_names():
        metadata = EXPERIMENT_TEMPLATES[name]
        artifacts = template_expected_artifacts(name)
        templates.append(
            {
                "schema_version": TEMPLATE_SCHEMA_VERSION,
                "name": name,
                "purpose": metadata["purpose"],
                "use_case": metadata["use_case"],
                "required": artifacts["required"],
                "optional": artifacts["optional"],
                "input_hints": list(metadata["input_hints"]),
                "required_inputs": list(metadata["required_inputs"]),
                "optional_inputs": list(metadata["optional_inputs"]),
            }
        )
    return templates


def _scaffold_expected_status(exp_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = exp_dir / "expected_artifacts.json"
    expected = read_json(path, default=None)
    if not isinstance(expected, dict):
        return {
            "status": "missing",
            "path": str(path),
            "required_count": 0,
            "optional_count": 0,
            "issues": ["missing_expected_artifacts"],
        }

    template = str(config.get("template") or expected.get("template") or "basic")
    issues: list[str] = []
    try:
        expected_template = normalize_template(template)
    except ValueError:
        expected_template = template
        issues.append("unsupported_template")

    if expected.get("schema_version") != TEMPLATE_SCHEMA_VERSION:
        issues.append("legacy_expected_artifacts_schema")
    if expected.get("template") != expected_template:
        issues.append("expected_template_mismatch")

    required = normalize_artifact_paths(expected.get("required"))
    optional = normalize_artifact_paths(expected.get("optional"))
    if expected_template in EXPERIMENT_TEMPLATES:
        canonical = template_expected_artifacts(expected_template)
        missing_required = sorted(set(canonical["required"]) - set(required))
        extra_required = sorted(set(required) - set(canonical["required"]))
    else:
        missing_required = []
        extra_required = []
    if missing_required:
        issues.append("missing_expected_required_artifacts")
    if extra_required:
        issues.append("extra_expected_required_artifacts")

    return {
        "status": "valid" if not issues else "needs_attention",
        "path": str(path),
        "schema_version": expected.get("schema_version"),
        "template": expected_template,
        "required_count": len(required),
        "optional_count": len(optional),
        "missing_required": missing_required,
        "extra_required": extra_required,
        "issues": issues,
    }


def inspect_experiment_scaffolds(project_dir: Path) -> dict[str, Any]:
    """Inspect experiment scaffolds and summarize template/expected artifact state."""
    project_dir = Path(project_dir)
    experiments_dir = project_dir / "experiments"
    scaffolds: list[dict[str, Any]] = []
    if experiments_dir.exists():
        for exp_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
            config = read_json(exp_dir / "experiment_config.json", default={}) or {}
            config = config if isinstance(config, dict) else {}
            inputs = read_json(exp_dir / "experiment_inputs.json", default={}) or {}
            inputs = inputs if isinstance(inputs, dict) else {}
            completeness = inputs.get("input_completeness", {}) if inputs else {}
            template = str(config.get("template") or "basic")
            expected_status = _scaffold_expected_status(exp_dir, config)
            issues = []
            try:
                normalized_template = normalize_template(template)
            except ValueError:
                normalized_template = template
                issues.append("unsupported_template")
            issues.extend(expected_status["issues"])
            scaffolds.append(
                {
                    "experiment_id": exp_dir.name,
                    "experiment_dir": str(exp_dir),
                    "status": config.get("status", "unknown"),
                    "runnable": bool(config.get("runnable")),
                    "template": normalized_template,
                    "expected_artifacts_status": expected_status["status"],
                    "expected_required_count": expected_status["required_count"],
                    "expected_optional_count": expected_status["optional_count"],
                    "experiment_inputs_status": "present" if inputs else "missing",
                    "input_completeness_status": completeness.get("status", "missing"),
                    "missing_required_inputs": completeness.get("missing", []),
                    "issues": sorted(set(issues)),
                }
            )

    template_counts = Counter(item["template"] for item in scaffolds)
    issue_counts = Counter(issue for item in scaffolds for issue in item["issues"])
    completeness_counts = Counter(item["input_completeness_status"] for item in scaffolds)
    missing_required_input_count = sum(len(item.get("missing_required_inputs", [])) for item in scaffolds)
    valid_expected_count = sum(1 for item in scaffolds if item["expected_artifacts_status"] == "valid")
    return {
        "schema_version": TEMPLATE_SCHEMA_VERSION,
        "scaffold_count": len(scaffolds),
        "template_counts": dict(template_counts),
        "input_completeness_counts": dict(completeness_counts),
        "missing_required_input_count": missing_required_input_count,
        "expected_artifacts_valid_count": valid_expected_count,
        "expected_artifacts_attention_count": len(scaffolds) - valid_expected_count,
        "issue_counts": dict(issue_counts),
        "scaffolds": scaffolds,
    }
