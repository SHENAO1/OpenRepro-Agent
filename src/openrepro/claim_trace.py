"""Claim-to-evidence traceability for reproduction workflows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .data_registry import data_index_summary
from .utils import iso_now, read_json, safe_write_text, write_json

CLAIM_TRACE_SCHEMA_VERSION = "1.6.1"
CLAIM_TRACE_VALIDATION_SCHEMA_VERSION = "1.6.1"


def _candidate_claims(project_dir: Path, filename: str, kind: str) -> list[dict[str, Any]]:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    claims: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not candidate.get("candidate_id"):
            continue
        candidate_id = str(candidate["candidate_id"])
        provenance = candidate.get("provenance", {}) if isinstance(candidate.get("provenance"), dict) else {}
        claims.append(
            {
                "claim_id": f"{kind}:{candidate_id}",
                "candidate_id": candidate_id,
                "kind": kind,
                "status": candidate.get("status", "candidate_unverified"),
                "text": candidate.get("evidence") or candidate.get("name") or candidate_id,
                "source_name": provenance.get("source_name"),
                "section": provenance.get("section"),
                "page_number": provenance.get("page_number"),
                "risk_level": candidate.get("risk_level"),
                "risk_flags": candidate.get("risk_flags", []),
            }
        )
    return claims


def _verified_claim_ids(project_dir: Path) -> set[str]:
    verified = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(verified, dict):
        return set()
    return {
        *(f"formula:{candidate_id}" for candidate_id in verified.get("formula_candidate_ids", [])),
        *(f"parameter:{candidate_id}" for candidate_id in verified.get("parameter_candidate_ids", [])),
    }


def _experiment_traces(project_dir: Path) -> list[dict[str, Any]]:
    experiments_dir = project_dir / "experiments"
    if not experiments_dir.exists():
        return []
    traces: list[dict[str, Any]] = []
    for exp_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
        config = read_json(exp_dir / "experiment_config.json", default={}) or {}
        spec = read_json(exp_dir / "experiment_spec.json", default={}) or {}
        config = config if isinstance(config, dict) else {}
        spec = spec if isinstance(spec, dict) else {}
        formula_claims = [f"formula:{item}" for item in config.get("formula_candidate_ids", []) if item]
        parameter_claims = [f"parameter:{item}" for item in config.get("parameter_candidate_ids", []) if item]
        verified_formula_claims = [f"formula:{item}" for item in config.get("verified_formula_candidate_ids", []) if item]
        verified_parameter_claims = [f"parameter:{item}" for item in config.get("verified_parameter_candidate_ids", []) if item]
        traces.append(
            {
                "experiment_id": exp_dir.name,
                "experiment_dir": str(exp_dir),
                "template": config.get("template"),
                "status": config.get("status"),
                "claim_ids": sorted(set(formula_claims + parameter_claims)),
                "verified_claim_ids": sorted(set(verified_formula_claims + verified_parameter_claims)),
                "registered_data_ids": [
                    item.get("data_id")
                    for item in (spec.get("data_contract", {}) or {}).get("registered_data", [])
                    if isinstance(item, dict)
                ],
                "spec_path": str(exp_dir / "experiment_spec.json") if (exp_dir / "experiment_spec.json").exists() else None,
                "spec_sha256": sha256_file(exp_dir / "experiment_spec.json") if (exp_dir / "experiment_spec.json").exists() else None,
            }
        )
    return traces


def _run_traces(project_dir: Path) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for run_dir in reversed(list_run_dirs(project_dir)):
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        manifest = manifest if isinstance(manifest, dict) else {}
        metadata = manifest.get("metadata", {}) if isinstance(manifest.get("metadata"), dict) else {}
        quality_gate = read_json(run_dir / "reports" / "quality_gate.json", default={}) or {}
        quality_gate = quality_gate if isinstance(quality_gate, dict) else {}
        traces.append(
            {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "command": manifest.get("command", "unknown"),
                "experiment_id": metadata.get("experiment_id"),
                "template": metadata.get("template"),
                "quality_gate_status": quality_gate.get("status") if quality_gate else "missing",
                "quality_gate_failed_check_names": quality_gate.get("failed_check_names", []) if quality_gate else [],
                "manifest_sha256": sha256_file(run_dir / "manifest.json") if (run_dir / "manifest.json").exists() else None,
            }
        )
    return traces


def build_claim_trace(project_dir: Path) -> dict[str, Any]:
    """Build claim trace payload without writing files."""
    project_dir = Path(project_dir)
    formula_claims = _candidate_claims(project_dir, "formula_candidates.json", "formula")
    parameter_claims = _candidate_claims(project_dir, "parameter_candidates.json", "parameter")
    verified_claims = _verified_claim_ids(project_dir)
    claims = []
    for claim in formula_claims + parameter_claims:
        item = dict(claim)
        item["verified_by_human"] = item["claim_id"] in verified_claims
        claims.append(item)
    experiments = _experiment_traces(project_dir)
    runs = _run_traces(project_dir)
    data_summary = data_index_summary(project_dir)
    trace = {
        "schema_version": CLAIM_TRACE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "claim_count": len(claims),
        "verified_claim_count": sum(1 for claim in claims if claim["verified_by_human"]),
        "experiment_trace_count": len(experiments),
        "run_trace_count": len(runs),
        "registered_data_count": data_summary["registered_count"],
        "claims": claims,
        "experiments": experiments,
        "runs": runs,
        "data_registry": {
            "registered_count": data_summary["registered_count"],
            "status_counts": data_summary["status_counts"],
            "sources": data_summary["sources"],
        },
        "policy": "Claim trace links workflow evidence only; it does not claim that a paper claim has been scientifically reproduced.",
    }
    return trace


def generate_claim_trace(project_dir: Path) -> dict[str, Any]:
    """Write workspace/claim_trace.json and workspace/CLAIM_TRACE.md."""
    project_dir = Path(project_dir)
    trace = build_claim_trace(project_dir)
    write_json(project_dir / "workspace" / "claim_trace.json", trace)
    safe_write_text(project_dir / "workspace" / "CLAIM_TRACE.md", _render_claim_trace_markdown(trace))
    return trace


def validate_claim_trace(project_dir: Path) -> dict[str, Any]:
    """Validate current claim trace links and freshness."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_trace.json"
    stored = read_json(path, default={}) or {}
    stored = stored if isinstance(stored, dict) else {}
    current = build_claim_trace(project_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not path.exists():
        issues.append(_validation_issue("claim_trace_missing", "workspace/claim_trace.json is missing."))
    elif _trace_fingerprint(stored) != _trace_fingerprint(current):
        issues.append(
            _validation_issue(
                "claim_trace_stale",
                "workspace/claim_trace.json no longer matches current candidates, specs, data, runs, or quality gates.",
                stored_fingerprint=_trace_fingerprint(stored),
                current_fingerprint=_trace_fingerprint(current),
            )
        )

    _linkage_issues(current, issues, warnings)
    valid = not issues
    result = {
        "schema_version": CLAIM_TRACE_VALIDATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "trace_path": str(path),
        "status": "passed" if valid else "failed",
        "valid": valid,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "claim_count": current["claim_count"],
            "verified_claim_count": current["verified_claim_count"],
            "experiment_trace_count": current["experiment_trace_count"],
            "run_trace_count": current["run_trace_count"],
            "registered_data_count": current["registered_data_count"],
        },
        "policy": "Claim trace validation checks workflow link integrity and freshness only; it does not claim scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "claim_trace_validation.json", result)
    safe_write_text(project_dir / "workspace" / "CLAIM_TRACE_VALIDATION.md", _render_claim_trace_validation_markdown(result))
    return result


def claim_trace_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim trace summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_trace.json"
    validation_path = project_dir / "workspace" / "claim_trace_validation.json"
    trace = read_json(path, default={}) or {}
    trace = trace if isinstance(trace, dict) else {}
    validation = read_json(validation_path, default={}) or {}
    validation = validation if isinstance(validation, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": trace.get("schema_version"),
        "claim_count": int(trace.get("claim_count", 0) or 0),
        "verified_claim_count": int(trace.get("verified_claim_count", 0) or 0),
        "experiment_trace_count": int(trace.get("experiment_trace_count", 0) or 0),
        "run_trace_count": int(trace.get("run_trace_count", 0) or 0),
        "registered_data_count": int(trace.get("registered_data_count", 0) or 0),
        "validation_present": validation_path.exists(),
        "validation_status": validation.get("status", "missing") if validation_path.exists() else "missing",
        "validation_issue_count": int(validation.get("issue_count", 0) or 0),
        "validation_warning_count": int(validation.get("warning_count", 0) or 0),
        "validation_sha256": sha256_file(validation_path) if validation_path.exists() else None,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _trace_fingerprint(trace: dict[str, Any]) -> str:
    stable = {
        "claim_count": trace.get("claim_count"),
        "verified_claim_count": trace.get("verified_claim_count"),
        "experiment_trace_count": trace.get("experiment_trace_count"),
        "run_trace_count": trace.get("run_trace_count"),
        "registered_data_count": trace.get("registered_data_count"),
        "claims": sorted(
            [
                {
                    "claim_id": item.get("claim_id"),
                    "verified_by_human": item.get("verified_by_human"),
                    "status": item.get("status"),
                    "source_name": item.get("source_name"),
                    "section": item.get("section"),
                    "page_number": item.get("page_number"),
                    "risk_level": item.get("risk_level"),
                    "risk_flags": item.get("risk_flags", []),
                }
                for item in trace.get("claims", [])
                if isinstance(item, dict)
            ],
            key=lambda item: str(item.get("claim_id")),
        ),
        "experiments": sorted(
            [
                {
                    "experiment_id": item.get("experiment_id"),
                    "template": item.get("template"),
                    "status": item.get("status"),
                    "claim_ids": sorted(item.get("claim_ids", [])),
                    "verified_claim_ids": sorted(item.get("verified_claim_ids", [])),
                    "registered_data_ids": sorted(str(data_id) for data_id in item.get("registered_data_ids", [])),
                    "spec_sha256": item.get("spec_sha256"),
                }
                for item in trace.get("experiments", [])
                if isinstance(item, dict)
            ],
            key=lambda item: str(item.get("experiment_id")),
        ),
        "runs": sorted(
            [
                {
                    "run_id": item.get("run_id"),
                    "command": item.get("command"),
                    "experiment_id": item.get("experiment_id"),
                    "template": item.get("template"),
                    "quality_gate_status": item.get("quality_gate_status"),
                    "quality_gate_failed_check_names": sorted(item.get("quality_gate_failed_check_names", [])),
                    "manifest_sha256": item.get("manifest_sha256"),
                }
                for item in trace.get("runs", [])
                if isinstance(item, dict)
            ],
            key=lambda item: str(item.get("run_id")),
        ),
        "data_registry": trace.get("data_registry", {}),
    }
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validation_issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details,
    }


def _linkage_issues(trace: dict[str, Any], issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    claim_ids = {str(item.get("claim_id")) for item in trace.get("claims", []) if isinstance(item, dict)}
    verified_claim_ids = {
        str(item.get("claim_id"))
        for item in trace.get("claims", [])
        if isinstance(item, dict) and item.get("verified_by_human")
    }
    experiment_ids = {str(item.get("experiment_id")) for item in trace.get("experiments", []) if isinstance(item, dict)}
    data_ids = {
        str(item.get("data_id"))
        for item in trace.get("data_registry", {}).get("sources", [])
        if isinstance(item, dict) and item.get("data_id")
    }
    linked_claims: set[str] = set()
    linked_verified_claims: set[str] = set()

    for experiment in trace.get("experiments", []):
        if not isinstance(experiment, dict):
            continue
        experiment_id = str(experiment.get("experiment_id"))
        for claim_id in experiment.get("claim_ids", []):
            claim_id = str(claim_id)
            linked_claims.add(claim_id)
            if claim_id not in claim_ids:
                issues.append(
                    _validation_issue(
                        "claim_trace_unresolved_experiment_claim",
                        f"Experiment {experiment_id} links missing claim {claim_id}.",
                        experiment_id=experiment_id,
                        claim_id=claim_id,
                    )
                )
        for claim_id in experiment.get("verified_claim_ids", []):
            claim_id = str(claim_id)
            linked_verified_claims.add(claim_id)
            if claim_id not in claim_ids:
                issues.append(
                    _validation_issue(
                        "claim_trace_unresolved_verified_claim",
                        f"Experiment {experiment_id} links missing verified claim {claim_id}.",
                        experiment_id=experiment_id,
                        claim_id=claim_id,
                    )
                )
            elif claim_id not in verified_claim_ids:
                issues.append(
                    _validation_issue(
                        "claim_trace_unverified_experiment_claim",
                        f"Experiment {experiment_id} marks unverified claim {claim_id} as verified.",
                        experiment_id=experiment_id,
                        claim_id=claim_id,
                    )
                )
        for data_id in experiment.get("registered_data_ids", []):
            data_id = str(data_id)
            if data_id and data_id not in data_ids:
                issues.append(
                    _validation_issue(
                        "claim_trace_unregistered_experiment_data",
                        f"Experiment {experiment_id} links unregistered data {data_id}.",
                        experiment_id=experiment_id,
                        data_id=data_id,
                    )
                )

    for run in trace.get("runs", []):
        if not isinstance(run, dict):
            continue
        experiment_id = run.get("experiment_id")
        if run.get("command") == "run-experiment" and (not experiment_id or str(experiment_id) not in experiment_ids):
            issues.append(
                _validation_issue(
                    "claim_trace_unlinked_experiment_run",
                    f"Run {run.get('run_id')} does not link to a known experiment scaffold.",
                    run_id=run.get("run_id"),
                    experiment_id=experiment_id,
                )
            )

    unlinked_verified = sorted(verified_claim_ids - linked_verified_claims)
    if unlinked_verified and trace.get("experiment_trace_count", 0):
        warnings.append(
            _validation_issue(
                "claim_trace_verified_claims_without_experiment",
                "Some human-verified claims are not linked to an experiment scaffold.",
                claim_ids=unlinked_verified,
            )
        )
    unlinked_claims = sorted(claim_ids - linked_claims)
    if unlinked_claims and trace.get("experiment_trace_count", 0):
        warnings.append(
            _validation_issue(
                "claim_trace_candidate_claims_without_experiment",
                "Some candidate claims are not linked to an experiment scaffold.",
                claim_ids=unlinked_claims,
            )
        )
    if trace.get("experiment_trace_count", 0) and trace.get("run_trace_count", 0) == 0:
        warnings.append(
            _validation_issue(
                "claim_trace_experiments_without_runs",
                "Experiment scaffolds exist, but no run evidence is linked yet.",
            )
        )


def _render_claim_trace_markdown(trace: dict[str, Any]) -> str:
    lines = [
        "# Claim Trace",
        "",
        f"- claim_count: {trace['claim_count']}",
        f"- verified_claim_count: {trace['verified_claim_count']}",
        f"- experiment_trace_count: {trace['experiment_trace_count']}",
        f"- run_trace_count: {trace['run_trace_count']}",
        f"- registered_data_count: {trace['registered_data_count']}",
        "",
        "## Claims",
        "",
        "| Claim | Kind | Verified | Source | Section |",
        "| --- | --- | --- | --- | --- |",
    ]
    for claim in trace["claims"]:
        lines.append(
            "| {claim_id} | {kind} | {verified} | {source} | {section} |".format(
                claim_id=claim["claim_id"],
                kind=claim["kind"],
                verified=claim["verified_by_human"],
                source=claim.get("source_name"),
                section=claim.get("section"),
            )
        )
    lines.extend(
        [
            "",
            "## Experiments",
            "",
            "| Experiment | Template | Claims | Verified Claims | Data |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for experiment in trace["experiments"]:
        lines.append(
            "| {experiment_id} | {template} | {claims} | {verified} | {data} |".format(
                experiment_id=experiment["experiment_id"],
                template=experiment.get("template"),
                claims=", ".join(experiment.get("claim_ids", [])),
                verified=", ".join(experiment.get("verified_claim_ids", [])),
                data=", ".join(str(item) for item in experiment.get("registered_data_ids", [])),
            )
        )
    lines.extend(
        [
            "",
            "## Runs",
            "",
            "| Run | Command | Experiment | Gate |",
            "| --- | --- | --- | --- |",
        ]
    )
    for run in trace["runs"]:
        lines.append(
            "| {run_id} | {command} | {experiment_id} | {gate} |".format(
                run_id=run["run_id"],
                command=run["command"],
                experiment_id=run.get("experiment_id"),
                gate=run.get("quality_gate_status"),
            )
        )
    lines.extend(["", "## Policy", "", trace["policy"], ""])
    return "\n".join(lines)


def _render_claim_trace_validation_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Claim Trace Validation",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- valid: {result['valid']}",
        f"- issue_count: {result['issue_count']}",
        f"- warning_count: {result['warning_count']}",
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
        lines.append("| none | No blocking claim trace issues found. |")
    lines.extend(["", "## Warnings", "", "| Code | Message |", "| --- | --- |"])
    if result["warnings"]:
        for item in result["warnings"]:
            lines.append(f"| {item['code']} | {item['message']} |")
    else:
        lines.append("| none | No claim trace warnings found. |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
