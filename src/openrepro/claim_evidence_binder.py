"""Bind traced claims to workflow evidence records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_trace import generate_claim_trace, validate_claim_trace
from .protocol_coverage import generate_protocol_coverage
from .review_decisions import review_decision_summary
from .utils import iso_now, read_json, safe_write_text, write_json

CLAIM_EVIDENCE_BINDER_SCHEMA_VERSION = "1.12.0"
CLAIM_EVIDENCE_BINDER_VALIDATION_SCHEMA_VERSION = "1.12.1"


def build_claim_evidence_binder(project_dir: Path) -> dict[str, Any]:
    """Build claim evidence binder payload without writing binder files."""
    project_dir = Path(project_dir)
    trace = generate_claim_trace(project_dir)
    validation = validate_claim_trace(project_dir)
    coverage_path = project_dir / "workspace" / "protocol_coverage.json"
    coverage = read_json(coverage_path, default={}) or {}
    if not isinstance(coverage, dict) or not coverage_path.exists():
        coverage = generate_protocol_coverage(project_dir)
    review_decisions = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    review_decisions = review_decisions if isinstance(review_decisions, dict) else {}

    claims = _claim_binders(trace, coverage, review_decisions)
    incomplete = [item for item in claims if item["status"] != "complete"]
    result = {
        "schema_version": CLAIM_EVIDENCE_BINDER_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "trace_schema_version": trace.get("schema_version"),
        "coverage_schema_version": coverage.get("schema_version"),
        "validation_status": validation.get("status"),
        "coverage_status": coverage.get("status"),
        "status": "complete" if trace.get("claim_count", 0) > 0 and not incomplete and coverage.get("status") == "complete" else "needs_evidence",
        "claim_count": len(claims),
        "complete_claim_count": len(claims) - len(incomplete),
        "incomplete_claim_count": len(incomplete),
        "top_command": _top_command(project_dir, incomplete, coverage),
        "claims": claims,
        "review_decision_status": review_decision_summary(project_dir),
        "policy": "Claim evidence binders organize workflow evidence only; they do not prove that paper claims were scientifically reproduced.",
    }
    return result


def generate_claim_evidence_binder(project_dir: Path) -> dict[str, Any]:
    """Write workspace/claim_evidence_binder.json and Markdown."""
    project_dir = Path(project_dir)
    result = build_claim_evidence_binder(project_dir)
    write_json(project_dir / "workspace" / "claim_evidence_binder.json", result)
    safe_write_text(project_dir / "workspace" / "CLAIM_EVIDENCE_BINDER.md", _render_binder_markdown(result))
    return result


def validate_claim_evidence_binder(project_dir: Path) -> dict[str, Any]:
    """Validate claim evidence binder freshness and internal consistency."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_evidence_binder.json"
    stored = read_json(path, default={}) or {}
    stored = stored if isinstance(stored, dict) else {}
    current = build_claim_evidence_binder(project_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not path.exists():
        issues.append(_validation_issue("binder_missing", "workspace/claim_evidence_binder.json is missing."))
    elif _binder_fingerprint(stored) != _binder_fingerprint(current):
        issues.append(
            _validation_issue(
                "binder_stale",
                "workspace/claim_evidence_binder.json no longer matches current claims, coverage, review decisions, data, specs, or runs.",
                stored_fingerprint=_binder_fingerprint(stored),
                current_fingerprint=_binder_fingerprint(current),
            )
        )
    if path.exists():
        _binder_integrity_issues(stored, issues, warnings)

    valid = not issues
    result = {
        "schema_version": CLAIM_EVIDENCE_BINDER_VALIDATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "binder_path": str(path),
        "status": "passed" if valid else "failed",
        "valid": valid,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "top_command": None if valid else f"openrepro evidence-binder {project_dir}",
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "stored_claim_count": int(stored.get("claim_count", 0) or 0),
            "current_claim_count": int(current.get("claim_count", 0) or 0),
            "stored_incomplete_claim_count": int(stored.get("incomplete_claim_count", 0) or 0),
            "current_incomplete_claim_count": int(current.get("incomplete_claim_count", 0) or 0),
            "stored_status": stored.get("status", "missing") if path.exists() else "missing",
            "current_status": current.get("status"),
        },
        "policy": "Claim evidence binder validation checks workflow evidence freshness and consistency only; it does not prove scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "claim_evidence_binder_validation.json", result)
    safe_write_text(
        project_dir / "workspace" / "CLAIM_EVIDENCE_BINDER_VALIDATION.md",
        _render_binder_validation_markdown(result),
    )
    return result


def claim_evidence_binder_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim evidence binder summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_evidence_binder.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "claim_count": int(data.get("claim_count", 0) or 0),
        "complete_claim_count": int(data.get("complete_claim_count", 0) or 0),
        "incomplete_claim_count": int(data.get("incomplete_claim_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def claim_evidence_binder_validation_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim evidence binder validation summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_evidence_binder_validation.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    binder = claim_evidence_binder_summary(project_dir)
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "valid": bool(data.get("valid")) if path.exists() else False,
        "issue_count": int(data.get("issue_count", binder["incomplete_claim_count"]) or 0),
        "warning_count": int(data.get("warning_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _claim_binders(trace: dict[str, Any], coverage: dict[str, Any], review_decisions: dict[str, Any]) -> list[dict[str, Any]]:
    experiments = [item for item in trace.get("experiments", []) if isinstance(item, dict)]
    runs = [item for item in trace.get("runs", []) if isinstance(item, dict)]
    coverage_items = _coverage_items_by_claim(coverage)
    claims: list[dict[str, Any]] = []
    for claim in trace.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "")
        linked_experiments = [
            experiment
            for experiment in experiments
            if claim_id in {str(value) for value in experiment.get("claim_ids", [])}
            or claim_id in {str(value) for value in experiment.get("verified_claim_ids", [])}
        ]
        linked_experiment_ids = {str(item.get("experiment_id")) for item in linked_experiments if item.get("experiment_id")}
        linked_runs = [run for run in runs if str(run.get("experiment_id")) in linked_experiment_ids]
        data_ids = sorted(
            {
                str(data_id)
                for experiment in linked_experiments
                for data_id in experiment.get("registered_data_ids", [])
                if data_id
            }
        )
        coverage_item = coverage_items.get(claim_id, {})
        gate_status = _claim_gate_status(linked_runs)
        missing = _missing_evidence(claim, linked_experiments, linked_runs, data_ids, gate_status, coverage_item)
        claims.append(
            {
                "claim_id": claim_id,
                "candidate_id": claim.get("candidate_id"),
                "kind": claim.get("kind"),
                "text": claim.get("text"),
                "source_name": claim.get("source_name"),
                "section": claim.get("section"),
                "verified_by_human": bool(claim.get("verified_by_human")),
                "risk_level": claim.get("risk_level"),
                "linked_experiments": [_experiment_ref(item) for item in linked_experiments],
                "linked_runs": [_run_ref(item) for item in linked_runs],
                "registered_data_ids": data_ids,
                "quality_gate_status": gate_status,
                "protocol_coverage": coverage_item,
                "review_decision_ids": _related_review_decision_ids(claim, review_decisions),
                "missing_evidence": missing,
                "status": "complete" if not missing else "needs_evidence",
            }
        )
    return claims


def _coverage_items_by_claim(coverage: dict[str, Any]) -> dict[str, dict[str, Any]]:
    for dimension in coverage.get("dimensions", []):
        if not isinstance(dimension, dict) or dimension.get("key") != "target_claims":
            continue
        return {
            str(item.get("id")): {
                "covered": bool(item.get("covered")),
                "verified_by_human": bool(item.get("verified_by_human")),
                "linked_experiments": item.get("linked_experiments", []),
                "linked_runs": item.get("linked_runs", []),
                "quality_gate_passed": bool(item.get("quality_gate_passed")),
            }
            for item in dimension.get("items", [])
            if isinstance(item, dict)
        }
    return {}


def _experiment_ref(experiment: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": experiment.get("experiment_id"),
        "template": experiment.get("template"),
        "status": experiment.get("status"),
        "registered_data_ids": experiment.get("registered_data_ids", []),
        "spec_sha256": experiment.get("spec_sha256"),
    }


def _run_ref(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.get("run_id"),
        "command": run.get("command"),
        "experiment_id": run.get("experiment_id"),
        "quality_gate_status": run.get("quality_gate_status"),
        "quality_gate_failed_check_names": run.get("quality_gate_failed_check_names", []),
        "manifest_sha256": run.get("manifest_sha256"),
    }


def _claim_gate_status(linked_runs: list[dict[str, Any]]) -> str:
    if not linked_runs:
        return "missing"
    statuses = {str(item.get("quality_gate_status") or "missing") for item in linked_runs}
    if statuses == {"passed"}:
        return "passed"
    if "failed" in statuses:
        return "failed"
    return "missing"


def _missing_evidence(
    claim: dict[str, Any],
    linked_experiments: list[dict[str, Any]],
    linked_runs: list[dict[str, Any]],
    data_ids: list[str],
    gate_status: str,
    coverage_item: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    if not claim.get("verified_by_human"):
        missing.append("human_verification")
    if not linked_experiments:
        missing.append("experiment_link")
    if not data_ids:
        missing.append("registered_data")
    if not linked_runs:
        missing.append("run_evidence")
    if linked_runs and gate_status != "passed":
        missing.append("quality_gate_passed")
    if coverage_item and not coverage_item.get("covered"):
        missing.append("protocol_coverage")
    return missing


def _related_review_decision_ids(claim: dict[str, Any], review_decisions: dict[str, Any]) -> list[str]:
    claim_terms = {
        str(claim.get("claim_id") or "").lower(),
        str(claim.get("candidate_id") or "").lower(),
    }
    related: list[str] = []
    for decision in review_decisions.get("decisions", []):
        if not isinstance(decision, dict):
            continue
        haystack = " ".join(
            [
                str(decision.get("item_id") or ""),
                str(decision.get("note") or ""),
                str((decision.get("board_item") or {}).get("title") or ""),
                str((decision.get("board_item") or {}).get("source") or ""),
            ]
        ).lower()
        if any(term and term in haystack for term in claim_terms):
            related.append(str(decision.get("decision_id")))
    return related


def _top_command(project_dir: Path, incomplete: list[dict[str, Any]], coverage: dict[str, Any]) -> str | None:
    if not incomplete:
        return None
    missing = set(incomplete[0].get("missing_evidence", []))
    if "human_verification" in missing:
        return f"openrepro approve-candidates {project_dir} --all --reviewer <name>"
    if "registered_data" in missing:
        return f"openrepro register-data {project_dir} --path <path> --role dataset"
    if "experiment_link" in missing:
        return f"openrepro scaffold-experiment {project_dir} --experiment-id <id>"
    if "run_evidence" in missing:
        return f"openrepro run-experiment {project_dir} --experiment-id <id> --confirm"
    if "quality_gate_passed" in missing:
        return f"openrepro quality-gate {project_dir} --all"
    return str(coverage.get("top_command") or f"openrepro protocol-plan {project_dir}")


def _binder_fingerprint(binder: dict[str, Any]) -> str:
    stable = {
        "schema_version": binder.get("schema_version"),
        "trace_schema_version": binder.get("trace_schema_version"),
        "coverage_schema_version": binder.get("coverage_schema_version"),
        "validation_status": binder.get("validation_status"),
        "coverage_status": binder.get("coverage_status"),
        "status": binder.get("status"),
        "claim_count": binder.get("claim_count"),
        "complete_claim_count": binder.get("complete_claim_count"),
        "incomplete_claim_count": binder.get("incomplete_claim_count"),
        "top_command": binder.get("top_command"),
        "claims": sorted(
            [
                {
                    "claim_id": item.get("claim_id"),
                    "candidate_id": item.get("candidate_id"),
                    "kind": item.get("kind"),
                    "source_name": item.get("source_name"),
                    "section": item.get("section"),
                    "verified_by_human": item.get("verified_by_human"),
                    "linked_experiments": sorted(
                        [
                            {
                                "experiment_id": experiment.get("experiment_id"),
                                "template": experiment.get("template"),
                                "status": experiment.get("status"),
                                "registered_data_ids": sorted(str(value) for value in experiment.get("registered_data_ids", [])),
                                "spec_sha256": experiment.get("spec_sha256"),
                            }
                            for experiment in item.get("linked_experiments", [])
                            if isinstance(experiment, dict)
                        ],
                        key=lambda experiment: str(experiment.get("experiment_id")),
                    ),
                    "linked_runs": sorted(
                        [
                            {
                                "run_id": run.get("run_id"),
                                "command": run.get("command"),
                                "experiment_id": run.get("experiment_id"),
                                "quality_gate_status": run.get("quality_gate_status"),
                                "quality_gate_failed_check_names": sorted(run.get("quality_gate_failed_check_names", [])),
                                "manifest_sha256": run.get("manifest_sha256"),
                            }
                            for run in item.get("linked_runs", [])
                            if isinstance(run, dict)
                        ],
                        key=lambda run: str(run.get("run_id")),
                    ),
                    "registered_data_ids": sorted(str(value) for value in item.get("registered_data_ids", [])),
                    "quality_gate_status": item.get("quality_gate_status"),
                    "protocol_coverage": item.get("protocol_coverage", {}),
                    "review_decision_ids": sorted(str(value) for value in item.get("review_decision_ids", [])),
                    "missing_evidence": sorted(str(value) for value in item.get("missing_evidence", [])),
                    "status": item.get("status"),
                }
                for item in binder.get("claims", [])
                if isinstance(item, dict)
            ],
            key=lambda item: str(item.get("claim_id")),
        ),
    }
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validation_issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details}


def _binder_integrity_issues(
    binder: dict[str, Any],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    claims = [item for item in binder.get("claims", []) if isinstance(item, dict)]
    claim_ids = [str(item.get("claim_id") or "") for item in claims]
    if len(set(claim_ids)) != len(claim_ids):
        issues.append(_validation_issue("binder_duplicate_claim_ids", "Claim evidence binder contains duplicate claim ids."))
    if int(binder.get("claim_count", 0) or 0) != len(claims):
        issues.append(
            _validation_issue(
                "binder_claim_count_mismatch",
                "Binder claim_count does not match the number of claim records.",
                claim_count=binder.get("claim_count"),
                actual_count=len(claims),
            )
        )
    incomplete = [item for item in claims if item.get("status") != "complete"]
    complete = [item for item in claims if item.get("status") == "complete"]
    if int(binder.get("complete_claim_count", 0) or 0) != len(complete):
        issues.append(_validation_issue("binder_complete_count_mismatch", "Binder complete_claim_count is inconsistent."))
    if int(binder.get("incomplete_claim_count", 0) or 0) != len(incomplete):
        issues.append(_validation_issue("binder_incomplete_count_mismatch", "Binder incomplete_claim_count is inconsistent."))
    for claim in claims:
        if not claim.get("claim_id"):
            issues.append(_validation_issue("binder_claim_id_missing", "A claim binder record is missing claim_id."))
        if claim.get("status") == "complete" and claim.get("missing_evidence"):
            issues.append(
                _validation_issue(
                    "binder_complete_claim_has_missing_evidence",
                    f"Claim {claim.get('claim_id')} is complete but still lists missing evidence.",
                    claim_id=claim.get("claim_id"),
                )
            )
        if claim.get("status") != "complete" and not claim.get("missing_evidence"):
            warnings.append(
                _validation_issue(
                    "binder_incomplete_claim_without_missing_evidence",
                    f"Claim {claim.get('claim_id')} is incomplete but has no missing evidence labels.",
                    claim_id=claim.get("claim_id"),
                )
            )


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_binder_markdown(binder: dict[str, Any]) -> str:
    lines = [
        "# Claim Evidence Binder",
        "",
        f"- schema_version: {binder['schema_version']}",
        f"- status: {binder['status']}",
        f"- claim_count: {binder['claim_count']}",
        f"- complete_claim_count: {binder['complete_claim_count']}",
        f"- incomplete_claim_count: {binder['incomplete_claim_count']}",
        f"- top_command: {binder['top_command']}",
        "",
        "## Claims",
        "",
        "| Claim | Status | Verified | Experiments | Runs | Data | Missing evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for claim in binder["claims"]:
        lines.append(
            "| {claim_id} | {status} | {verified} | {experiments} | {runs} | {data} | {missing} |".format(
                claim_id=_cell(claim["claim_id"]),
                status=_cell(claim["status"]),
                verified=_cell(claim["verified_by_human"]),
                experiments=_cell([item.get("experiment_id") for item in claim["linked_experiments"]]),
                runs=_cell([item.get("run_id") for item in claim["linked_runs"]]),
                data=_cell(claim["registered_data_ids"]),
                missing=_cell(claim["missing_evidence"]),
            )
        )
    if not binder["claims"]:
        lines.append("| none | needs_evidence | False | [] | [] | [] | ['claim_trace'] |")
    lines.extend(["", "## Policy", "", binder["policy"], ""])
    return "\n".join(lines)


def _render_binder_validation_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Claim Evidence Binder Validation",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- valid: {result['valid']}",
        f"- issue_count: {result['issue_count']}",
        f"- warning_count: {result['warning_count']}",
        f"- top_command: {result['top_command']}",
        "",
        "## Summary",
        "",
    ]
    for key, value in result["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Issues", "", "| Code | Message |", "| --- | --- |"])
    if result["issues"]:
        for item in result["issues"]:
            lines.append(f"| {item['code']} | {item['message']} |")
    else:
        lines.append("| none | No binder validation issues found. |")
    lines.extend(["", "## Warnings", "", "| Code | Message |", "| --- | --- |"])
    if result["warnings"]:
        for item in result["warnings"]:
            lines.append(f"| {item['code']} | {item['message']} |")
    else:
        lines.append("| none | No binder validation warnings found. |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
