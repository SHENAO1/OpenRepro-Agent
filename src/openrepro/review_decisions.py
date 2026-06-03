"""Human decision records for review board items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .review_board import generate_review_board, review_board_summary
from .utils import iso_now, read_json, safe_write_text, write_json

REVIEW_DECISIONS_SCHEMA_VERSION = "1.9.1"
ALLOWED_REVIEW_DECISIONS = {"resolved", "deferred", "rejected", "needs_followup"}
CLOSED_REVIEW_DECISIONS = {"resolved", "rejected"}


def record_review_decision(
    project_dir: Path,
    item_id: str,
    decision: str,
    reviewer: str,
    note: str = "",
    followup_command: str | None = None,
) -> dict[str, Any]:
    """Append a human decision for a current review board item."""
    project_dir = Path(project_dir)
    decision = decision.strip().lower()
    if decision not in ALLOWED_REVIEW_DECISIONS:
        allowed = ", ".join(sorted(ALLOWED_REVIEW_DECISIONS))
        raise ValueError(f"Unsupported decision {decision!r}; expected one of: {allowed}")
    if not reviewer.strip():
        raise ValueError("Reviewer is required.")

    board = _current_or_generated_board(project_dir)
    item_map = {str(item.get("item_id")): item for item in board.get("items", []) if isinstance(item, dict)}
    if item_id not in item_map:
        raise ValueError(f"Review board item not found: {item_id}")

    existing = _load_decisions(project_dir)
    decisions = existing.get("decisions", [])
    decisions = decisions if isinstance(decisions, list) else []
    item = item_map[item_id]
    record = {
        "decision_id": f"D{len(decisions) + 1:03d}",
        "created_at": iso_now(),
        "item_id": item_id,
        "decision": decision,
        "reviewer": reviewer.strip(),
        "note": note,
        "followup_command": followup_command,
        "closes_item": decision in CLOSED_REVIEW_DECISIONS,
        "board_item": {
            "priority": item.get("priority"),
            "source": item.get("source"),
            "title": item.get("title"),
            "suggested_command": item.get("suggested_command"),
        },
        "policy": "Review decisions record human workflow handling only; they do not validate scientific claims.",
    }
    decisions.append(record)
    return _write_review_decisions(project_dir, decisions, board)


def generate_review_decisions(project_dir: Path) -> dict[str, Any]:
    """Write current review decision summary artifacts."""
    project_dir = Path(project_dir)
    board = _current_or_generated_board(project_dir)
    existing = _load_decisions(project_dir)
    decisions = existing.get("decisions", [])
    decisions = decisions if isinstance(decisions, list) else []
    return _write_review_decisions(project_dir, decisions, board)


def review_decision_summary(project_dir: Path) -> dict[str, Any]:
    """Return review decision status without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "review_decisions.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    board = review_board_summary(project_dir)
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", _status_from_counts(board["item_count"], board["item_count"])),
        "decision_count": int(data.get("decision_count", 0) or 0),
        "closed_count": int(data.get("closed_count", 0) or 0),
        "followup_count": int(data.get("followup_count", 0) or 0),
        "deferred_count": int(data.get("deferred_count", 0) or 0),
        "unresolved_item_count": int(data.get("unresolved_item_count", board["item_count"]) or 0),
        "top_item": data.get("top_item", board.get("top_item")),
        "top_command": data.get("top_command") or _decision_command(project_dir, board.get("top_item")),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _current_or_generated_board(project_dir: Path) -> dict[str, Any]:
    board_path = project_dir / "workspace" / "review_board.json"
    board = read_json(board_path, default={}) or {}
    if not isinstance(board, dict) or not board_path.exists():
        board = generate_review_board(project_dir)
    return board


def _load_decisions(project_dir: Path) -> dict[str, Any]:
    data = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    return data if isinstance(data, dict) else {}


