"""Paper-level claim/method/data/experiment/metric lineage graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .claim_trace import generate_claim_trace
from .utils import iso_now, read_json, safe_write_text, write_json

PAPER_LINEAGE_SCHEMA_VERSION = "1.26.0"


def generate_paper_lineage(project_dir: Path) -> dict[str, Any]:
    """Write workspace/paper_lineage.json and workspace/PAPER_LINEAGE.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    lineage = build_paper_lineage(project_dir)
    write_json(project_dir / "workspace" / "paper_lineage.json", lineage)
    safe_write_text(project_dir / "workspace" / "PAPER_LINEAGE.md", _render_markdown(lineage))
    return lineage


def build_paper_lineage(project_dir: Path) -> dict[str, Any]:
    """Build paper lineage payload without writing files."""
    project_dir = Path(project_dir)
    trace = _claim_trace(project_dir)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    for claim in trace.get("claims", []) if isinstance(trace.get("claims", []), list) else []:
        if not isinstance(claim, dict):
            continue
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=f"claim:{claim.get('claim_id')}",
                kind="claim",
                label=str(claim.get("claim_id")),
                status="verified" if claim.get("verified_by_human") else str(claim.get("status") or "candidate"),
                source=claim.get("source_name"),
                details={
                    "text": claim.get("text"),
                    "section": claim.get("section"),
                    "page_number": claim.get("page_number"),
                    "risk_level": claim.get("risk_level"),
                    "risk_flags": claim.get("risk_flags", []),
                },
            ),
        )

    for data in trace.get("data_registry", {}).get("sources", []) if isinstance(trace.get("data_registry"), dict) else []:
        if not isinstance(data, dict) or not data.get("data_id"):
            continue
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=f"data:{data.get('data_id')}",
                kind="data",
                label=str(data.get("data_id")),
                status=str(data.get("status") or "registered"),
                source=data.get("path"),
                details={"role": data.get("role"), "sha256": data.get("sha256"), "note": data.get("note")},
            ),
        )

    for experiment in trace.get("experiments", []) if isinstance(trace.get("experiments", []), list) else []:
        if not isinstance(experiment, dict) or not experiment.get("experiment_id"):
            continue
        experiment_id = str(experiment["experiment_id"])
        method_id = f"method:{experiment_id}"
        experiment_node_id = f"experiment:{experiment_id}"
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=method_id,
                kind="method",
                label=str(experiment.get("template") or experiment_id),
                status=str(experiment.get("status") or "candidate"),
                source=experiment.get("spec_path"),
                details={"experiment_id": experiment_id, "template": experiment.get("template")},
            ),
        )
        _add_node(
            nodes,
            seen_nodes,
            _node(
                node_id=experiment_node_id,
                kind="experiment",
                label=experiment_id,
                status=str(experiment.get("status") or "candidate"),
                source=experiment.get("experiment_dir"),
                details={"template": experiment.get("template"), "spec_sha256": experiment.get("spec_sha256")},
            ),
        )
        for claim_id in experiment.get("claim_ids", []):
            _add_edge(edges, seen_edges, f"claim:{claim_id}", method_id, "supports_method")
        _add_edge(edges, seen_edges, method_id, experiment_node_id, "implemented_as")
        for data_id in experiment.get("registered_data_ids", []):
            if data_id:
                _add_edge(edges, seen_edges, method_id, f"data:{data_id}", "requires_data")
                _add_edge(edges, seen_edges, f"data:{data_id}", experiment_node_id, "used_by")

    _add_metric_nodes(project_dir, trace, nodes, edges, seen_nodes, seen_edges)
    counts = _counts(nodes)
    status, top_command = _lineage_status(project_dir, counts)
    return {
        "schema_version": PAPER_LINEAGE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": top_command,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "claim_count": counts.get("claim", 0),
        "method_count": counts.get("method", 0),
        "data_count": counts.get("data", 0),
        "experiment_count": counts.get("experiment", 0),
        "metric_count": counts.get("metric", 0),
        "nodes": nodes,
        "edges": edges,
        "source": {
            "claim_trace_status": "present" if (project_dir / "workspace" / "claim_trace.json").exists() else "generated",
            "claim_trace_claim_count": trace.get("claim_count", 0),
            "claim_trace_experiment_count": trace.get("experiment_trace_count", 0),
            "claim_trace_run_count": trace.get("run_trace_count", 0),
            "registered_data_count": trace.get("registered_data_count", 0),
        },
        "guardrails": [
            "Does not run experiments.",
            "Does not verify scientific correctness.",
            "Does not infer missing paper claims beyond existing workflow artifacts.",
            "Does not fabricate data, methods, metrics, or results.",
        ],
        "policy": "Paper lineage organizes existing workflow evidence only; it does not claim scientific reproduction success.",
    }


