"""Project timeline generation for auditable workflow history."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

PROJECT_TIMELINE_SCHEMA_VERSION = "1.16.1"


def generate_project_timeline(project_dir: Path) -> dict[str, Any]:
    """Write workspace/project_timeline.json and Markdown."""
    project_dir = Path(project_dir)
    events: list[dict[str, Any]] = []
    _collect_project_events(project_dir, events)
    _collect_source_events(project_dir, events)
    _collect_candidate_review_events(project_dir, events)
    _collect_verified_candidate_events(project_dir, events)
    _collect_claim_signoff_events(project_dir, events)
    _collect_review_decision_events(project_dir, events)
    _collect_run_events(project_dir, events)
    _collect_artifact_events(project_dir, events)
    events = _sorted_events(events)

    from .project_manager import get_status

    status = get_status(project_dir).to_dict()
    stage_counts = Counter(str(event["stage"]) for event in events)
    type_counts = Counter(str(event["event_type"]) for event in events)
    timeline = {
        "schema_version": PROJECT_TIMELINE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": status.get("project_name", project_dir.name),
        "project_dir": str(project_dir),
        "status": "ready" if events else "empty",
        "event_count": len(events),
        "stage_counts": dict(stage_counts),
        "event_type_counts": dict(type_counts),
        "first_event_at": events[0]["occurred_at"] if events else None,
        "latest_event_at": events[-1]["occurred_at"] if events else None,
        "latest_event_title": events[-1]["title"] if events else None,
        "human_decision_count": type_counts.get("human_decision", 0),
        "run_event_count": type_counts.get("run", 0),
        "artifact_event_count": type_counts.get("artifact", 0),
        "events": events,
        "policy": "Project timelines record workflow history and human decisions; they do not prove scientific reproduction.",
    }
    write_json(project_dir / "workspace" / "project_timeline.json", timeline)
    safe_write_text(project_dir / "workspace" / "PROJECT_TIMELINE.md", _render_markdown(timeline))
    return timeline


def project_timeline_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing project timeline summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "project_timeline.json"
    markdown_path = project_dir / "workspace" / "PROJECT_TIMELINE.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "event_count": int(data.get("event_count", 0) or 0),
        "human_decision_count": int(data.get("human_decision_count", 0) or 0),
        "run_event_count": int(data.get("run_event_count", 0) or 0),
        "latest_event_at": data.get("latest_event_at"),
        "latest_event_title": data.get("latest_event_title"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _collect_project_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    from .config import load_project_config

    try:
        config = load_project_config(project_dir)
    except Exception:
        config = {}
    if (project_dir / "project_config.yaml").exists():
        events.append(
            _event(
                occurred_at=str(config.get("created_at") or _mtime(project_dir / "project_config.yaml")),
                stage="project",
                event_type="artifact",
                title="Project initialized",
                summary="Project configuration and standard workspace directories were created.",
                artifact_path=project_dir / "project_config.yaml",
                status="initialized",
            )
        )


def _collect_source_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    source_index = read_json(project_dir / "workspace" / "source_index.json", default={}) or {}
    for source in source_index.get("sources", []) if isinstance(source_index, dict) else []:
        if not isinstance(source, dict):
            continue
        events.append(
            _event(
                occurred_at=source.get("ingested_at") or source_index.get("updated_at") or _mtime(project_dir / "workspace" / "source_index.json"),
                stage="ingest",
                event_type="source",
                title=f"Ingested {source.get('source_name')}",
                summary=source.get("note") or f"Source status: {source.get('status')}",
                artifact_path=project_dir / str(source.get("copied_path", "")),
                status=source.get("status"),
                actor=None,
                metadata={"suffix": source.get("suffix"), "size_bytes": source.get("size_bytes")},
            )
        )


def _collect_candidate_review_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    data = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    for review in data.get("reviews", []) if isinstance(data, dict) else []:
        if not isinstance(review, dict):
            continue
        events.append(
            _event(
                occurred_at=review.get("reviewed_at") or data.get("created_at"),
                stage="candidate_review",
                event_type="human_decision",
                title=f"Reviewed candidate {review.get('candidate_id')}",
                summary=f"{review.get('candidate_type')} marked {review.get('status')}.",
                artifact_path=project_dir / "workspace" / "candidate_reviews.json",
                status=review.get("status"),
                actor=review.get("reviewer"),
                metadata={"candidate_type": review.get("candidate_type"), "note": review.get("note")},
            )
        )


def _collect_verified_candidate_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    data = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return
    ids = list(data.get("formula_candidate_ids", [])) + list(data.get("parameter_candidate_ids", []))
    events.append(
        _event(
            occurred_at=data.get("created_at") or _mtime(project_dir / "workspace" / "verified_candidates.json"),
            stage="approval",
            event_type="human_decision",
            title="Verified candidates approved",
            summary=f"{len(ids)} candidate(s) promoted into verified inputs.",
            artifact_path=project_dir / "workspace" / "verified_candidates.json",
            status=data.get("status"),
            actor=data.get("reviewer"),
            metadata={"candidate_ids": ids},
        )
    )


def _collect_claim_signoff_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    data = read_json(project_dir / "workspace" / "claim_signoffs.json", default={}) or {}
    for signoff in data.get("signoffs", []) if isinstance(data, dict) else []:
        if not isinstance(signoff, dict):
            continue
        events.append(
            _event(
                occurred_at=signoff.get("created_at") or data.get("created_at"),
                stage="claim_signoff",
                event_type="human_decision",
                title=f"Claim signoff {signoff.get('claim_id')}",
                summary=f"Decision: {signoff.get('decision')}.",
                artifact_path=project_dir / "workspace" / "claim_signoffs.json",
                status=signoff.get("decision"),
                actor=signoff.get("reviewer"),
                metadata={"terminal": signoff.get("terminal"), "note": signoff.get("note")},
            )
        )


def _collect_review_decision_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    data = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    for decision in data.get("decisions", []) if isinstance(data, dict) else []:
        if not isinstance(decision, dict):
            continue
        events.append(
            _event(
                occurred_at=decision.get("created_at") or data.get("created_at"),
                stage="review_decision",
                event_type="human_decision",
                title=f"Review decision {decision.get('item_id')}",
                summary=f"Decision: {decision.get('decision')}.",
                artifact_path=project_dir / "workspace" / "review_decisions.json",
                status=decision.get("decision"),
                actor=decision.get("reviewer"),
                metadata={"closes_item": decision.get("closes_item"), "note": decision.get("note")},
            )
        )


def _collect_run_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    for run_dir in list_run_dirs(project_dir):
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        manifest = manifest if isinstance(manifest, dict) else {}
        gate = read_json(run_dir / "reports" / "quality_gate.json", default={}) or {}
        gate = gate if isinstance(gate, dict) else {}
        command = manifest.get("command") or "unknown"
        events.append(
            _event(
                occurred_at=manifest.get("created_at") or _mtime(run_dir / "manifest.json"),
                stage="run",
                event_type="run",
                title=f"Run recorded: {run_dir.name}",
                summary=f"Command {command}; quality gate {gate.get('status', 'missing')}.",
                artifact_path=run_dir / "manifest.json",
                status=gate.get("status") or manifest.get("command"),
                metadata={
                    "run_id": run_dir.name,
                    "command": command,
                    "quality_gate_status": gate.get("status", "missing"),
                    "artifact_count": len(manifest.get("artifacts", [])) if isinstance(manifest.get("artifacts"), list) else 0,
                },
            )
        )


def _collect_artifact_events(project_dir: Path, events: list[dict[str, Any]]) -> None:
    artifacts = [
        ("analyze", "Analysis completed", project_dir / "workspace" / "analysis_result.json", "status"),
        ("plan", "Experiment plan generated", project_dir / "workspace" / "experiment_plan_validation.json", "status"),
        ("data", "Data registry updated", project_dir / "workspace" / "data_index.json", "status"),
        ("lineage", "Run lineage generated", project_dir / "workspace" / "run_lineage.json", None),
        ("claim_trace", "Claim trace generated", project_dir / "workspace" / "claim_trace.json", "status"),
        ("claim_trace", "Claim trace validated", project_dir / "workspace" / "claim_trace_validation.json", "status"),
        ("scorecard", "Readiness scorecard generated", project_dir / "workspace" / "reproduction_scorecard.json", "overall_status"),
        ("gaps", "Reproduction gaps generated", project_dir / "workspace" / "reproduction_gaps.json", "status"),
        ("checkpoints", "Workflow checkpoints generated", project_dir / "workspace" / "workflow_checkpoints.json", "status"),
        ("advance", "Advance dry-run generated", project_dir / "workspace" / "advance_plan.json", "status"),
        ("review_board", "Review board generated", project_dir / "workspace" / "review_board.json", "status"),
        ("protocol", "Reproduction protocol generated", project_dir / "workspace" / "reproduction_protocol.json", "status"),
        ("protocol", "Protocol coverage generated", project_dir / "workspace" / "protocol_coverage.json", "status"),
        ("protocol", "Protocol plan generated", project_dir / "workspace" / "protocol_plan.json", "status"),
        ("protocol", "Protocol preflight generated", project_dir / "workspace" / "protocol_preflight.json", "status"),
        ("claim_evidence", "Claim evidence binder generated", project_dir / "workspace" / "claim_evidence_binder.json", "status"),
        ("claim_evidence", "Claim evidence binder validated", project_dir / "workspace" / "claim_evidence_binder_validation.json", "status"),
        ("claim_evidence", "Claim signoffs validated", project_dir / "workspace" / "claim_signoff_validation.json", "status"),
        ("claim_evidence", "Claim evidence report generated", project_dir / "reports" / "claim_evidence_report.json", "status"),
        ("claim_evidence", "Claim evidence report validated", project_dir / "reports" / "claim_evidence_report_validation.json", "status"),
        ("reviewer_packet", "Reviewer packet generated", project_dir / "reports" / "reviewer_packet.json", "status"),
        ("handoff", "Project report generated", project_dir / "reports" / "report.md", None),
        ("handoff", "Handoff generated", project_dir / "handoff" / "AGENT_HANDOFF.md", None),
        ("evidence_package", "Evidence package generated", project_dir / "reports" / "evidence_package.json", "freshness.status"),
        ("review_site", "Review site generated", project_dir / "reports" / "review_site_manifest.json", "status"),
    ]
    for stage, title, path, status_key in artifacts:
        if not path.exists():
            continue
        data = read_json(path, default={}) if path.suffix == ".json" else {}
        data = data if isinstance(data, dict) else {}
        status = _nested_value(data, status_key) if status_key else "present"
        events.append(
            _event(
                occurred_at=data.get("created_at") or _mtime(path),
                stage=stage,
                event_type="artifact",
                title=title,
                summary=f"{relpath(path, project_dir)} is {status}.",
                artifact_path=path,
                status=status,
            )
        )


def _event(
    occurred_at: Any,
    stage: str,
    event_type: str,
    title: str,
    summary: str,
    artifact_path: Path,
    status: Any,
    actor: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "occurred_at": str(occurred_at or ""),
        "stage": stage,
        "event_type": event_type,
        "title": title,
        "summary": summary,
        "status": status,
        "actor": actor,
        "artifact_path": str(artifact_path),
        "metadata": metadata or {},
    }


def _sorted_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda item: (str(item.get("occurred_at") or "9999"), str(item.get("stage")), str(item.get("title"))))


def _nested_value(data: dict[str, Any], key: str | None) -> Any:
    if not key:
        return None
    value: Any = data
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _mtime(path: Path) -> str:
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat()


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _render_markdown(timeline: dict[str, Any]) -> str:
    lines = [
        "# Project Timeline",
        "",
        f"- schema_version: {timeline['schema_version']}",
        f"- status: {timeline['status']}",
        f"- event_count: {timeline['event_count']}",
        f"- human_decision_count: {timeline['human_decision_count']}",
        f"- run_event_count: {timeline['run_event_count']}",
        f"- latest_event_at: {timeline['latest_event_at']}",
        f"- latest_event_title: {timeline['latest_event_title']}",
        "",
        "## Stage Counts",
        "",
    ]
    for stage, count in sorted(timeline["stage_counts"].items()):
        lines.append(f"- {stage}: {count}")
    lines.extend(
        [
            "",
            "## Events",
            "",
            "| Time | Stage | Type | Title | Status | Actor | Artifact |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for event in timeline["events"]:
        lines.append(
            "| {time} | {stage} | {event_type} | {title} | {status} | {actor} | `{artifact}` |".format(
                time=_cell(event.get("occurred_at")),
                stage=_cell(event.get("stage")),
                event_type=_cell(event.get("event_type")),
                title=_cell(event.get("title")),
                status=_cell(event.get("status")),
                actor=_cell(event.get("actor")),
                artifact=_cell(event.get("artifact_path")),
            )
        )
    lines.extend(["", "## Policy", "", timeline["policy"], ""])
    return "\n".join(lines)