def _write_review_decisions(project_dir: Path, decisions: list[dict[str, Any]], board: dict[str, Any]) -> dict[str, Any]:
    latest_by_item: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if isinstance(decision, dict) and decision.get("item_id"):
            latest_by_item[str(decision["item_id"])] = decision

    board_items = [item for item in board.get("items", []) if isinstance(item, dict)]
    closed_ids = {
        item_id
        for item_id, decision in latest_by_item.items()
        if str(decision.get("decision")) in CLOSED_REVIEW_DECISIONS
    }
    unresolved_items = [item for item in board_items if str(item.get("item_id")) not in closed_ids]
    latest_decisions = sorted(latest_by_item.values(), key=lambda item: str(item.get("item_id")))
    result = {
        "schema_version": REVIEW_DECISIONS_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_dir": str(project_dir),
        "board_schema_version": board.get("schema_version"),
        "board_item_count": int(board.get("item_count", len(board_items)) or 0),
        "status": _status_from_counts(len(board_items), len(unresolved_items)),
        "decision_count": len(decisions),
        "closed_count": sum(1 for item in latest_decisions if str(item.get("decision")) in CLOSED_REVIEW_DECISIONS),
        "followup_count": sum(1 for item in latest_decisions if str(item.get("decision")) == "needs_followup"),
        "deferred_count": sum(1 for item in latest_decisions if str(item.get("decision")) == "deferred"),
        "unresolved_item_count": len(unresolved_items),
        "top_item": str(unresolved_items[0].get("item_id")) if unresolved_items else None,
        "top_command": _decision_command(project_dir, str(unresolved_items[0].get("item_id"))) if unresolved_items else None,
        "latest_decisions": latest_decisions,
        "unresolved_items": unresolved_items,
        "decisions": decisions,
        "policy": "Review decisions record human workflow handling only; closing review items does not prove scientific reproduction success.",
    }
    write_json(project_dir / "workspace" / "review_decisions.json", result)
    safe_write_text(project_dir / "workspace" / "REVIEW_DECISIONS.md", _render_review_decisions_markdown(result))
    return result


def _status_from_counts(board_item_count: int, unresolved_item_count: int) -> str:
    if board_item_count <= 0:
        return "clear"
    if unresolved_item_count <= 0:
        return "complete"
    return "needs_decision"


def _decision_command(project_dir: Path, item_id: Any) -> str | None:
    if not item_id:
        return None
    return f"openrepro review-decision {project_dir} --item-id {item_id} --decision needs_followup --reviewer <name>"


def _render_review_decisions_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Review Decisions",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- board_item_count: {result['board_item_count']}",
        f"- decision_count: {result['decision_count']}",
        f"- closed_count: {result['closed_count']}",
        f"- followup_count: {result['followup_count']}",
        f"- deferred_count: {result['deferred_count']}",
        f"- unresolved_item_count: {result['unresolved_item_count']}",
        f"- top_item: {result['top_item']}",
        f"- top_command: {result['top_command']}",
        "",
        "## Latest Decisions",
        "",
        "| Item | Decision | Reviewer | Closes | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    if result["latest_decisions"]:
        for item in result["latest_decisions"]:
            lines.append(
                "| {item_id} | {decision} | {reviewer} | {closes} | {note} |".format(
                    item_id=item.get("item_id"),
                    decision=item.get("decision"),
                    reviewer=item.get("reviewer"),
                    closes=item.get("closes_item"),
                    note=str(item.get("note") or "").replace("|", "/"),
                )
            )
    else:
        lines.append("| none | none | none | False | No review decisions recorded. |")
    lines.extend(["", "## Unresolved Items", "", "| Priority | Source | Item | Suggested decision command |", "| --- | --- | --- | --- |"])
    if result["unresolved_items"]:
        for item in result["unresolved_items"]:
            command = _decision_command(Path(result["project_dir"]), item.get("item_id")) or ""
            lines.append(
                "| {priority} | {source} | {title} | `{command}` |".format(
                    priority=item.get("priority"),
                    source=item.get("source"),
                    title=str(item.get("title") or "").replace("|", "/"),
                    command=command,
                )
            )
    else:
        lines.append("| none | workflow | No unresolved review board items. |  |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)
