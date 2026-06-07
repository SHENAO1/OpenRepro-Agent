"""Searchable query artifacts for paper evidence explorer manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_explorer import generate_evidence_explorer
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

EVIDENCE_QUERY_SCHEMA_VERSION = "1.32.0"
EVIDENCE_QUERY_KINDS = {"all", "claim", "node", "run", "data", "artifact"}


def query_evidence(
    project_dir: Path,
    *,
    kind: str = "all",
    text: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Write workspace evidence query artifacts from the evidence explorer manifest."""
    project_dir = Path(project_dir)
    normalized_kind = _normalize_kind(kind)
    bounded_limit = max(1, min(int(limit), 200))
    needle = (text or "").strip().lower()
    explorer = _explorer(project_dir)
    candidates = _query_rows(explorer)
    filtered = [
        row
        for row in candidates
        if (normalized_kind == "all" or row["kind"] == normalized_kind) and (not needle or needle in row["search_text"])
    ]
    results = [_public_row(row) for row in filtered[:bounded_limit]]
    query = {
        "schema_version": EVIDENCE_QUERY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "kind": normalized_kind,
        "text": text or None,
        "limit": bounded_limit,
        "result_count": len(results),
        "matched_count": len(filtered),
        "total_candidate_count": len(candidates),
        "results": results,
        "paths": {
            "json": str(project_dir / "workspace" / "evidence_query.json"),
            "markdown": str(project_dir / "workspace" / "EVIDENCE_QUERY.md"),
            "explorer_manifest": str(project_dir / "reports" / "evidence_explorer_manifest.json"),
        },
        "policy": "Evidence queries search workflow evidence for review; they do not verify scientific correctness or claim reproduction success.",
    }
    write_json(project_dir / "workspace" / "evidence_query.json", query)
    safe_write_text(project_dir / "workspace" / "EVIDENCE_QUERY.md", _render_markdown(query))
    return query


def evidence_query_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing evidence query summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "evidence_query.json"
    markdown_path = project_dir / "workspace" / "EVIDENCE_QUERY.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "kind": data.get("kind"),
        "text": data.get("text"),
        "result_count": int(data.get("result_count", 0) or 0),
        "matched_count": int(data.get("matched_count", 0) or 0),
        "total_candidate_count": int(data.get("total_candidate_count", 0) or 0),
        "status": "present" if path.exists() else "missing",
    }


def _normalize_kind(kind: str) -> str:
    value = (kind or "all").strip().lower()
    if value not in EVIDENCE_QUERY_KINDS:
        allowed = ", ".join(sorted(EVIDENCE_QUERY_KINDS))
        raise ValueError(f"Unknown evidence query kind: {kind}. Expected one of: {allowed}")
    return value


def _explorer(project_dir: Path) -> dict[str, Any]:
    manifest_path = project_dir / "reports" / "evidence_explorer_manifest.json"
    explorer = read_json(manifest_path, default={}) or {}
    if not isinstance(explorer, dict) or not explorer:
        explorer = generate_evidence_explorer(project_dir)
    return explorer if isinstance(explorer, dict) else {}


def _query_rows(explorer: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for claim in _list(explorer.get("claims")):
        rows.append(
            _row(
                kind="claim",
                item_id=claim.get("claim_id"),
                title=claim.get("text"),
                status=claim.get("status"),
                source=claim.get("top_command"),
                payload={
                    "evidence_count": len(claim.get("evidence", [])) if isinstance(claim.get("evidence"), list) else 0,
                    "open_action": claim.get("open_action"),
                },
                raw=claim,
            )
        )
    for node in _list(explorer.get("nodes")):
        rows.append(
            _row(
                kind="node",
                item_id=node.get("node_id"),
                title=node.get("label"),
                status=node.get("status"),
                source=node.get("source"),
                payload={"node_kind": node.get("kind")},
                raw=node,
            )
        )
    for run in _list(explorer.get("runs")):
        rows.append(
            _row(
                kind="run",
                item_id=run.get("run_id"),
                title=run.get("command") or run.get("experiment_id"),
                status=run.get("quality_gate_status") or run.get("status"),
                source=run.get("relative_path") or run.get("run_dir"),
                payload={
                    "experiment_id": run.get("experiment_id"),
                    "metrics": run.get("metrics") if isinstance(run.get("metrics"), dict) else {},
                },
                raw=run,
            )
        )
    for source in _list(explorer.get("data_sources")):
        rows.append(
            _row(
                kind="data",
                item_id=source.get("data_id"),
                title=source.get("registered_path") or source.get("path"),
                status=source.get("status"),
                source=source.get("registered_path") or source.get("path"),
                payload={"role": source.get("role"), "sha256": source.get("sha256")},
                raw=source,
            )
        )
    for artifact in _list(explorer.get("artifact_links")):
        rows.append(
            _row(
                kind="artifact",
                item_id=artifact.get("path") or artifact.get("label"),
                title=artifact.get("label"),
                status="present" if artifact.get("present") else "missing",
                source=artifact.get("path"),
                payload={"sha256": artifact.get("sha256")},
                raw=artifact,
            )
        )
    return rows


def _row(
    *,
    kind: str,
    item_id: Any,
    title: Any,
    status: Any,
    source: Any,
    payload: dict[str, Any],
    raw: dict[str, Any],
) -> dict[str, Any]:
    public = {
        "kind": kind,
        "id": _string(item_id),
        "title": _string(title),
        "status": _string(status),
        "source": _string(source),
        "payload": payload,
    }
    public["search_text"] = _search_text(public, raw)
    return public


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "search_text"}


def _list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _search_text(public: dict[str, Any], raw: dict[str, Any]) -> str:
    return " ".join(
        [
            json.dumps(public, ensure_ascii=False, sort_keys=True, default=str),
            json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str),
        ]
    ).lower()


def _render_markdown(query: dict[str, Any]) -> str:
    lines = [
        "# Evidence Query",
        "",
        f"- schema_version: {query['schema_version']}",
        f"- kind: {query['kind']}",
        f"- text: {query['text']}",
        f"- result_count: {query['result_count']}",
        f"- matched_count: {query['matched_count']}",
        f"- total_candidate_count: {query['total_candidate_count']}",
        "",
        "## Results",
        "",
        "| Kind | ID | Title | Status | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in query["results"]:
        lines.append(
            "| {kind} | {item_id} | {title} | {status} | {source} |".format(
                kind=_cell(result["kind"]),
                item_id=_cell(result["id"]),
                title=_cell(result["title"]),
                status=_cell(result["status"]),
                source=_cell(_source(result["source"], query["project_dir"])),
            )
        )
    lines.extend(["", "## Policy", "", query["policy"], ""])
    return "\n".join(lines)


def _source(source: str, project_dir: str) -> str:
    if not source:
        return ""
    path = Path(source)
    try:
        if path.is_absolute():
            return relpath(path, Path(project_dir)).replace("\\", "/")
    except ValueError:
        return source
    return source


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
