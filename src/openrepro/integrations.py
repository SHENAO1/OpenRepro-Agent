"""Declarative integration exports for external reproducibility tools."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .artifact_manager import latest_run_dir
from .utils import iso_now, read_json, safe_write_text, write_json, write_yaml

INTEGRATION_SCHEMA_VERSION = "1.52.0"
INTEGRATION_EXECUTION_SCHEMA_VERSION = "1.54.0"
SUPPORTED_INTEGRATIONS = ("mlflow", "aim", "dvc", "hydra")
INTEGRATION_DEPENDENCIES = {
    "mlflow": {"kind": "python_module", "name": "mlflow", "package": "mlflow"},
    "aim": {"kind": "python_module", "name": "aim", "package": "aim"},
    "dvc": {"kind": "executable", "name": "dvc", "package": "dvc"},
    "hydra": {"kind": "python_module", "name": "hydra", "package": "hydra-core"},
}


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
    execution_path = project_dir / "workspace" / "integration_execution.json"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    execution = read_json(execution_path, default={}) or {}
    execution = execution if isinstance(execution, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(project_dir / "workspace" / "INTEGRATIONS.md") if path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "target_count": int(data.get("target_count", 0) or 0),
        "targets": list(data.get("targets", [])) if isinstance(data.get("targets"), list) else [],
        "execution_present": execution_path.exists(),
        "execution_status": execution.get("status", "missing"),
        "execution_path": str(execution_path) if execution_path.exists() else None,
    }


def run_integration_execution(
    project_dir: Path,
    targets: list[str] | None = None,
    *,
    confirm: bool = False,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Write and optionally execute supervised integration adapter plans."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    project_dir = project_dir.resolve()
    selected = _normalize_targets(targets)
    export = export_integrations(project_dir, targets=selected)
    output_dir = project_dir / "integrations"
    log_dir = output_dir / "execution_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    executions = []
    for target in selected:
        plan = _execution_plan(project_dir, output_dir, target, export["context"])
        if confirm:
            plan = _execute_plan(project_dir, log_dir, plan, timeout_seconds=timeout_seconds)
        else:
            plan["status"] = "planned"
            plan["note"] = "Dry-run plan only. Re-run with --confirm to execute when the dependency is available."
        write_json(output_dir / f"{target}_execution_plan.json", plan)
        executions.append(plan)

    if not confirm:
        status = "planned"
    elif any(item.get("status") == "failed" for item in executions):
        status = "needs_review"
    elif all(item.get("status") == "skipped_missing_dependency" for item in executions):
        status = "skipped_missing_dependency"
    else:
        status = "executed"

    result = {
        "schema_version": INTEGRATION_EXECUTION_SCHEMA_VERSION,
        "created_at": iso_now(),
        "openrepro_version": __version__,
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "confirm": confirm,
        "timeout_seconds": timeout_seconds,
        "target_count": len(selected),
        "targets": selected,
        "executions": executions,
        "guardrails": [
            "External tools are never invoked unless --confirm is provided.",
            "Missing optional integration dependencies are recorded as skipped, not success.",
            "Adapter scripts are supervised helper scripts and do not prove scientific reproduction.",
        ],
        "policy": "Integration execution reports tool adapter status only; they do not verify scientific outputs.",
    }
    write_json(project_dir / "workspace" / "integration_execution.json", result)
    safe_write_text(project_dir / "workspace" / "INTEGRATION_EXECUTION.md", _render_execution_markdown(result))
    return result


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


def _dependency_status(target: str) -> dict[str, Any]:
    dependency = INTEGRATION_DEPENDENCIES[target]
    name = str(dependency["name"])
    if dependency["kind"] == "python_module":
        available = importlib.util.find_spec(name) is not None
        version = None
        if available:
            try:
                version = importlib.metadata.version(str(dependency["package"]))
            except importlib.metadata.PackageNotFoundError:
                version = None
        return {
            "kind": "python_module",
            "name": name,
            "package": dependency["package"],
            "available": available,
            "version": version,
        }
    executable = shutil.which(name)
    version = None
    if executable:
        try:
            completed = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=15)
            version = (completed.stdout or completed.stderr).strip().splitlines()[0] if (completed.stdout or completed.stderr) else None
        except (OSError, subprocess.SubprocessError):
            version = None
    return {
        "kind": "executable",
        "name": name,
        "package": dependency["package"],
        "available": executable is not None,
        "path": executable,
        "version": version,
    }


def _execution_plan(project_dir: Path, output_dir: Path, target: str, context: dict[str, Any]) -> dict[str, Any]:
    dependency = _dependency_status(target)
    if target == "mlflow":
        script_path = output_dir / "run_mlflow_adapter.py"
        safe_write_text(script_path, _mlflow_script())
        command = [sys.executable, str(script_path)]
        artifact_path = output_dir / "mlflow_run_context.json"
        mode = "adapter_script"
    elif target == "aim":
        script_path = output_dir / "run_aim_adapter.py"
        safe_write_text(script_path, _aim_script())
        command = [sys.executable, str(script_path)]
        artifact_path = output_dir / "aim_run_context.json"
        mode = "adapter_script"
    elif target == "hydra":
        script_path = output_dir / "run_hydra_adapter.py"
        safe_write_text(script_path, _hydra_script())
        command = [sys.executable, str(script_path)]
        artifact_path = output_dir / "hydra_config.yaml"
        mode = "adapter_script"
    elif target == "dvc":
        script_path = None
        command = ["dvc", "--version"]
        artifact_path = output_dir / "dvc_stage.yaml"
        mode = "dependency_preflight"
    else:  # pragma: no cover - guarded by _normalize_targets
        raise ValueError(f"Unsupported integration target: {target}")
    return {
        "schema_version": INTEGRATION_EXECUTION_SCHEMA_VERSION,
        "target": target,
        "status": "ready_to_execute" if dependency["available"] else "missing_dependency",
        "mode": mode,
        "dependency": dependency,
        "command": command,
        "script_path": str(script_path) if script_path else None,
        "artifact_path": str(artifact_path),
        "latest_run_dir": context.get("latest_run_dir"),
        "created_at": iso_now(),
    }


def _execute_plan(project_dir: Path, log_dir: Path, plan: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    if not plan["dependency"]["available"]:
        plan["status"] = "skipped_missing_dependency"
        plan["note"] = f"Optional dependency is not available: {plan['dependency']['name']}"
        return plan
    target = str(plan["target"])
    stdout_path = log_dir / f"{target}.stdout.log"
    stderr_path = log_dir / f"{target}.stderr.log"
    try:
        completed = subprocess.run(
            [str(item) for item in plan["command"]],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        safe_write_text(stdout_path, exc.stdout or "")
        safe_write_text(stderr_path, exc.stderr or f"Timed out after {timeout_seconds} seconds.")
        plan.update(
            {
                "status": "failed",
                "returncode": None,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "note": f"Execution timed out after {timeout_seconds} seconds.",
            }
        )
        return plan
    safe_write_text(stdout_path, completed.stdout or "")
    safe_write_text(stderr_path, completed.stderr or "")
    plan.update(
        {
            "status": "executed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "note": "Adapter command completed." if completed.returncode == 0 else "Adapter command returned a non-zero exit code.",
        }
    )
    return plan


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


def _mlflow_script() -> str:
    return '''"""Supervised MLflow adapter generated by OpenRepro-Agent."""

from __future__ import annotations

import json
from pathlib import Path


def _numeric_metrics(path: Path | None) -> dict[str, float]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {str(key): float(value) for key, value in data.items() if isinstance(value, (int, float))}


def main() -> None:
    import mlflow

    project_dir = Path(__file__).resolve().parents[1]
    context = json.loads((project_dir / "integrations" / "mlflow_run_context.json").read_text(encoding="utf-8"))
    tracking_uri = (project_dir / "mlruns").as_uri()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(context["experiment_name"])
    metrics_path = Path(context["metrics_path"]) if context.get("metrics_path") else None
    artifact_root = Path(context["artifact_location"]) if context.get("artifact_location") else None
    with mlflow.start_run(run_name=context["run_name"]):
        mlflow.set_tags({key: value for key, value in context["tags"].items() if value is not None})
        for key, value in _numeric_metrics(metrics_path).items():
            mlflow.log_metric(key, value)
        if artifact_root and artifact_root.exists():
            mlflow.log_artifacts(str(artifact_root), artifact_path="openrepro_latest_run")
    print(json.dumps({"status": "logged", "tracking_uri": tracking_uri}))


if __name__ == "__main__":
    main()
'''


def _aim_script() -> str:
    return '''"""Supervised Aim adapter generated by OpenRepro-Agent."""

from __future__ import annotations

import json
from pathlib import Path


def _numeric_metrics(path: Path | None) -> dict[str, float]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {str(key): float(value) for key, value in data.items() if isinstance(value, (int, float))}


def main() -> None:
    from aim import Run

    project_dir = Path(__file__).resolve().parents[1]
    context = json.loads((project_dir / "integrations" / "aim_run_context.json").read_text(encoding="utf-8"))
    run_context = context["run_context"]
    run = Run(repo=context["repo"], experiment=run_context["experiment"])
    run["openrepro.project"] = run_context["project"]
    run["openrepro.template"] = run_context.get("template")
    metrics_path = Path(run_context.get("latest_run_dir", "")) / "data" / "metrics.json" if run_context.get("latest_run_dir") else None
    for key, value in _numeric_metrics(metrics_path).items():
        run.track(value, name=key)
    run.close()
    print(json.dumps({"status": "logged", "repo": context["repo"]}))


if __name__ == "__main__":
    main()
'''


def _hydra_script() -> str:
    return '''"""Supervised Hydra config preflight generated by OpenRepro-Agent."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def main() -> None:
    import hydra

    project_dir = Path(__file__).resolve().parents[1]
    config_path = project_dir / "integrations" / "hydra_config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    print(json.dumps({
        "status": "loaded",
        "hydra_version": getattr(hydra, "__version__", None),
        "project": (config.get("openrepro") or {}).get("project_name"),
        "experiment": (config.get("experiment") or {}).get("id"),
    }))


if __name__ == "__main__":
    main()
'''


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


def _render_execution_markdown(result: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {target} | {status} | {dependency} | `{command}` | `{stdout}` |".format(
            target=item.get("target"),
            status=item.get("status"),
            dependency=(item.get("dependency") or {}).get("name"),
            command=" ".join(str(part) for part in item.get("command", [])),
            stdout=item.get("stdout_path") or "",
        )
        for item in result["executions"]
    )
    return f"""# Integration Execution

- schema_version: {result['schema_version']}
- status: {result['status']}
- confirm: {result['confirm']}
- target_count: {result['target_count']}

| Target | Status | Dependency | Command | Stdout |
| --- | --- | --- | --- | --- |
{rows}

## Guardrails

- External tools are never invoked unless `--confirm` is provided.
- Missing optional integration dependencies are recorded as skipped, not success.
- Adapter scripts are supervised helper scripts and do not prove scientific reproduction.

## Policy

Integration execution reports tool adapter status only; it does not verify scientific outputs.
"""
