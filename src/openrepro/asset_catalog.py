"""Unified project asset catalog generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import list_run_dirs, sha256_file
from .data_registry import data_index_summary
from .run_index import generate_run_index
from .utils import iso_now, read_json, relpath, safe_write_text, slugify, write_json

ASSET_CATALOG_SCHEMA_VERSION = "1.35.0"
CATALOG_OUTPUTS = {
    "workspace/asset_catalog.json",
    "workspace/ASSET_CATALOG.md",
    "workspace/ASSET_CATALOG_GRAPH.md",
    "workspace/asset_build_plan.json",
    "workspace/ASSET_BUILD_PLAN.md",
    "workspace/asset_materialization.json",
    "workspace/ASSET_MATERIALIZATION.md",
    "workspace/artifact_cache.json",
    "workspace/ARTIFACT_CACHE.md",
    "workspace/artifact_cache_validation.json",
    "workspace/ARTIFACT_CACHE_VALIDATION.md",
    "workspace/artifact_cache_remotes.json",
    "workspace/ARTIFACT_CACHE_REMOTES.md",
    "workspace/artifact_cache_push.json",
    "workspace/ARTIFACT_CACHE_PUSH.md",
    "workspace/artifact_cache_pull.json",
    "workspace/ARTIFACT_CACHE_PULL.md",
    "workspace/cache_restore_plan.json",
    "workspace/CACHE_RESTORE_PLAN.md",
    "workspace/evaluation_registry.json",
    "workspace/EVALUATION_REGISTRY.md",
    "workspace/evaluation_results.json",
    "workspace/EVALUATION_RESULTS.md",
    "workspace/experiment_leaderboard.json",
    "workspace/EXPERIMENT_LEADERBOARD.md",
    "workspace/agent_sandbox_run.json",
    "workspace/AGENT_SANDBOX_RUN.md",
    "workspace/agent_sandbox_trajectory.jsonl",
    "workspace/ci_summary.json",
    "workspace/CI_SUMMARY.md",
    "workspace/ci_validation.json",
    "workspace/CI_VALIDATION.md",
    "workspace/local_ui_summary.json",
    "workspace/LOCAL_UI_SUMMARY.md",
    "workspace/plugin_registry.json",
    "workspace/PLUGIN_REGISTRY.md",
    "workspace/plugin_validation.json",
    "workspace/PLUGIN_VALIDATION.md",
    "workspace/promotion_plan.json",
    "workspace/PROMOTION_PLAN.md",
    "workspace/promotion_record.json",
    "workspace/PROMOTION_RECORD.md",
    "workspace/promotion_registry.json",
    "workspace/PROMOTION_REGISTRY.md",
    "workspace/github_pr_summary.json",
    "workspace/GITHUB_PR_SUMMARY.md",
}
CATALOG_ROOTS = ("sources", "data", "experiments", "outputs", "workspace", "reports", "handoff")


def generate_asset_catalog(project_dir: Path) -> dict[str, Any]:
    """Write a unified catalog of project files and logical workflow assets."""
    project_dir = Path(project_dir)
    assets = _dedupe_assets(
        [
            *_logical_assets(project_dir),
            *_file_assets(project_dir),
        ]
    )
    kind_counts = _count_by_key(assets, "kind")
    status_counts = _count_by_key(assets, "status")
    catalog = {
        "schema_version": ASSET_CATALOG_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if assets else "empty",
        "asset_count": len(assets),
        "kind_counts": kind_counts,
        "status_counts": status_counts,
        "assets": assets,
        "paths": {
            "json": str(project_dir / "workspace" / "asset_catalog.json"),
            "markdown": str(project_dir / "workspace" / "ASSET_CATALOG.md"),
            "graph": str(project_dir / "workspace" / "ASSET_CATALOG_GRAPH.md"),
        },
        "policy": "Asset catalogs organize observed workflow files and logical assets only; they do not verify scientific correctness.",
    }
    write_json(project_dir / "workspace" / "asset_catalog.json", catalog)
    safe_write_text(project_dir / "workspace" / "ASSET_CATALOG.md", _render_markdown(catalog))
    safe_write_text(project_dir / "workspace" / "ASSET_CATALOG_GRAPH.md", _render_graph_markdown(catalog))
    return catalog


def asset_catalog_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing asset catalog summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "asset_catalog.json"
    markdown_path = project_dir / "workspace" / "ASSET_CATALOG.md"
    graph_path = project_dir / "workspace" / "ASSET_CATALOG_GRAPH.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "graph_path": str(graph_path) if graph_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "asset_count": int(data.get("asset_count", 0) or 0),
        "kind_counts": data.get("kind_counts", {}) if isinstance(data.get("kind_counts"), dict) else {},
    }


def list_catalog_assets(project_dir: Path, *, kind: str = "all") -> dict[str, Any]:
    """Return catalog assets, generating the catalog when missing."""
    catalog = _catalog(project_dir)
    normalized_kind = (kind or "all").strip().lower()
    assets = catalog.get("assets", []) if isinstance(catalog.get("assets"), list) else []
    if normalized_kind != "all":
        assets = [asset for asset in assets if asset.get("kind") == normalized_kind]
    return {
        "schema_version": ASSET_CATALOG_SCHEMA_VERSION,
        "project_dir": str(Path(project_dir)),
        "kind": normalized_kind,
        "asset_count": len(assets),
        "assets": assets,
    }


def get_catalog_asset(project_dir: Path, asset_id: str) -> dict[str, Any]:
    """Return one catalog asset by id."""
    catalog = _catalog(project_dir)
    for asset in catalog.get("assets", []):
        if isinstance(asset, dict) and asset.get("asset_id") == asset_id:
            return asset
    raise ValueError(f"Asset not found: {asset_id}")


def generate_asset_catalog_graph(project_dir: Path) -> dict[str, Any]:
    """Regenerate the asset catalog graph markdown."""
    catalog = _catalog(project_dir)
    graph_path = Path(project_dir) / "workspace" / "ASSET_CATALOG_GRAPH.md"
    safe_write_text(graph_path, _render_graph_markdown(catalog))
    return {
        "schema_version": ASSET_CATALOG_SCHEMA_VERSION,
        "project_dir": str(Path(project_dir)),
        "status": "ready",
        "asset_count": int(catalog.get("asset_count", 0) or 0),
        "path": str(graph_path),
    }


def _catalog(project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    catalog = read_json(project_dir / "workspace" / "asset_catalog.json", default={}) or {}
    if not isinstance(catalog, dict) or not catalog:
        catalog = generate_asset_catalog(project_dir)
    return catalog


def _logical_assets(project_dir: Path) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    config = project_dir / "project_config.yaml"
    if config.exists():
        assets.append(_file_asset(project_dir, config, kind="config", label="project_config.yaml"))
    pipeline = project_dir / "openrepro.pipeline.yaml"
    if pipeline.exists():
        assets.append(_file_asset(project_dir, pipeline, kind="config", label="openrepro.pipeline.yaml"))
    data = data_index_summary(project_dir)
    for source in data.get("sources", []):
        assets.append(
            {
                "asset_id": str(source.get("data_id") or _asset_id("data", source.get("registered_path"))),
                "kind": "data",
                "label": str(source.get("data_id") or source.get("registered_path") or "data"),
                "path": str(source.get("registered_path") or source.get("path") or ""),
                "present": bool(source.get("status") == "current"),
                "status": str(source.get("status") or "unknown"),
                "size_bytes": source.get("current_size_bytes") or source.get("size_bytes"),
                "sha256": source.get("current_sha256") or source.get("sha256"),
                "metadata": {"role": source.get("role"), "path_mode": source.get("path_mode")},
                "relations": [],
            }
        )
    for experiment_dir in sorted((project_dir / "experiments").glob("*")) if (project_dir / "experiments").exists() else []:
        if experiment_dir.is_dir():
            assets.append(_directory_asset(project_dir, experiment_dir, kind="experiment"))
    for run_dir in list_run_dirs(project_dir):
        assets.append(_directory_asset(project_dir, run_dir, kind="run"))
    for run in _run_index(project_dir).get("runs", []):
        if isinstance(run, dict):
            assets.append(
                {
                    "asset_id": _asset_id("run", run.get("relative_path") or run.get("run_id")),
                    "kind": "run",
                    "label": str(run.get("run_id") or "run"),
                    "path": str(run.get("relative_path") or ""),
                    "present": True,
                    "status": str(run.get("quality_gate_status") or "observed"),
                    "size_bytes": None,
                    "sha256": run.get("manifest_sha256"),
                    "metadata": {
                        "command": run.get("command"),
                        "experiment_id": run.get("experiment_id"),
                        "metric_count": run.get("metric_count"),
                    },
                    "relations": _run_relations(run),
                }
            )
    return assets


def _file_assets(project_dir: Path) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for root_name in CATALOG_ROOTS:
        root = project_dir / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            relative = relpath(path, project_dir).replace("\\", "/")
            if relative in CATALOG_OUTPUTS:
                continue
            assets.append(_file_asset(project_dir, path, kind=_kind_for_path(relative)))
    return assets


def _file_asset(project_dir: Path, path: Path, *, kind: str, label: str | None = None) -> dict[str, Any]:
    relative = relpath(path, project_dir).replace("\\", "/")
    return {
        "asset_id": _asset_id(kind, relative),
        "kind": kind,
        "label": label or path.name,
        "path": relative,
        "present": path.exists(),
        "status": "present" if path.exists() else "missing",
        "size_bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        "metadata": {"suffix": path.suffix.lower()},
        "relations": _path_relations(relative),
    }


def _directory_asset(project_dir: Path, path: Path, *, kind: str) -> dict[str, Any]:
    relative = relpath(path, project_dir).replace("\\", "/")
    files = [item for item in path.rglob("*") if item.is_file()]
    return {
        "asset_id": _asset_id(kind, relative),
        "kind": kind,
        "label": path.name,
        "path": relative,
        "present": path.exists(),
        "status": "present" if path.exists() else "missing",
        "size_bytes": sum(item.stat().st_size for item in files),
        "sha256": None,
        "metadata": {"file_count": len(files)},
        "relations": _path_relations(relative),
    }


def _run_index(project_dir: Path) -> dict[str, Any]:
    index = read_json(project_dir / "workspace" / "run_index.json", default={}) or {}
    if not isinstance(index, dict) or not index:
        index = generate_run_index(project_dir)
    return index if isinstance(index, dict) else {}


def _kind_for_path(relative: str) -> str:
    root = relative.split("/", 1)[0]
    if root == "sources":
        return "source"
    if root == "data":
        return "data_file"
    if root == "experiments":
        return "experiment_artifact"
    if root == "outputs":
        return "run_artifact"
    if root == "workspace":
        return "workspace_artifact"
    if root == "reports":
        return "report"
    if root == "handoff":
        return "handoff"
    return "file"


def _path_relations(relative: str) -> list[dict[str, str]]:
    parts = relative.split("/")
    relations: list[dict[str, str]] = []
    if parts and parts[0] in CATALOG_ROOTS:
        relations.append({"type": "under", "target": parts[0]})
    if len(parts) >= 2 and parts[0] in {"experiments", "outputs"}:
        relations.append({"type": "contained_by", "target": "/".join(parts[:2])})
    return relations


def _run_relations(run: dict[str, Any]) -> list[dict[str, str]]:
    relations = []
    if run.get("experiment_id"):
        relations.append({"type": "produced_by_experiment", "target": str(run["experiment_id"])})
    if run.get("relative_path"):
        relations.append({"type": "stored_at", "target": str(run["relative_path"])})
    return relations


def _asset_id(kind: str, value: Any) -> str:
    return slugify(f"{kind}_{value}")[:120]


def _dedupe_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for asset in assets:
        asset_id = str(asset.get("asset_id") or _asset_id(asset.get("kind", "asset"), asset.get("path")))
        asset["asset_id"] = asset_id
        if asset_id not in deduped:
            deduped[asset_id] = asset
            continue
        existing = deduped[asset_id]
        existing_relations = existing.setdefault("relations", [])
        for relation in asset.get("relations", []):
            if relation not in existing_relations:
                existing_relations.append(relation)
        existing_metadata = existing.setdefault("metadata", {})
        existing_metadata.update(asset.get("metadata", {}))
    return sorted(deduped.values(), key=lambda item: (str(item.get("kind")), str(item.get("path")), str(item.get("asset_id"))))


def _count_by_key(assets: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in assets:
        value = str(asset.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _render_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# Asset Catalog",
        "",
        f"- schema_version: {catalog['schema_version']}",
        f"- status: {catalog['status']}",
        f"- asset_count: {catalog['asset_count']}",
        f"- kind_counts: {catalog['kind_counts']}",
        "",
        "| Asset | Kind | Status | Path | SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for asset in catalog["assets"]:
        lines.append(
            "| {asset_id} | {kind} | {status} | `{path}` | `{sha}` |".format(
                asset_id=_cell(asset.get("asset_id")),
                kind=_cell(asset.get("kind")),
                status=_cell(asset.get("status")),
                path=_cell(asset.get("path")),
                sha=_cell(str(asset.get("sha256") or "")[:12]),
            )
        )
    lines.extend(["", "## Policy", "", catalog["policy"], ""])
    return "\n".join(lines)


def _render_graph_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# Asset Catalog Graph",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    roots = sorted({asset.get("path", "").split("/", 1)[0] for asset in catalog.get("assets", []) if asset.get("path")})
    for root in roots:
        lines.append(f"  root_{slugify(root)}[\"{_mermaid(root)}\"]")
    for asset in catalog.get("assets", [])[:250]:
        asset_id = str(asset.get("asset_id"))
        node = f"asset_{slugify(asset_id)}"
        label = f"{asset.get('kind')}: {asset.get('label') or asset_id}"
        lines.append(f"  {node}[\"{_mermaid(label)}\"]")
        path = str(asset.get("path") or "")
        root = path.split("/", 1)[0] if path else ""
        if root:
            lines.append(f"  root_{slugify(root)} --> {node}")
        for relation in asset.get("relations", [])[:3]:
            if relation.get("target"):
                target = f"ref_{slugify(relation['target'])}"
                lines.append(f"  {target}[\"{_mermaid(relation['target'])}\"]")
                lines.append(f"  {node} -. {relation.get('type', 'relates')} .-> {target}")
    lines.extend(["```", "", catalog["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")


def _mermaid(value: Any) -> str:
    return str(value).replace('"', "'").replace("\n", " ")
