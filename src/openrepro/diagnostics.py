"""Failure classification and repair suggestions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import latest_run_dir, validate_run_manifest
from .config import get_demo_config
from .document_loader import load_source_index
from .utils import iso_now


REPAIR_SUGGESTIONS: dict[str, str] = {
    "missing_artifact": "Re-run the producing command, then run `openrepro validate` again.",
    "manifest_mismatch": "The artifact changed after manifest creation; re-run the command or regenerate trusted artifacts.",
    "missing_manifest": "Run `openrepro run-demo`, `openrepro run-sweep`, or `openrepro benchmark` to create a manifest.",
    "invalid_task_schema": "Fix the benchmark task JSON so it includes all required fields.",
    "missing_source_file": "Check task source paths or ingest the missing source manually.",
    "pdf_extraction_failed": "Use a text-layer PDF, OCR the document, or add Markdown/txt notes for analysis.",
    "invalid_demo_config": "Fix project_config.yaml demo values, then rerun plan and demo commands.",
    "provider_disabled": "Use the default mock provider or explicitly enable a future real provider implementation.",
    "unknown_error": "Inspect logs and rerun the failing command with the smallest reproducible input.",
}


def classify_message(message: str) -> str:
    """Classify a validation or runtime message into a stable failure code."""
    lower = message.lower()
    if "sha-256 mismatch" in lower or "size mismatch" in lower:
        return "manifest_mismatch"
    if "manifest not found" in lower or "manifest" in lower and "invalid" in lower:
        return "missing_manifest"
    if "missing required artifact" in lower or "missing on disk" in lower:
        return "missing_artifact"
    if "schema" in lower and "task" in lower:
        return "invalid_task_schema"
    if "source file" in lower and "not found" in lower:
        return "missing_source_file"
    if "pdf" in lower and ("failed" in lower or "empty" in lower):
        return "pdf_extraction_failed"
    if "demo." in lower or "code_length" in lower or "noise_std" in lower:
        return "invalid_demo_config"
    if "provider" in lower and ("disabled" in lower or "not implemented" in lower):
        return "provider_disabled"
    return "unknown_error"


def issue(code: str, message: str, source: str = "diagnostics") -> dict[str, str]:
    """Create a normalized diagnosis issue."""
    return {
        "code": code,
        "source": source,
        "message": message,
        "repair_suggestion": REPAIR_SUGGESTIONS.get(code, REPAIR_SUGGESTIONS["unknown_error"]),
    }


def diagnose_validation_result(result: dict[str, Any]) -> list[dict[str, str]]:
    """Create diagnosis issues from a manifest validation result."""
    issues: list[dict[str, str]] = []
    for message in result.get("errors", []):
        issues.append(issue(classify_message(str(message)), str(message), source="manifest"))
    for message in result.get("warnings", []):
        issues.append(issue(classify_message(str(message)), str(message), source="manifest_warning"))
    return issues


def diagnose_error(message: str, source: str = "runtime") -> dict[str, str]:
    """Create one diagnosis issue from an exception or error message."""
    return issue(classify_message(message), message, source=source)


def _demo_config_issues(project_dir: Path) -> list[dict[str, str]]:
    config = get_demo_config(project_dir)
    checks = [
        (int(config.get("code_length", 0) or 0) <= 0, "demo.code_length must be positive"),
        (int(config.get("samples_per_chip", 0) or 0) <= 1, "demo.samples_per_chip must be greater than 1"),
        (
            int(config.get("subcarrier_cycles_per_chip", 0) or 0) <= 0,
            "demo.subcarrier_cycles_per_chip must be positive",
        ),
        (float(config.get("noise_std", -1) or 0) < 0, "demo.noise_std must be non-negative"),
    ]
    return [issue("invalid_demo_config", message, source="project_config") for failed, message in checks if failed]


def diagnose_project(project_dir: Path, run_dir: Path | None = None) -> dict[str, Any]:
    """Diagnose a project and optional run directory."""
    project_dir = Path(project_dir)
    issues: list[dict[str, str]] = []
    source_index = load_source_index(project_dir)
    sources = source_index.get("sources", [])
    if not sources:
        issues.append(issue("missing_source_file", "No sources have been ingested.", source="source_index"))
    for record in sources:
        if record.get("suffix") == ".pdf" and record.get("extraction_status") not in (None, "extracted"):
            issues.append(
                issue(
                    "pdf_extraction_failed",
                    f"PDF extraction needs review for {record.get('source_name')}: {record.get('status')}",
                    source="source_index",
                )
            )
    issues.extend(_demo_config_issues(project_dir))

    target = run_dir or latest_run_dir(project_dir)
    validation: dict[str, Any] | None = None
    if target is not None:
        validation = validate_run_manifest(target)
        if not validation.get("valid"):
            issues.extend(diagnose_validation_result(validation))

    return {
        "schema_version": "0.3.0",
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "run_dir": str(target) if target else None,
        "healthy": len(issues) == 0,
        "issues": issues,
        "validation": validation,
    }
