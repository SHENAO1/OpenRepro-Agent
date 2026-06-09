"""Unified evidence graph for auditable reproduction state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .claim_trace import build_claim_trace
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

EVIDENCE_GRAPH_SCHEMA_VERSION = "1.57.0"


def build_evidence_graph(project_dir: Path) -> dict[str, Any]:
    """Build an auditable graph over claims, data, experiments, runs, and reviews."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    trace = build_claim_trace(project_dir)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    _add_source_nodes(project_dir, nodes, seen_nodes)
    _add_claim_nodes(trace, nodes, edges, seen_nodes, seen_edges)
    _add_data_nodes(trace, nodes, seen_nodes)
    _add_experiment_nodes(trace, nodes, edges, seen_nodes, seen_edges)
    _add_run_nodes(trace, nodes, edges, seen_nodes, seen_edges)
    _add_review_nodes(project_dir, trace, nodes, edges, seen_nodes, seen_edges)
    _add_artifact_nodes(project_dir, nodes, edges, seen_nodes, seen_edges)

    counts = _counts(nodes)
    status, top_command = _graph_status(project_dir, counts, trace)
    graph = {
        "schema_version": EVIDENCE_GRAPH_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": top_command,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_counts": counts,
        "claim_count": counts.get("claim", 0),
        "source_count": counts.get("source", 0),
        "data_count": counts.get("data", 0),
        "experiment_count": counts.get("experiment", 0),
        "run_count": counts.get("run", 0),
        "review_decision_count": counts.get("review_decision", 0),
        "artifact_count": counts.get("artifact", 0),
        "nodes": sorted(nodes, key=lambda item: (str(item.get("kind")), str(item.get("node_id")))),
        "edges": sorted(edges, key=lambda item: (str(item.get("source")), str(item.get("target")), str(item.get("relation")))),
        "source_artifacts": _source_artifacts(project_dir),
        "guardrails": [
            "Does not run experiments.",
            "Does not validate scientific correctness.",
            "Does not promote candidate claims without human review.",
            "Does not fabricate missing evidence, data, metrics, or review decisions.",
        ],
        "policy": "Evidence graphs organize existing workflow evidence for human and supervised-agent review; they do not prove scientific reproduction.",
    }
    return graph


def generate_evidence_graph(project_dir: Path) -> dict[str, Any]:
    """Write workspace/evidence_graph.json and workspace/EVIDENCE_GRAPH.md."""
    project_dir = Path(project_dir)
    graph = build_evidence_graph(project_dir)
    write_json(project_dir / "workspace" / "evidence_graph.json", graph)
    safe_write_text(project_dir / "workspace" / "EVIDENCE_GRAPH.md", _render_markdown(graph))
    return graph


def evidence_graph_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing evidence graph summary without mutating project files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "evidence_graph.json"
    markdown_path = project_dir / "workspace" / "EVIDENCE_GRAPH.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "top_command": data.get("top_command"),
        "node_count": int(data.get("node_count", 0) or 0),
        "edge_count": int(data.get("edge_count", 0) or 0),
        "claim_count": int(data.get("claim_count", 0) or 0),
        "data_count": int(data.get("data_count", 0) or 0),
        "experiment_count": int(data.get("experiment_count", 0) or 0),
        "run_count": int(data.get("run_count", 0) or 0),
        "review_decision_count": int(data.get("review_decision_count", 0) or 0),
        "artifact_count": int(data.get("artifact_count", 0) or 0),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _add_source_nodes(project_dir: Path, nodes: list[dict[str, Any]], seen_nodes: set[str]) -> None:
    source_index = read_json(project_dir / "workspace" / "source_index.json", default={}) or {}
    sources = source_index.get("sources", []) if isinstance(source_index, dict) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_name = str(source.get("source_name") or source.get("name") or source.get("path") or "")
        if not source_name:
            continue
        copied_path = source.get("copied_path") or source.get("path")
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=f"source:{source_name}",
                kind="source",
                label=source_name,
                status=str(source.get("status") or "ingested"),
                path=str(copied_path) if copied_path else None,
                source_artifact="workspace/source_index.json",
                details={
                    "source_type": source.get("source_type"),
                    "original_path": source.get("original_path"),
                    "sha256": source.get("sha256"),
                    "page_count": source.get("page_count"),
                },
            ),
        )


