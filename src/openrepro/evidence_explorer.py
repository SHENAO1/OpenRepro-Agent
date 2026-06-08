"""Static paper evidence explorer generation."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .claim_evidence_binder import generate_claim_evidence_binder
from .data_registry import data_index_summary
from .paper_lineage import generate_paper_lineage
from .run_index import generate_run_index
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

EVIDENCE_EXPLORER_SCHEMA_VERSION = "1.31.0"


def generate_evidence_explorer(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write reports/evidence_explorer/index.html and manifest."""
    project_dir = Path(project_dir)
    lineage = _lineage(project_dir)
    binder = _binder(project_dir)
    run_index = _run_index(project_dir)
    data = data_index_summary(project_dir)
    explorer = {
        "schema_version": EVIDENCE_EXPLORER_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": _status(lineage, binder, run_index),
        "claim_count": int(lineage.get("claim_count", 0) or 0),
        "method_count": int(lineage.get("method_count", 0) or 0),
        "data_count": int(lineage.get("data_count", 0) or 0),
        "experiment_count": int(lineage.get("experiment_count", 0) or 0),
        "metric_count": int(lineage.get("metric_count", 0) or 0),
        "run_count": int(run_index.get("run_count", 0) or 0),
        "registered_data_count": int(data.get("registered_count", 0) or 0),
        "nodes": lineage.get("nodes", []),
        "edges": lineage.get("edges", []),
        "claims": binder.get("claims", []) if isinstance(binder.get("claims"), list) else [],
        "runs": run_index.get("runs", []),
        "data_sources": data.get("sources", []),
        "artifact_links": _artifact_links(project_dir),
        "policy": "Evidence explorers organize workflow evidence for review; they do not verify scientific correctness or claim reproduction success.",
    }
    reports = project_dir / "reports"
    explorer_dir = reports / "evidence_explorer"
    index_path = explorer_dir / "index.html"
    manifest_path = reports / "evidence_explorer_manifest.json"
    explorer["index_path"] = str(index_path)
    explorer["manifest_path"] = str(manifest_path)
    explorer["zip_path"] = str(reports / "evidence_explorer.zip") if export_zip else None
    safe_write_text(index_path, _render_html(explorer))
    write_json(manifest_path, explorer)
    if export_zip:
        explorer["zip_path"] = str(_export_zip(project_dir, explorer))
        write_json(manifest_path, explorer)
    return explorer


