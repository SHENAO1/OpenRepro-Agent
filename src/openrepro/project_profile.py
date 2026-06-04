"""Project profile generation for reproduction workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_trace import generate_claim_trace
from .config import load_project_config
from .data_registry import data_index_summary
from .document_loader import load_source_index
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .gaps import gaps_summary
from .protocol_coverage import protocol_coverage_summary
from .protocol_preflight import protocol_preflight_summary
from .reproduction_protocol import protocol_summary
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, safe_write_text, truncate, write_json

PROJECT_PROFILE_SCHEMA_VERSION = "1.20.0"


def generate_project_profile(project_dir: Path) -> dict[str, Any]:
    """Write workspace/project_profile.json and workspace/PROJECT_PROFILE.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    profile = build_project_profile(project_dir)
    write_json(project_dir / "workspace" / "project_profile.json", profile)
    safe_write_text(project_dir / "workspace" / "PROJECT_PROFILE.md", _render_markdown(profile))
    return profile


def build_project_profile(project_dir: Path) -> dict[str, Any]:
    """Build a project profile payload without writing files."""
    project_dir = Path(project_dir)
    config = load_project_config(project_dir)
    source_index = load_source_index(project_dir)
    claim_trace = _load_or_build_claim_trace(project_dir)
    data_summary = data_index_summary(project_dir)
    scaffolds = inspect_experiment_scaffolds(project_dir)
    specs = inspect_experiment_specs(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    protocol = protocol_summary(project_dir)
    protocol_coverage = protocol_coverage_summary(project_dir)
    protocol_preflight = protocol_preflight_summary(project_dir)
    freshness = _artifact_freshness_status(project_dir)

    sources = _profile_sources(source_index)
    target_claims = _target_claims(claim_trace)
    required_data = _required_data(data_summary)
    required_experiments = _required_experiments(scaffolds, specs, claim_trace)
    acceptance_dimensions = _acceptance_dimensions(
        sources=sources,
        target_claims=target_claims,
        required_data=required_data,
        required_experiments=required_experiments,
        claim_trace=claim_trace,
        scorecard=scorecard,
        gaps=gaps,
        protocol=protocol,
        protocol_coverage=protocol_coverage,
        protocol_preflight=protocol_preflight,
        freshness=freshness,
    )
    status, top_command = _profile_status(project_dir, sources, target_claims, required_experiments, acceptance_dimensions)

    return {
        "schema_version": PROJECT_PROFILE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": str(config.get("project_name") or project_dir.name),
        "project_dir": str(project_dir),
        "project_type": "paper_reproduction_workflow",
        "reproduction_goal": _reproduction_goal(config, target_claims),
        "status": status,
        "top_command": top_command,
        "source_count": len(sources),
        "target_claim_count": len(target_claims),
        "required_data_count": len(required_data),
        "required_experiment_count": len(required_experiments),
        "acceptance_dimension_count": len(acceptance_dimensions),
        "sources": sources,
        "target_claims": target_claims,
        "required_data": required_data,
        "required_experiments": required_experiments,
        "acceptance_dimensions": acceptance_dimensions,
        "context": {
            "scorecard_status": scorecard.get("overall_status"),
            "readiness_score": scorecard.get("overall_score"),
            "gaps_status": gaps.get("status"),
            "open_gap_count": gaps.get("open_count"),
            "protocol_status": protocol.get("status"),
            "protocol_coverage_status": protocol_coverage.get("status"),
            "protocol_preflight_status": protocol_preflight.get("status"),
            "artifact_freshness_status": freshness.get("status"),
        },
        "policy": "Project profiles define reproduction scope and acceptance dimensions only; they do not claim scientific reproduction success.",
    }


def project_profile_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing project profile summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "project_profile.json"
    markdown_path = project_dir / "workspace" / "PROJECT_PROFILE.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "top_command": data.get("top_command"),
        "project_type": data.get("project_type"),
        "target_claim_count": int(data.get("target_claim_count", 0) or 0),
        "required_data_count": int(data.get("required_data_count", 0) or 0),
        "required_experiment_count": int(data.get("required_experiment_count", 0) or 0),
        "acceptance_dimension_count": int(data.get("acceptance_dimension_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _load_or_build_claim_trace(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "workspace" / "claim_trace.json"
    data = read_json(path, default=None)
    if isinstance(data, dict):
        return data
    return generate_claim_trace(project_dir)


def _artifact_freshness_status(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "workspace" / "artifact_freshness.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "status": data.get("status", "missing") if path.exists() else "missing",
        "top_command": data.get("top_command"),
    }


def _profile_sources(source_index: dict[str, Any]) -> list[dict[str, Any]]:
    sources = []
    for record in source_index.get("sources", []):
        if not isinstance(record, dict):
            continue
        sources.append(
            {
                "source_name": record.get("source_name"),
                "path": record.get("copied_path"),
                "status": record.get("status"),
                "suffix": record.get("suffix"),
                "page_count": record.get("page_count"),
                "char_count": record.get("char_count"),
            }
        )
    return sources


def _target_claims(claim_trace: dict[str, Any]) -> list[dict[str, Any]]:
    claims = []
    for claim in claim_trace.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claims.append(
            {
                "claim_id": claim.get("claim_id"),
                "kind": claim.get("kind"),
                "status": "verified_by_human" if claim.get("verified_by_human") else claim.get("status"),
                "verified_by_human": bool(claim.get("verified_by_human")),
                "source_name": claim.get("source_name"),
                "section": claim.get("section"),
                "page_number": claim.get("page_number"),
                "risk_level": claim.get("risk_level"),
                "text": truncate(str(claim.get("text") or ""), 500),
            }
        )
    return sorted(claims, key=lambda item: str(item.get("claim_id")))


def _required_data(data_summary: dict[str, Any]) -> list[dict[str, Any]]:
    required = []
    for source in data_summary.get("sources", []):
        if not isinstance(source, dict):
            continue
        required.append(
            {
                "data_id": source.get("data_id"),
                "role": source.get("role"),
                "path": source.get("registered_path") or source.get("path"),
                "status": source.get("status"),
                "valid": source.get("valid"),
                "note": source.get("note"),
            }
        )
    return sorted(required, key=lambda item: str(item.get("data_id")))


def _required_experiments(
    scaffolds: dict[str, Any],
    specs: dict[str, Any],
    claim_trace: dict[str, Any],
) -> list[dict[str, Any]]:
    spec_by_id = {
        str(item.get("experiment_id")): item
        for item in specs.get("specs", [])
        if isinstance(item, dict) and item.get("experiment_id")
    }
    trace_by_id = {
        str(item.get("experiment_id")): item
        for item in claim_trace.get("experiments", [])
        if isinstance(item, dict) and item.get("experiment_id")
    }
    experiments = []
    for scaffold in scaffolds.get("scaffolds", []):
        if not isinstance(scaffold, dict):
            continue
        experiment_id = str(scaffold.get("experiment_id"))
        spec = spec_by_id.get(experiment_id, {})
        trace = trace_by_id.get(experiment_id, {})
        experiments.append(
            {
                "experiment_id": experiment_id,
                "template": scaffold.get("template"),
                "status": scaffold.get("status"),
                "runnable": scaffold.get("runnable"),
                "input_completeness_status": scaffold.get("input_completeness_status"),
                "missing_required_inputs": scaffold.get("missing_required_inputs", []),
                "spec_status": spec.get("status", "missing") if spec else "missing",
                "expected_artifacts_status": scaffold.get("expected_artifacts_status"),
                "claim_ids": trace.get("claim_ids", []),
                "verified_claim_ids": trace.get("verified_claim_ids", []),
                "registered_data_ids": trace.get("registered_data_ids", []),
            }
        )
    return sorted(experiments, key=lambda item: item["experiment_id"])


def _acceptance_dimensions(
    *,
    sources: list[dict[str, Any]],
    target_claims: list[dict[str, Any]],
    required_data: list[dict[str, Any]],
    required_experiments: list[dict[str, Any]],
    claim_trace: dict[str, Any],
    scorecard: dict[str, Any],
    gaps: dict[str, Any],
    protocol: dict[str, Any],
    protocol_coverage: dict[str, Any],
    protocol_preflight: dict[str, Any],
    freshness: dict[str, Any],
) -> list[dict[str, Any]]:
    run_trace_count = int(claim_trace.get("run_trace_count", 0) or 0)
    verified_claim_count = sum(1 for claim in target_claims if claim.get("verified_by_human"))
    current_data_count = sum(1 for item in required_data if item.get("status") == "current")
    fresh_status = freshness.get("status")
    return [
        _dimension("sources_ingested", bool(sources), "Imported source material exists.", "openrepro ingest <project> --source <path>"),
        _dimension(
            "target_claims_defined",
            bool(target_claims),
            "Formula and parameter candidates are available as target claims.",
            "openrepro analyze <project>",
        ),
        _dimension(
            "claims_human_reviewed",
            bool(target_claims) and verified_claim_count == len(target_claims),
            f"{verified_claim_count}/{len(target_claims)} target claims are human verified.",
            "openrepro approve-candidates <project> --all --reviewer <name>",
        ),
        _dimension(
            "data_registered",
            bool(required_data) and current_data_count == len(required_data),
            f"{current_data_count}/{len(required_data)} registered data files are current.",
            "openrepro register-data <project> --path <file> --role dataset",
        ),
        _dimension(
            "experiments_scaffolded",
            bool(required_experiments),
            "At least one experiment scaffold is available.",
            "openrepro scaffold-experiment <project> --experiment-id <id>",
        ),
        _dimension(
            "experiment_inputs_complete",
            bool(required_experiments)
            and all(item.get("input_completeness_status") in {"complete", "no_required_inputs"} for item in required_experiments),
            "Experiment input contracts have no missing required inputs.",
            "openrepro validate-inputs <project> --experiment-id <id>",
        ),
        _dimension(
            "experiment_runs_present",
            run_trace_count > 0,
            f"{run_trace_count} run trace(s) are linked to the claim trace.",
            "openrepro run-experiment <project> --experiment-id <id> --confirm",
        ),
        _dimension(
            "quality_gates_passed",
            scorecard.get("overall_status") in {"ready", "passed"},
            f"Readiness scorecard status is {scorecard.get('overall_status')}.",
            "openrepro scorecard <project>",
        ),
        _dimension(
            "open_gaps_resolved",
            gaps.get("status") == "clear",
            f"Gap status is {gaps.get('status')}.",
            "openrepro gaps <project>",
        ),
        _dimension(
            "protocol_ready",
            protocol.get("status") == "ready"
            and protocol_coverage.get("status") == "complete"
            and protocol_preflight.get("status") == "ready",
            "Protocol, coverage, and preflight artifacts are ready.",
            "openrepro protocol-preflight <project>",
        ),
        _dimension(
            "artifact_freshness_current",
            fresh_status in {"current", "missing"},
            f"Artifact freshness status is {fresh_status}.",
            "openrepro freshness <project>",
        ),
    ]


def _dimension(name: str, passed: bool, summary: str, command: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "needs_work",
        "summary": summary,
        "suggested_command": command,
    }


def _profile_status(
    project_dir: Path,
    sources: list[dict[str, Any]],
    target_claims: list[dict[str, Any]],
    required_experiments: list[dict[str, Any]],
    dimensions: list[dict[str, Any]],
) -> tuple[str, str | None]:
    if not sources:
        return "needs_sources", f"openrepro ingest {project_dir} --source <markdown_or_txt_or_pdf>"
    if not target_claims:
        return "needs_claims", f"openrepro analyze {project_dir}"
    if not required_experiments:
        return "needs_experiments", f"openrepro scaffold-experiment {project_dir} --experiment-id <id>"
    if any(item.get("status") != "passed" for item in dimensions):
        return "ready_with_open_work", None
    return "ready", None


def _reproduction_goal(config: dict[str, Any], target_claims: list[dict[str, Any]]) -> str:
    project_name = str(config.get("project_name") or "the project")
    claim_count = len(target_claims)
    return (
        f"Prepare an auditable workflow profile for {project_name}, covering {claim_count} target "
        "claim(s), required data, experiment scaffolds, and acceptance dimensions without asserting "
        "that the paper has been scientifically reproduced."
    )


def _render_markdown(profile: dict[str, Any]) -> str:
    source_lines = _table(
        ["Source", "Status", "Path"],
        [[item.get("source_name"), item.get("status"), item.get("path")] for item in profile["sources"]],
    )
    claim_lines = _table(
        ["Claim", "Kind", "Status", "Risk", "Text"],
        [
            [item.get("claim_id"), item.get("kind"), item.get("status"), item.get("risk_level"), item.get("text")]
            for item in profile["target_claims"]
        ],
    )
    data_lines = _table(
        ["Data", "Role", "Status", "Path"],
        [[item.get("data_id"), item.get("role"), item.get("status"), item.get("path")] for item in profile["required_data"]],
    )
    experiment_lines = _table(
        ["Experiment", "Template", "Status", "Inputs", "Spec"],
        [
            [
                item.get("experiment_id"),
                item.get("template"),
                item.get("status"),
                item.get("input_completeness_status"),
                item.get("spec_status"),
            ]
            for item in profile["required_experiments"]
        ],
    )
    dimension_lines = _table(
        ["Dimension", "Status", "Summary", "Suggested command"],
        [
            [item.get("name"), item.get("status"), item.get("summary"), item.get("suggested_command")]
            for item in profile["acceptance_dimensions"]
        ],
    )
    return f"""# Project Profile

- schema_version: {profile['schema_version']}
- created_at: {profile['created_at']}
- project_name: {profile['project_name']}
- project_type: {profile['project_type']}
- status: {profile['status']}
- top_command: {profile['top_command']}

## Reproduction Goal

{profile['reproduction_goal']}

## Sources

{source_lines}

## Target Claims

{claim_lines}

## Required Data

{data_lines}

## Required Experiments

{experiment_lines}

## Acceptance Dimensions

{dimension_lines}

## Context

- readiness_score: {profile['context']['readiness_score']}
- scorecard_status: {profile['context']['scorecard_status']}
- gaps_status: {profile['context']['gaps_status']}
- protocol_status: {profile['context']['protocol_status']}
- artifact_freshness_status: {profile['context']['artifact_freshness_status']}

## Policy

{profile['policy']}
"""


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    if not rows:
        rows = [["" for _ in headers]]
    for row in rows:
        padded = list(row) + ["" for _ in range(max(0, len(headers) - len(row)))]
        lines.append("| " + " | ".join(_cell(value) for value in padded[: len(headers)]) + " |")
    return "\n".join(lines)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