def paper_lineage_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing paper lineage summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "paper_lineage.json"
    markdown_path = project_dir / "workspace" / "PAPER_LINEAGE.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "node_count": int(data.get("node_count", 0) or 0),
        "edge_count": int(data.get("edge_count", 0) or 0),
        "claim_count": int(data.get("claim_count", 0) or 0),
        "method_count": int(data.get("method_count", 0) or 0),
        "data_count": int(data.get("data_count", 0) or 0),
        "experiment_count": int(data.get("experiment_count", 0) or 0),
        "metric_count": int(data.get("metric_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _claim_trace(project_dir: Path) -> dict[str, Any]:
    trace = read_json(project_dir / "workspace" / "claim_trace.json", default={}) or {}
    if not isinstance(trace, dict) or not trace:
        trace = generate_claim_trace(project_dir)
    return trace


def _node(node_id: str, kind: str, label: str, status: str, source: Any, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "kind": kind,
        "label": label,
        "status": status,
        "source": source,
        "details": details,
    }


def _add_node(nodes: list[dict[str, Any]], seen: set[str], node: dict[str, Any]) -> None:
    if node["node_id"] in seen:
        return
    seen.add(node["node_id"])
    nodes.append(node)


def _add_edge(edges: list[dict[str, Any]], seen: set[tuple[str, str, str]], source: str, target: str, relation: str) -> None:
    key = (source, target, relation)
    if key in seen:
        return
    seen.add(key)
    edges.append({"source": source, "target": target, "relation": relation})


def _add_metric_nodes(
    project_dir: Path,
    trace: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
    seen_edges: set[tuple[str, str, str]],
) -> None:
    run_by_id = {str(run.get("run_id")): run for run in trace.get("runs", []) if isinstance(run, dict)}
    for run_dir in list_run_dirs(project_dir):
        run_id = run_dir.name
        run = run_by_id.get(run_id, {})
        experiment_id = run.get("experiment_id")
        experiment_node_id = f"experiment:{experiment_id}" if experiment_id else f"experiment:run:{run_id}"
        if not experiment_id:
            _add_node(
                nodes,
                seen_nodes,
                _node(
                    node_id=experiment_node_id,
                    kind="experiment",
                    label=str(run.get("command") or run_id),
                    status=str(run.get("quality_gate_status") or "run_evidence"),
                    source=str(run_dir),
                    details={"run_id": run_id, "command": run.get("command")},
                ),
            )
        metrics = _run_metrics(run_dir)
        for metric_name, metric_value in metrics.items():
            metric_id = f"metric:{run_id}:{metric_name}"
            _add_node(
                nodes,
                seen_nodes,
                _node(
                    node_id=metric_id,
                    kind="metric",
                    label=metric_name,
                    status=str(run.get("quality_gate_status") or "recorded"),
                    source=str(run_dir),
                    details={"run_id": run_id, "value": metric_value},
                ),
            )
            _add_edge(edges, seen_edges, experiment_node_id, metric_id, "records_metric")


def _run_metrics(run_dir: Path) -> dict[str, Any]:
    candidates = [
        run_dir / "data" / "demo_metrics.json",
        run_dir / "data" / "execution_result.json",
    ]
    metrics: dict[str, Any] = {}
    for path in candidates:
        data = read_json(path, default={}) or {}
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if isinstance(value, (int, float, str, bool)) or value is None:
                metrics[str(key)] = value
    sweep = read_json(run_dir / "data" / "sweep_results.json", default={}) or {}
    if isinstance(sweep, dict) and isinstance(sweep.get("results"), list):
        metrics["sweep_result_count"] = len(sweep["results"])
    return metrics


def _counts(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        kind = str(node.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _lineage_status(project_dir: Path, counts: dict[str, int]) -> tuple[str, str | None]:
    if counts.get("claim", 0) == 0:
        return "needs_claim_trace", f"openrepro trace-claims {project_dir} --validate"
    if counts.get("method", 0) == 0 or counts.get("experiment", 0) == 0:
        return "partial", f"openrepro scaffold-experiment {project_dir} --experiment-id <id>"
    if counts.get("metric", 0) == 0:
        return "partial", f"openrepro run-experiment {project_dir} --experiment-id <id> --confirm"
    return "ready", None


def _render_markdown(lineage: dict[str, Any]) -> str:
    node_rows = [
        "| Node | Kind | Label | Status | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for node in lineage["nodes"]:
        node_rows.append(
            "| {node_id} | {kind} | {label} | {status} | `{source}` |".format(
                node_id=_cell(node["node_id"]),
                kind=_cell(node["kind"]),
                label=_cell(node["label"]),
                status=_cell(node["status"]),
                source=_cell(node.get("source")),
            )
        )
    edge_rows = [
        "| Source | Relation | Target |",
        "| --- | --- | --- |",
    ]
    for edge in lineage["edges"]:
        edge_rows.append(
            "| {source} | {relation} | {target} |".format(
                source=_cell(edge["source"]),
                relation=_cell(edge["relation"]),
                target=_cell(edge["target"]),
            )
        )
    guardrails = "\n".join(f"- {item}" for item in lineage["guardrails"])
    return f"""# Paper Lineage

- schema_version: {lineage['schema_version']}
- created_at: {lineage['created_at']}
- project_name: {lineage['project_name']}
- status: {lineage['status']}
- top_command: {lineage['top_command']}
- node_count: {lineage['node_count']}
- edge_count: {lineage['edge_count']}
- claim_count: {lineage['claim_count']}
- method_count: {lineage['method_count']}
- data_count: {lineage['data_count']}
- experiment_count: {lineage['experiment_count']}
- metric_count: {lineage['metric_count']}

## Nodes

{chr(10).join(node_rows)}

## Edges

{chr(10).join(edge_rows)}

## Guardrails

{guardrails}

## Policy

{lineage['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
