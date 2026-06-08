"""Declarative integration exports for external reproducibility tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .artifact_manager import latest_run_dir
from .utils import iso_now, read_json, safe_write_text, write_json, write_yaml

INTEGRATION_SCHEMA_VERSION = "1.52.0"
SUPPORTED_INTEGRATIONS = ("mlflow", "aim", "dvc", "hydra")


def export_integrations(project_dir: Path, targets: list[str] | None = None) -> dict[str, Any]:
    """Write optional adapter artifacts without importing or executing external tools."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    selected = _normalize_targets(targets)
    context = _project_context(project_dir)
    output_dir = project_dir / "integrations"
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = []
    for target in selected:
        artifacts.append(_write_target(project_dir, output_dir, target, context))

    result = {
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "openrepro_version": __version__,
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready",
        "target_count": len(selected),
        "targets": selected,
        "artifacts": artifacts,
        "context": context,
        "guardrails": [
            "Integration export writes adapter files only.",
            "No external integration package is imported or executed.",
            "Generated files are starting points for supervised MLflow, Aim, DVC, or Hydra setup.",
        ],
        "policy": "Integration exports describe interoperability surfaces only; they do not run experiments or verify scientific outputs.",
    }
    write_json(project_dir / "workspace" / "integrations.json", result)
    safe_write_text(project_dir / "workspace" / "INTEGRATIONS.md", _render_markdown(result))
    return result


def integrations_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing integration export summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "integrations.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(project_dir / "workspace" / "INTEGRATIONS.md") if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "target_count": int(data.get("target_count", 0) or 0),
        "targets": list(data.get("targets", [])) if isinstance(data.get("targets"), list) else [],
    }


def _normalize_targets(targets: list[str] | None) -> list[str]:
    if not targets:
        return list(SUPPORTED_INTEGRATIONS)
    selected = []
    for target in targets:
        normalized = target.strip().lower()
        if normalized not in SUPPORTED_INTEGRATIONS:
            supported = ", ".join(SUPPORTED_INTEGRATIONS)
            raise ValueError(f"Unsupported integration target: {target}. Supported targets: {supported}.")
        if normalized not in selected:
            selected.append(normalized)
    return selected


def _project_context(project_dir: Path) -> dict[str, Any]:
    latest = latest_run_dir(project_dir)
    manifest = read_json(latest / "manifest.json", default={}) if latest else {}
    metadata = read_json(latest / "metadata.json", default={}) if latest else {}
    metrics = _latest_metrics(latest) if latest else {}
    experiment_id = metadata.get("experiment_id") if isinstance(metadata, dict) else None
    template = metadata.get("template") if isinstance(metadata, dict) else None
    return {
        "project_name": project_dir.name,
        "latest_run_dir": str(latest) if latest else None,
        "latest_command": manifest.get("command") if isinstance(manifest, dict) else None,
        "latest_run_status": metadata.get("status") if isinstance(metadata, dict) else None,
        "experiment_id": experiment_id,
        "template": template,
        "metrics_path": str(latest / "data" / "metrics.json") if latest and (latest / "data" / "metrics.json").exists() else None,
        "metric_keys": sorted(metrics),
        "artifact_root": str(latest) if latest else str(project_dir / "outputs"),
    }


def _latest_metrics(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return {}
    for relative in ["data/metrics.json", "data/demo_metrics.json", "data/sweep_results.json"]:
        metrics = read_json(run_dir / relative, default={}) or {}
        if isinstance(metrics, dict) and metrics:
            return metrics
    return {}


def _write_target(project_dir: Path, output_dir: Path, target: str, context: dict[str, Any]) -> dict[str, Any]:
    if target == "mlflow":
        path = output_dir / "mlflow_run_context.json"
        write_json(path, _mlflow_payload(project_dir, context))
    elif target == "aim":
        path = output_dir / "aim_run_context.json"
        write_json(path, _aim_payload(project_dir, context))
    elif target == "dvc":
        path = output_dir / "dvc_stage.yaml"
        write_yaml(path, _dvc_payload(project_dir, context))
    elif target == "hydra":
        path = output_dir / "hydra_config.yaml"
        write_yaml(path, _hydra_payload(project_dir, context))
    else:  # pragma: no cover - guarded by _normalize_targets
        raise ValueError(f"Unsupported integration target: {target}")
    return {
        "target": target,
        "path": str(path),
        "status": "written",
        "note": "Declaration only; external tool execution is intentionally out of scope.",
    }


def _mlflow_payload(project_dir: Path, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "integration": "mlflow",
        "experiment_name": project_dir.name,
        "run_name": context.get("experiment_id") or context.get("latest_command") or "openrepro_run",
        "artifact_location": context.get("artifact_root"),
        "metrics_path": context.get("metrics_path"),
        "tags": {
            "openrepro.project": project_dir.name,
            "openrepro.version": __version__,
            "openrepro.template": context.get("template"),
            "openrepro.latest_command": context.get("latest_command"),
        },
        "policy": "Import this into MLflow only under supervised user control.",
    }


def _aim_payload(project_dir: Path, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "integration": "aim",
        "repo": str(project_dir / ".aim"),
        "run_context": {
            "project": project_dir.name,
            "experiment": context.get("experiment_id") or "openrepro",
            "template": context.get("template"),
            "latest_run_dir": context.get("latest_run_dir"),
            "metric_keys": context.get("metric_keys", []),
        },
        "policy": "This file is an Aim handoff context; it does not create an Aim repo.",
    }


def _dvc_payload(project_dir: Path, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "stages": {
            "openrepro_refresh": {
                "cmd": f"openrepro refresh {project_dir.name} --zip",
                "deps": ["project_config.yaml", "sources"],
                "outs": ["workspace", "reports", "handoff"],
                "desc": "Template stage for supervised DVC adoption; review paths before use.",
            }
        },
        "meta": {
            "integration": "dvc",
            "latest_run_dir": context.get("latest_run_dir"),
            "policy": "Declaration only; copy or adapt into a project-root dvc.yaml before running DVC.",
        },
    }


def _hydra_payload(project_dir: Path, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "openrepro": {
            "project_dir": str(project_dir),
            "project_name": project_dir.name,
            "latest_run_dir": context.get("latest_run_dir"),
        },
        "experiment": {
            "id": context.get("experiment_id") or "openrepro_experiment",
            "template": context.get("template") or "basic",
            "metrics_path": context.get("metrics_path"),
        },
        "policy": "Hydra config export is a starter config only; it does not execute experiments.",
    }


def _render_markdown(result: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {artifact['target']} | {artifact['status']} | `{artifact['path']}` |"
        for artifact in result["artifacts"]
    )
    return f"""# Integration Exports

- status: {result['status']}
- target_count: {result['target_count']}
- latest_run_dir: `{result['context'].get('latest_run_dir')}`
- latest_command: {result['context'].get('latest_command')}

| Target | Status | Path |
| --- | --- | --- |
{rows}

## Guardrails

- Integration export writes adapter files only.
- No external integration package is imported or executed.
- Generated files are starting points for supervised MLflow, Aim, DVC, or Hydra setup.

## Policy

Integration exports describe interoperability surfaces only; they do not run experiments or verify scientific outputs.
"""