def evidence_explorer_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing evidence explorer summary without mutating files."""
    project_dir = Path(project_dir)
    index_path = project_dir / "reports" / "evidence_explorer" / "index.html"
    manifest_path = project_dir / "reports" / "evidence_explorer_manifest.json"
    zip_path = project_dir / "reports" / "evidence_explorer.zip"
    data = read_json(manifest_path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": index_path.exists(),
        "path": str(index_path) if index_path.exists() else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if index_path.exists() else "missing"),
        "claim_count": int(data.get("claim_count", 0) or 0),
        "run_count": int(data.get("run_count", 0) or 0),
        "sha256": sha256_file(index_path) if index_path.exists() else None,
    }


def _lineage(project_dir: Path) -> dict[str, Any]:
    lineage = read_json(project_dir / "workspace" / "paper_lineage.json", default={}) or {}
    if not isinstance(lineage, dict) or not lineage:
        lineage = generate_paper_lineage(project_dir)
    return lineage


def _binder(project_dir: Path) -> dict[str, Any]:
    binder = read_json(project_dir / "workspace" / "claim_evidence_binder.json", default={}) or {}
    if not isinstance(binder, dict) or not binder:
        binder = generate_claim_evidence_binder(project_dir)
    return binder


def _run_index(project_dir: Path) -> dict[str, Any]:
    index = read_json(project_dir / "workspace" / "run_index.json", default={}) or {}
    if not isinstance(index, dict) or not index:
        index = generate_run_index(project_dir, export_zip=False)
    return index


def _status(lineage: dict[str, Any], binder: dict[str, Any], run_index: dict[str, Any]) -> str:
    if lineage.get("status") in {"ready", "complete"} and binder.get("claim_count", 0) and run_index.get("run_count", 0):
        return "ready"
    if lineage.get("claim_count", 0) or binder.get("claim_count", 0) or run_index.get("run_count", 0):
        return "partial"
    return "empty"


def _artifact_links(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "workspace" / "PAPER_LINEAGE.md",
        project_dir / "workspace" / "CLAIM_EVIDENCE_BINDER.md",
        project_dir / "workspace" / "DATA_PROFILE.md",
        project_dir / "workspace" / "DATA_EXPECTATION_RESULTS.md",
        project_dir / "workspace" / "RUN_INDEX.md",
        project_dir / "workspace" / "EVIDENCE_QUERY.md",
        project_dir / "workspace" / "WORKFLOW_PRESET.md",
        project_dir / "workspace" / "PIPELINE_PLAN.md",
        project_dir / "workspace" / "PIPELINE_VALIDATION.md",
        project_dir / "workspace" / "ASSET_CATALOG.md",
        project_dir / "reports" / "run_explorer" / "index.html",
        project_dir / "reports" / "claim_evidence_report.md",
        project_dir / "reports" / "reviewer_packet.md",
    ]
    return [
        {
            "label": path.name,
            "path": relpath(path, project_dir).replace("\\", "/"),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        }
        for path in paths
    ]


def _export_zip(project_dir: Path, explorer: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "evidence_explorer.zip"
    files = [
        project_dir / "reports" / "evidence_explorer" / "index.html",
        project_dir / "reports" / "evidence_explorer_manifest.json",
    ]
    files.extend(project_dir / str(item["path"]) for item in explorer.get("artifact_links", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _render_html(explorer: dict[str, Any]) -> str:
    claim_rows = "\n".join(_claim_row(claim) for claim in explorer["claims"][:200])
    node_rows = "\n".join(_node_row(node) for node in explorer["nodes"][:300])
    run_rows = "\n".join(_run_row(run) for run in explorer["runs"][:200])
    data_rows = "\n".join(_data_row(source) for source in explorer["data_sources"][:100])
    link_rows = "\n".join(_link_row(link) for link in explorer["artifact_links"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Evidence Explorer - {escape(explorer['project_name'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #1f2933; --muted: #667085; --line: #d8dee8; --soft: #f7f9fc; --good: #147d64; --warn: #a15c00; --bad: #b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #fff; }}
    header {{ padding: 24px 30px 18px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 24px 28px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 30px 0 12px; font-size: 19px; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; min-height: 78px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 22px; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; }}
    .good {{ color: var(--good); background: #e8f5ef; }}
    .warn {{ color: var(--warn); background: #fff4df; }}
    .bad {{ color: var(--bad); background: #fdecec; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid var(--line); background: #fff; margin-bottom: 22px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    code {{ font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <header>
    <h1>OpenRepro Evidence Explorer: {escape(explorer['project_name'])}</h1>
    <div>Status: {_badge(explorer['status'])}</div>
    <p>Generated at {escape(explorer['created_at'])}. {escape(explorer['policy'])}</p>
  </header>
  <main>
    <section class="grid">
      <div class="metric"><span>Claims</span><strong>{explorer['claim_count']}</strong></div>
      <div class="metric"><span>Methods</span><strong>{explorer['method_count']}</strong></div>
      <div class="metric"><span>Data nodes</span><strong>{explorer['data_count']}</strong></div>
      <div class="metric"><span>Experiments</span><strong>{explorer['experiment_count']}</strong></div>
      <div class="metric"><span>Metrics</span><strong>{explorer['metric_count']}</strong></div>
      <div class="metric"><span>Runs</span><strong>{explorer['run_count']}</strong></div>
    </section>
    <section><h2>Claim Evidence</h2><table><thead><tr><th>Claim</th><th>Status</th><th>Evidence</th><th>Open action</th></tr></thead><tbody>{claim_rows}</tbody></table></section>
    <section><h2>Lineage Nodes</h2><table><thead><tr><th>Node</th><th>Kind</th><th>Status</th><th>Source</th></tr></thead><tbody>{node_rows}</tbody></table></section>
    <section><h2>Runs</h2><table><thead><tr><th>Run</th><th>Command</th><th>Experiment</th><th>Gate</th><th>Metrics</th></tr></thead><tbody>{run_rows}</tbody></table></section>
    <section><h2>Registered Data</h2><table><thead><tr><th>Data</th><th>Role</th><th>Status</th><th>Path</th></tr></thead><tbody>{data_rows}</tbody></table></section>
    <section><h2>Artifacts</h2><table><thead><tr><th>Artifact</th><th>Status</th><th>Path</th><th>SHA-256</th></tr></thead><tbody>{link_rows}</tbody></table></section>
  </main>
</body>
</html>
"""


def _claim_row(claim: dict[str, Any]) -> str:
    evidence_count = len(claim.get("evidence", [])) if isinstance(claim.get("evidence"), list) else 0
    return f"<tr><td><code>{_cell(claim.get('claim_id'))}</code><br>{_cell(claim.get('text'))}</td><td>{_badge(claim.get('status'))}</td><td>{evidence_count}</td><td>{_cell(claim.get('top_command'))}</td></tr>"


def _node_row(node: dict[str, Any]) -> str:
    return f"<tr><td><code>{_cell(node.get('node_id'))}</code><br>{_cell(node.get('label'))}</td><td>{_cell(node.get('kind'))}</td><td>{_badge(node.get('status'))}</td><td>{_cell(node.get('source'))}</td></tr>"


def _run_row(run: dict[str, Any]) -> str:
    metrics = ", ".join(f"{key}={value}" for key, value in list((run.get("metrics") or {}).items())[:5])
    return f"<tr><td><code>{_cell(run.get('run_id'))}</code></td><td>{_cell(run.get('command'))}</td><td>{_cell(run.get('experiment_id'))}</td><td>{_badge(run.get('quality_gate_status'))}</td><td>{_cell(metrics)}</td></tr>"


def _data_row(source: dict[str, Any]) -> str:
    return f"<tr><td><code>{_cell(source.get('data_id'))}</code></td><td>{_cell(source.get('role'))}</td><td>{_badge(source.get('status'))}</td><td>{_cell(source.get('registered_path') or source.get('path'))}</td></tr>"


def _link_row(link: dict[str, Any]) -> str:
    return f"<tr><td>{_cell(link.get('label'))}</td><td>{_badge('present' if link.get('present') else 'missing')}</td><td>{_cell(link.get('path'))}</td><td><code>{_cell(link.get('sha256'))}</code></td></tr>"


def _badge(value: Any) -> str:
    text = _cell(value)
    normalized = str(value).lower()
    if normalized in {"ready", "complete", "passed", "current", "present", "verified"}:
        kind = "good"
    elif normalized in {"missing", "failed", "blocked", "stale", "rejected"}:
        kind = "bad"
    else:
        kind = "warn"
    return f'<span class="badge {kind}">{text}</span>'


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value))
