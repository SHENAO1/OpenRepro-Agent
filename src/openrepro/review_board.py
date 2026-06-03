"""Human review board aggregation for reproduction workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .advance import advance_summary
from .artifact_manager import sha256_file
from .claim_trace import claim_trace_summary
from .data_registry import data_index_summary
from .experiment_spec import inspect_experiment_specs
from .gaps import gaps_summary
from .scorecard import scorecard_summary
from .utils import iso_now, read_json, safe_write_text, write_json

REVIEW_BOARD_SCHEMA_VERSION = "1.9.0"


def generate_review_board(project_dir: Path) -> dict[str, Any]:
    """Write workspace/review_board.json and Markdown."""
    project_dir = Path(project_dir)
    items: list[dict[str, Any]] = []
    _candidate_items(project_dir, items)
    _data_items(project_dir, items)
    _spec_items(project_dir, items)
    _claim_trace_items(project_dir, items)
    _scorecard_items(project_dir, items)
    _gap_items(project_dir, items)
    _advance_items(project_dir, items)
    ordered = sorted(items, key=lambda item: (_priority_rank(item["priority"]), item["item_id"]))
    result = {
        "schema_version": REVIEW_BOARD_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "status": "clear" if not ordered else "needs_review",
        "item_count": len(ordered),
        "critical_count": sum(1 for item in ordered if item["priority"] == "critical"),
        "high_count": sum(1 for item in ordered if item["priority"] == "high"),
        "medium_count": sum(1 for item in ordered if item["priority"] == "medium"),
        "low_count": sum(1 for item in ordered if item["priority"] == "low"),
        "top_item": ordered[0]["item_id"] if ordered else None,
        "top_command": ordered[0]["suggested_command"] if ordered else None,
        "items": ordered,
        "policy": "Review boards collect human review prompts only; clearing the board does not prove scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "review_board.json", result)
    safe_write_text(project_dir / "workspace" / "REVIEW_BOARD.md", _render_review_board_markdown(result))
    return result


def review_board_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing review board summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "review_board.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "missing") if path.exists() else "missing",
        "item_count": int(data.get("item_count", 0) or 0),
        "critical_count": int(data.get("critical_count", 0) or 0),
        "high_count": int(data.get("high_count", 0) or 0),
        "medium_count": int(data.get("medium_count", 0) or 0),
        "low_count": int(data.get("low_count", 0) or 0),
        "top_item": data.get("top_item"),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _candidate_items(project_dir: Path, items: list[dict[str, Any]]) -> None:
    verified_ids = _verified_claim_ids(project_dir)
    candidate_ids = _candidate_ids(project_dir)
    reviews = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews_list = reviews.get("reviews", []) if isinstance(reviews, dict) else []
    if candidate_ids and not verified_ids:
        items.append(
            _item(
                "candidate_verification_missing",
                "high",
                "candidate_review",
                "Candidate evidence exists but no verified candidate artifact is available.",
                f"openrepro approve-candidates {project_dir} --all --reviewer <name>",
            )
        )
    for review in reviews_list:
        if not isinstance(review, dict):
            continue
        candidate_id = str(review.get("candidate_id") or "")
        if not candidate_id or candidate_id in verified_ids:
            continue
        if review.get("status") == "needs_more_evidence":
            items.append(
                _item(
                    f"candidate_{candidate_id}_needs_more_evidence",
                    "medium",
                    "candidate_review",
                    f"Candidate {candidate_id} still needs more evidence.",
                    f"openrepro review-candidates {project_dir} --candidate-id {candidate_id} --status verified_by_human --reviewer <name>",
                    {"review": review},
                )
            )
    for candidate in _high_risk_candidates(project_dir):
        claim_id = str(candidate.get("candidate_id") or "")
        if claim_id and claim_id not in verified_ids:
            items.append(
                _item(
                    f"candidate_{claim_id}_high_risk",
                    "high",
                    "candidate_risk",
                    f"High-risk candidate {claim_id} needs human review.",
                    f"openrepro review-candidates {project_dir} --candidate-id {claim_id} --status verified_by_human --reviewer <name>",
                    {"candidate": candidate},
                )
            )


def _data_items(project_dir: Path, items: list[dict[str, Any]]) -> None:
    data = data_index_summary(project_dir)
    for source in data["sources"]:
        if source.get("valid"):
            continue
        data_id = str(source.get("data_id") or "unknown")
        items.append(
            _item(
                f"data_{data_id}_{source.get('status')}",
                "high",
                "data_registry",
                f"Registered data {data_id} is {source.get('status')}.",
                f"openrepro validate-data {project_dir}",
                {"source": source},
            )
        )


def _spec_items(project_dir: Path, items: list[dict[str, Any]]) -> None:
    specs = inspect_experiment_specs(project_dir)
    for spec in specs.get("specs", []):
        if not isinstance(spec, dict):
            continue
        status = spec.get("freshness_status") or spec.get("status")
        experiment_id = str(spec.get("experiment_id") or "<id>")
        if spec.get("valid") is False or status in {"missing", "invalid"}:
            priority = "high"
        elif status == "stale":
            priority = "medium"
        else:
            continue
        items.append(
            _item(
                f"spec_{experiment_id}_{status}",
                priority,
                "experiment_spec",
                f"Experiment spec for {experiment_id} needs review: {status}.",
                f"openrepro validate-experiment-spec {project_dir} --experiment-id {experiment_id}",
                {"spec": spec},
            )
        )


def _claim_trace_items(project_dir: Path, items: list[dict[str, Any]]) -> None:
    trace = claim_trace_summary(project_dir)
    if trace["present"] and trace["validation_status"] == "passed":
        return
    if not trace["present"]:
        priority = "medium"
        message = "Claim trace artifacts are missing."
        command = f"openrepro trace-claims {project_dir} --validate"
    elif trace["validation_status"] == "missing":
        priority = "medium"
        message = "Claim trace exists but validation has not been run."
        command = f"openrepro validate-claims {project_dir}"
    else:
        priority = "high"
        message = f"Claim trace validation is {trace['validation_status']}."
        command = f"openrepro validate-claims {project_dir}"
    items.append(_item("claim_trace_review", priority, "claim_trace", message, command, {"claim_trace": trace}))


def _scorecard_items(project_dir: Path, items: list[dict[str, Any]]) -> None:
    summary = scorecard_summary(project_dir)
    if not summary["present"]:
        items.append(
            _item(
                "scorecard_missing",
                "medium",
                "scorecard",
                "Readiness scorecard is missing.",
                f"openrepro scorecard {project_dir}",
            )
        )
        return
    scorecard = read_json(project_dir / "workspace" / "reproduction_scorecard.json", default={}) or {}
    if not isinstance(scorecard, dict):
        return
    for dimension in scorecard.get("dimensions", []):
        if not isinstance(dimension, dict) or dimension.get("status") == "ready":
            continue
        key = str(dimension.get("key") or "unknown")
        priority = "high" if dimension.get("status") == "blocked" else "medium"
        recommendations = dimension.get("recommendations", []) if isinstance(dimension.get("recommendations"), list) else []
        items.append(
            _item(
                f"scorecard_{key}",
                priority,
                "scorecard",
                f"Scorecard dimension needs review: {dimension.get('label')} ({dimension.get('score')}).",
                str(recommendations[0]) if recommendations else f"openrepro scorecard {project_dir}",
                {"dimension": dimension},
            )
        )


def _gap_items(project_dir: Path, items: list[dict[str, Any]]) -> None:
    summary = gaps_summary(project_dir)
    if not summary["present"]:
        items.append(_item("gaps_missing", "medium", "gaps", "Reproduction gaps are missing.", f"openrepro gaps {project_dir}"))
        return
    gaps = read_json(project_dir / "workspace" / "reproduction_gaps.json", default={}) or {}
    if not isinstance(gaps, dict):
        return
    for gap in gaps.get("gaps", []):
        if not isinstance(gap, dict):
            continue
        priority = str(gap.get("severity") or "medium")
        if priority not in {"critical", "high", "medium", "low"}:
            priority = "medium"
        items.append(
            _item(
                f"gap_{gap.get('gap_id')}",
                priority,
                "gaps",
                str(gap.get("title") or gap.get("gap_id")),
                str(gap.get("suggested_command") or f"openrepro gaps {project_dir}"),
                {"gap": gap},
            )
        )


def _advance_items(project_dir: Path, items: list[dict[str, Any]]) -> None:
    summary = advance_summary(project_dir)
    if not summary["present"]:
        items.append(
            _item(
                "advance_plan_missing",
                "low",
                "advance",
                "Advance dry-run plan is missing.",
                f"openrepro advance {project_dir} --dry-run",
            )
        )
        return
    plan = read_json(project_dir / "workspace" / "advance_plan.json", default={}) or {}
    if not isinstance(plan, dict):
        return
    for action in plan.get("actions", []):
        if not isinstance(action, dict) or not action.get("requires_human_input"):
            continue
        items.append(
            _item(
                f"advance_{action.get('action_id')}",
                "medium",
                "advance",
                f"Advance command requires human input: {action.get('command')}",
                str(action.get("command") or f"openrepro advance {project_dir} --dry-run"),
                {"action": action},
            )
        )


def _candidate_ids(project_dir: Path) -> set[str]:
    ids: set[str] = set()
    for filename in ["formula_candidates.json", "parameter_candidates.json"]:
        data = read_json(project_dir / "workspace" / filename, default={}) or {}
        candidates = data.get("candidates", []) if isinstance(data, dict) else []
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("candidate_id"):
                ids.add(str(candidate["candidate_id"]))
    return ids


def _verified_claim_ids(project_dir: Path) -> set[str]:
    verified = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(verified, dict):
        return set()
    return {str(item) for item in verified.get("formula_candidate_ids", [])} | {
        str(item) for item in verified.get("parameter_candidate_ids", [])
    }


def _high_risk_candidates(project_dir: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for filename in ["formula_candidates.json", "parameter_candidates.json"]:
        data = read_json(project_dir / "workspace" / filename, default={}) or {}
        for candidate in data.get("candidates", []) if isinstance(data, dict) else []:
            if isinstance(candidate, dict) and candidate.get("risk_level") == "high":
                candidates.append(candidate)
    return candidates


def _item(
    item_id: str,
    priority: str,
    source: str,
    title: str,
    suggested_command: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "priority": priority,
        "source": source,
        "title": title,
        "suggested_command": suggested_command,
        "details": details or {},
        "status": "open",
    }


def _priority_rank(priority: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 4)


def _render_review_board_markdown(board: dict[str, Any]) -> str:
    lines = [
        "# Review Board",
        "",
        f"- schema_version: {board['schema_version']}",
        f"- status: {board['status']}",
        f"- item_count: {board['item_count']}",
        f"- critical_count: {board['critical_count']}",
        f"- high_count: {board['high_count']}",
        f"- medium_count: {board['medium_count']}",
        f"- top_item: {board['top_item']}",
        f"- top_command: {board['top_command']}",
        "",
        "## Items",
        "",
        "| Priority | Source | Item | Suggested command |",
        "| --- | --- | --- | --- |",
    ]
    if board["items"]:
        for item in board["items"]:
            lines.append(
                "| {priority} | {source} | {title} | `{command}` |".format(
                    priority=item["priority"],
                    source=item["source"],
                    title=item["title"],
                    command=item["suggested_command"],
                )
            )
    else:
        lines.append("| none | workflow | No open human review items found. |  |")
    lines.extend(["", "## Policy", "", board["policy"], ""])
    return "\n".join(lines)