def _add_claim_nodes(
    trace: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
    seen_edges: set[tuple[str, str, str]],
) -> None:
    for claim in trace.get("claims", []) if isinstance(trace.get("claims"), list) else []:
        if not isinstance(claim, dict) or not claim.get("claim_id"):
            continue
        claim_id = str(claim["claim_id"])
        source_name = claim.get("source_name")
        status = "verified_by_human" if claim.get("verified_by_human") else str(claim.get("status") or "candidate")
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=f"claim:{claim_id}",
                kind="claim",
                label=claim_id,
                status=status,
                path=None,
                source_artifact="workspace/claim_trace.json",
                details={
                    "candidate_id": claim.get("candidate_id"),
                    "claim_kind": claim.get("kind"),
                    "text": claim.get("text"),
                    "source_name": source_name,
                    "section": claim.get("section"),
                    "page_number": claim.get("page_number"),
                    "risk_level": claim.get("risk_level"),
                    "risk_flags": claim.get("risk_flags", []),
                },
            ),
        )
        if source_name:
            _add_edge(edges, seen_edges, f"source:{source_name}", f"claim:{claim_id}", "states")


def _add_data_nodes(trace: dict[str, Any], nodes: list[dict[str, Any]], seen_nodes: set[str]) -> None:
    registry = trace.get("data_registry", {}) if isinstance(trace.get("data_registry"), dict) else {}
    for data in registry.get("sources", []) if isinstance(registry.get("sources"), list) else []:
        if not isinstance(data, dict) or not data.get("data_id"):
            continue
        data_id = str(data["data_id"])
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=f"data:{data_id}",
                kind="data",
                label=data_id,
                status=str(data.get("status") or "registered"),
                path=data.get("path"),
                source_artifact="workspace/data_index.json",
                details={
                    "role": data.get("role"),
                    "sha256": data.get("sha256"),
                    "note": data.get("note"),
                    "valid": data.get("valid"),
                },
            ),
        )


def _add_experiment_nodes(
    trace: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
    seen_edges: set[tuple[str, str, str]],
) -> None:
    for experiment in trace.get("experiments", []) if isinstance(trace.get("experiments"), list) else []:
        if not isinstance(experiment, dict) or not experiment.get("experiment_id"):
            continue
        experiment_id = str(experiment["experiment_id"])
        experiment_node = f"experiment:{experiment_id}"
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=experiment_node,
                kind="experiment",
                label=experiment_id,
                status=str(experiment.get("status") or "unknown"),
                path=experiment.get("experiment_dir"),
                source_artifact="workspace/claim_trace.json",
                details={
                    "template": experiment.get("template"),
                    "spec_path": experiment.get("spec_path"),
                    "spec_sha256": experiment.get("spec_sha256"),
                    "verified_claim_ids": experiment.get("verified_claim_ids", []),
                    "registered_data_ids": experiment.get("registered_data_ids", []),
                },
            ),
        )
        for claim_id in experiment.get("claim_ids", []):
            if claim_id:
                _add_edge(edges, seen_edges, f"claim:{claim_id}", experiment_node, "scoped_by_experiment")
        for claim_id in experiment.get("verified_claim_ids", []):
            if claim_id:
                _add_edge(edges, seen_edges, f"claim:{claim_id}", experiment_node, "verified_input_for")
        for data_id in experiment.get("registered_data_ids", []):
            if data_id:
                _add_edge(edges, seen_edges, experiment_node, f"data:{data_id}", "requires_data")


