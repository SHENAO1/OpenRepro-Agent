"""Claim-to-evidence traceability for reproduction workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .data_registry import data_index_summary
from .utils import iso_now, read_json, safe_write_text, write_json

CLAIM_TRACE_SCHEMA_VERSION = "1.6.0"


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


def generate_claim_trace(project_dir: Path) -> dict[str, Any]:
    """Write workspace/claim_trace.json and workspace/CLAIM_TRACE.md."""
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
    write_json(project_dir / "workspace" / "claim_trace.json", trace)
    safe_write_text(project_dir / "workspace" / "CLAIM_TRACE.md", _render_claim_trace_markdown(trace))
    return trace


def claim_trace_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing claim trace summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "claim_trace.json"
    trace = read_json(path, default={}) or {}
    trace = trace if isinstance(trace, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": trace.get("schema_version"),
        "claim_count": int(trace.get("claim_count", 0) or 0),
        "verified_claim_count": int(trace.get("verified_claim_count", 0) or 0),
        "experiment_trace_count": int(trace.get("experiment_trace_count", 0) or 0),
        "run_trace_count": int(trace.get("run_trace_count", 0) or 0),
        "registered_data_count": int(trace.get("registered_data_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


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
