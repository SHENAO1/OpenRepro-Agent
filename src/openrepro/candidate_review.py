"""Candidate listing and review lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .approval import approve_candidates, load_verified_candidates
from .utils import iso_now, read_json, safe_write_text, write_json

REVIEW_SCHEMA_VERSION = "0.7.1"
REVIEW_STATUSES = {"verified_by_human", "rejected_by_human", "needs_more_evidence"}


def _load_candidates(project_dir: Path, filename: str, candidate_type: str) -> list[dict[str, Any]]:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    result = []
    for item in candidates:
        if isinstance(item, dict) and item.get("candidate_id"):
            normalized = dict(item)
            normalized["candidate_type"] = candidate_type
            result.append(normalized)
    return result


def _candidate_records(project_dir: Path) -> list[dict[str, Any]]:
    return _load_candidates(project_dir, "formula_candidates.json", "formula") + _load_candidates(
        project_dir,
        "parameter_candidates.json",
        "parameter",
    )


def _review_map(project_dir: Path) -> dict[str, dict[str, Any]]:
    data = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews = data.get("reviews", []) if isinstance(data, dict) else []
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        if isinstance(review, dict) and review.get("candidate_id"):
            latest[str(review["candidate_id"])] = review
    return latest


def list_candidates(project_dir: Path, status: str | None = None) -> dict[str, Any]:
    """List formula and parameter candidates with latest review status."""
    project_dir = Path(project_dir)
    reviews = _review_map(project_dir)
    verified = load_verified_candidates(project_dir)
    verified_ids = set(str(item) for item in verified.get("formula_candidate_ids", []))
    verified_ids.update(str(item) for item in verified.get("parameter_candidate_ids", []))
    records = []
    for candidate in _candidate_records(project_dir):
        candidate_id = str(candidate["candidate_id"])
        latest_review = reviews.get(candidate_id)
        review_status = (
            latest_review.get("status")
            if latest_review
            else "verified_by_human"
            if candidate_id in verified_ids
            else candidate.get("status", "candidate_unverified")
        )
        record = dict(candidate)
        record["review_status"] = review_status
        record["reviewer"] = latest_review.get("reviewer") if latest_review else None
        record["review_note"] = latest_review.get("note") if latest_review else None
        record["reviewed_at"] = latest_review.get("reviewed_at") if latest_review else None
        if status is None or record["review_status"] == status:
            records.append(record)
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "candidate_count": len(records),
        "candidates": records,
    }


def review_candidates(
    project_dir: Path,
    candidate_ids: list[str],
    status: str,
    reviewer: str = "human",
    note: str = "",
) -> dict[str, Any]:
    """Record a human review status for selected candidate ids."""
    project_dir = Path(project_dir)
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    if not candidate_ids:
        raise ValueError("At least one --candidate-id is required.")

    candidates = {str(item["candidate_id"]): item for item in _candidate_records(project_dir)}
    missing = [candidate_id for candidate_id in candidate_ids if candidate_id not in candidates]
    if missing:
        raise ValueError(f"Unknown candidate id(s): {', '.join(missing)}")

    existing = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews = existing.get("reviews", []) if isinstance(existing, dict) else []
    reviewed_at = iso_now()
    new_reviews = []
    for candidate_id in candidate_ids:
        candidate = candidates[candidate_id]
        review = {
            "candidate_id": candidate_id,
            "candidate_type": candidate["candidate_type"],
            "source_name": candidate.get("source_name"),
            "status": status,
            "reviewer": reviewer,
            "note": note,
            "reviewed_at": reviewed_at,
            "evidence": candidate.get("evidence"),
            "name": candidate.get("name"),
            "value": candidate.get("value"),
            "unit": candidate.get("unit"),
        }
        reviews.append(review)
        new_reviews.append(review)

    result = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "created_at": reviewed_at,
        "project_dir": str(project_dir),
        "review_count": len(reviews),
        "latest_review_count": len(new_reviews),
        "reviews": reviews,
        "policy": "Candidate reviews record human workflow state; they do not claim paper reproduction success.",
    }
    workspace = project_dir / "workspace"
    write_json(workspace / "candidate_reviews.json", result)
    safe_write_text(workspace / "CANDIDATE_REVIEWS.md", _render_reviews(result))

    if status == "verified_by_human":
        formula_ids = [item["candidate_id"] for item in new_reviews if item["candidate_type"] == "formula"]
        parameter_ids = [item["candidate_id"] for item in new_reviews if item["candidate_type"] == "parameter"]
        approve_candidates(
            project_dir,
            formula_ids=formula_ids,
            parameter_ids=parameter_ids,
            reviewer=reviewer,
            verification_note=note,
        )
    return result


def _render_reviews(result: dict[str, Any]) -> str:
    lines = [
        "# Candidate Reviews",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- review_count: {result['review_count']}",
        "",
        "| Candidate | Type | Status | Reviewer | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in result["reviews"]:
        lines.append(
            f"| {item.get('candidate_id')} | {item.get('candidate_type')} | {item.get('status')} | {item.get('reviewer')} | {item.get('note') or ''} |"
        )
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