def _add_run_nodes(
    trace: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
    seen_edges: set[tuple[str, str, str]],
) -> None:
    for run in trace.get("runs", []) if isinstance(trace.get("runs"), list) else []:
        if not isinstance(run, dict) or not run.get("run_id"):
            continue
        run_id = str(run["run_id"])
        experiment_id = run.get("experiment_id")
        run_node = f"run:{run_id}"
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=run_node,
                kind="run",
                label=run_id,
                status=str(run.get("quality_gate_status") or "run_evidence"),
                path=run.get("run_dir"),
                source_artifact="workspace/claim_trace.json",
                details={
                    "command": run.get("command"),
                    "experiment_id": experiment_id,
                    "template": run.get("template"),
                    "quality_gate_failed_check_names": run.get("quality_gate_failed_check_names", []),
                    "manifest_sha256": run.get("manifest_sha256"),
                },
            ),
        )
        if experiment_id:
            _add_edge(edges, seen_edges, f"experiment:{experiment_id}", run_node, "executed_as")


def _add_review_nodes(
    project_dir: Path,
    trace: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
    seen_edges: set[tuple[str, str, str]],
) -> None:
    decisions = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    decision_items = decisions.get("decisions", []) if isinstance(decisions, dict) else []
    candidate_claim_ids = {
        str(claim.get("candidate_id")): str(claim.get("claim_id"))
        for claim in trace.get("claims", [])
        if isinstance(claim, dict) and claim.get("candidate_id") and claim.get("claim_id")
    }
    for decision in decision_items if isinstance(decision_items, list) else []:
        if not isinstance(decision, dict) or not decision.get("decision_id"):
            continue
        decision_id = str(decision["decision_id"])
        item_id = str(decision.get("item_id") or "")
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=f"review_decision:{decision_id}",
                kind="review_decision",
                label=decision_id,
                status=str(decision.get("decision") or "recorded"),
                path=None,
                source_artifact="workspace/review_decisions.json",
                details={
                    "item_id": item_id,
                    "reviewer": decision.get("reviewer"),
                    "closes_item": decision.get("closes_item"),
                    "followup_command": decision.get("followup_command"),
                    "note": decision.get("note"),
                },
            ),
        )
        candidate_id = _candidate_id_from_review_item(item_id)
        claim_id = candidate_claim_ids.get(candidate_id or "")
        if claim_id:
            _add_edge(edges, seen_edges, f"review_decision:{decision_id}", f"claim:{claim_id}", "reviews")


def _add_artifact_nodes(
    project_dir: Path,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
    seen_edges: set[tuple[str, str, str]],
) -> None:
    artifacts = [
        ("claim_trace", project_dir / "workspace" / "claim_trace.json"),
        ("claim_trace_validation", project_dir / "workspace" / "claim_trace_validation.json"),
        ("paper_lineage", project_dir / "workspace" / "paper_lineage.json"),
        ("run_lineage", project_dir / "workspace" / "run_lineage.json"),
        ("review_board", project_dir / "workspace" / "review_board.json"),
        ("review_decisions", project_dir / "workspace" / "review_decisions.json"),
        ("evidence_package", project_dir / "reports" / "evidence_package.json"),
    ]
    for label, path in artifacts:
        if not path.exists():
            continue
        node_id = f"artifact:{label}"
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=node_id,
                kind="artifact",
                label=label,
                status="present",
                path=str(path),
                source_artifact=relpath(path, project_dir).replace("\\", "/"),
                details={"sha256": sha256_file(path), "size_bytes": path.stat().st_size},
            ),
        )


def _source_artifacts(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "workspace" / "source_index.json",
        project_dir / "workspace" / "claim_trace.json",
        project_dir / "workspace" / "data_index.json",
        project_dir / "workspace" / "review_decisions.json",
        project_dir / "workspace" / "run_lineage.json",
        project_dir / "workspace" / "paper_lineage.json",
    ]
    return [
        {
            "path": relpath(path, project_dir).replace("\\", "/"),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        }
        for path in paths
    ]


