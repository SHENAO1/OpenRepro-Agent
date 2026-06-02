"""Human approval gate for candidate formulas and parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import iso_now, read_json, safe_write_text, write_json

APPROVAL_SCHEMA_VERSION = "0.5.0"


def _candidate_map(project_dir: Path, filename: str) -> dict[str, dict[str, Any]]:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    return {
        str(item.get("candidate_id")): item
        for item in candidates
        if isinstance(item, dict) and item.get("candidate_id")
    }


def _select_candidates(
    available: dict[str, dict[str, Any]],
    requested_ids: list[str],
    approve_all: bool,
    kind: str,
) -> list[dict[str, Any]]:
    if approve_all:
        selected = list(available.values())
    else:
        missing = [candidate_id for candidate_id in requested_ids if candidate_id not in available]
        if missing:
            raise ValueError(f"Unknown {kind} candidate id(s): {', '.join(missing)}")
        selected = [available[candidate_id] for candidate_id in requested_ids]
    return selected


def _verified_record(
    candidate: dict[str, Any],
    reviewer: str,
    verification_note: str,
    verified_at: str,
) -> dict[str, Any]:
    record = dict(candidate)
    record["status"] = "verified_by_human"
    record["verified_at"] = verified_at
    record["reviewer"] = reviewer
    record["verification_note"] = verification_note
    return record


def approve_candidates(
    project_dir: Path,
    formula_ids: list[str] | None = None,
    parameter_ids: list[str] | None = None,
    approve_all: bool = False,
    reviewer: str = "human",
    verification_note: str = "",
) -> dict[str, Any]:
    """Promote selected candidate formulas/parameters into verified evidence."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    formula_ids = formula_ids or []
    parameter_ids = parameter_ids or []
    if not approve_all and not formula_ids and not parameter_ids:
        raise ValueError("Select candidates with --formula-id/--parameter-id or use --all.")

    formulas = _candidate_map(project_dir, "formula_candidates.json")
    parameters = _candidate_map(project_dir, "parameter_candidates.json")
    selected_formulas = _select_candidates(formulas, formula_ids, approve_all, "formula")
    selected_parameters = _select_candidates(parameters, parameter_ids, approve_all, "parameter")
    if approve_all and not selected_formulas and not selected_parameters:
        raise ValueError("No candidate formulas or parameters are available. Run `openrepro analyze` first.")

    verified_at = iso_now()
    note = verification_note or "Human reviewer approved candidate for guarded experiment scaffolding."
    verified_formulas = [_verified_record(item, reviewer, note, verified_at) for item in selected_formulas]
    verified_parameters = [_verified_record(item, reviewer, note, verified_at) for item in selected_parameters]
    status = "verified_candidates_available" if verified_formulas or verified_parameters else "no_candidates_verified"
    result = {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "created_at": verified_at,
        "status": status,
        "reviewer": reviewer,
        "verification_note": note,
        "formula_candidate_count": len(verified_formulas),
        "parameter_candidate_count": len(verified_parameters),
        "formula_candidate_ids": [item["candidate_id"] for item in verified_formulas],
        "parameter_candidate_ids": [item["candidate_id"] for item in verified_parameters],
        "formula_candidates": verified_formulas,
        "parameter_candidates": verified_parameters,
        "policy": (
            "Verified candidates are human-approved inputs for implementation work. "
            "They do not by themselves prove paper reproduction success."
        ),
    }

    workspace = project_dir / "workspace"
    write_json(workspace / "verified_candidates.json", result)
    safe_write_text(workspace / "VERIFIED_CANDIDATES.md", _render_verified_markdown(result))
    return result


def load_verified_candidates(project_dir: Path) -> dict[str, Any]:
    """Load the verified candidate artifact, if present."""
    data = read_json(Path(project_dir) / "workspace" / "verified_candidates.json", default={}) or {}
    return data if isinstance(data, dict) else {}


def _render_verified_markdown(result: dict[str, Any]) -> str:
    formula_lines = "\n".join(
        f"- {item.get('candidate_id')}: {item.get('evidence', '')}" for item in result.get("formula_candidates", [])
    ) or "- None"
    parameter_lines = "\n".join(
        f"- {item.get('candidate_id')}: {item.get('name')} = {item.get('value')} {item.get('unit', '')}".rstrip()
        for item in result.get("parameter_candidates", [])
    ) or "- None"
    return f"""# Verified Candidates

- status: {result['status']}
- reviewer: {result['reviewer']}
- created_at: {result['created_at']}
- formula_candidate_count: {result['formula_candidate_count']}
- parameter_candidate_count: {result['parameter_candidate_count']}

## Formula Candidates

{formula_lines}

## Parameter Candidates

{parameter_lines}

## Verification Note

{result['verification_note']}

## Policy

Verified candidates are human-approved inputs for implementation work. They do not by themselves prove paper reproduction success.
"""