def _candidate_id_from_review_item(item_id: str) -> str | None:
    if item_id.startswith("candidate_") and item_id.endswith("_needs_more_evidence"):
        return item_id.removeprefix("candidate_").removesuffix("_needs_more_evidence")
    if item_id.startswith("candidate_") and item_id.endswith("_high_risk"):
        return item_id.removeprefix("candidate_").removesuffix("_high_risk")
    return None


def _node(
    node_id: str,
    kind: str,
    label: str,
    status: str,
    path: Any,
    source_artifact: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "kind": kind,
        "label": label,
        "status": status,
        "path": path,
        "source_artifact": source_artifact,
        "details": details,
    }


def _add_node(nodes: list[dict[str, Any]], seen: set[str], node: dict[str, Any]) -> None:
    if node["node_id"] in seen:
        return
    seen.add(str(node["node_id"]))
    nodes.append(node)


def _add_edge(edges: list[dict[str, Any]], seen: set[tuple[str, str, str]], source: str, target: str, relation: str) -> None:
    key = (source, target, relation)
    if key in seen:
        return
    seen.add(key)
    edges.append({"source": source, "target": target, "relation": relation})


def _counts(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        kind = str(node.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _graph_status(project_dir: Path, counts: dict[str, int], trace: dict[str, Any]) -> tuple[str, str | None]:
    if counts.get("claim", 0) == 0:
        return "needs_claim_trace", f"openrepro trace-claims {project_dir} --validate"
    if trace.get("verified_claim_count", 0) == 0:
        return "needs_human_review", f"openrepro review-candidates {project_dir} --candidate-id <id> --status verified_by_human --reviewer <name>"
    if counts.get("experiment", 0) == 0:
        return "needs_experiment", f"openrepro scaffold-experiment {project_dir} --experiment-id <id>"
    if counts.get("run", 0) == 0:
        return "needs_run", f"openrepro run-experiment {project_dir} --experiment-id <id> --confirm"
    return "ready_for_review", None


def _render_markdown(graph: dict[str, Any]) -> str:
    count_rows = "\n".join(f"| {key} | {value} |" for key, value in sorted(graph["node_counts"].items()))
    node_rows = "\n".join(
        "| {node_id} | {kind} | {status} | {source} |".format(
            node_id=_cell(node.get("node_id")),
            kind=_cell(node.get("kind")),
            status=_cell(node.get("status")),
            source=_cell(node.get("source_artifact")),
        )
        for node in graph["nodes"][:40]
    )
    edge_rows = "\n".join(
        "| {source} | {relation} | {target} |".format(
            source=_cell(edge.get("source")),
            relation=_cell(edge.get("relation")),
            target=_cell(edge.get("target")),
        )
        for edge in graph["edges"][:60]
    )
    artifact_rows = "\n".join(
        f"| {_cell(item['path'])} | {_cell(item['present'])} | {_cell(item.get('sha256'))} |"
        for item in graph["source_artifacts"]
    )
    return f"""# Evidence Graph

- schema_version: {graph['schema_version']}
- status: {graph['status']}
- top_command: {graph['top_command']}
- node_count: {graph['node_count']}
- edge_count: {graph['edge_count']}

## Node Counts

| Kind | Count |
| --- | --- |
{count_rows or "| none | 0 |"}

## Nodes

Showing the first 40 nodes.

| Node | Kind | Status | Source Artifact |
| --- | --- | --- | --- |
{node_rows or "| none | none | missing | none |"}

## Edges

Showing the first 60 edges.

| Source | Relation | Target |
| --- | --- | --- |
{edge_rows or "| none | none | none |"}

## Source Artifacts

| Artifact | Present | SHA-256 |
| --- | --- | --- |
{artifact_rows}

## Guardrails

{chr(10).join(f"- {item}" for item in graph['guardrails'])}

## Policy

{graph['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value).replace("|", "/")
    return str(value).replace("\n", " ").replace("|", "/")
