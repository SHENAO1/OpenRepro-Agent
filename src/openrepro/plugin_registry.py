"""Declarative plugin registry for project extensions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, read_json, read_yaml, safe_write_text, slugify, write_json, write_yaml

PLUGIN_REGISTRY_SCHEMA_VERSION = "1.47.0"
PLUGIN_KINDS = {"command", "provider", "reporter", "evaluator"}
PLUGIN_RUN_MODES = {"declaration", "external_supervised", "safe_command"}
FORBIDDEN_COMMANDS = {"run-experiment", "rerun-experiment", "repair", "claim-signoff", "review-decision", "agent"}


def register_plugin(
    project_dir: Path,
    *,
    plugin_id: str,
    kind: str,
    entrypoint: str,
    description: str = "",
    capabilities: list[str] | None = None,
    run_mode: str = "declaration",
    enabled: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Add or update a declarative plugin entry."""
    project_dir = Path(project_dir)
    plugin_id = _normalize_id(plugin_id)
    kind = _normalize(kind, PLUGIN_KINDS, "kind")
    run_mode = _normalize(run_mode, PLUGIN_RUN_MODES, "run mode")
    entrypoint = (entrypoint or "").strip()
    if not entrypoint:
        raise ValueError("Plugin entrypoint cannot be empty.")

    config = _config(project_dir)
    entries = _entries(config)
    existing = {entry["plugin_id"]: entry for entry in entries}
    if plugin_id in existing and not overwrite:
        raise ValueError(f"Plugin already exists: {plugin_id}. Pass --overwrite to update it.")
    created_at = existing.get(plugin_id, {}).get("created_at") or iso_now()
    existing[plugin_id] = {
        "plugin_id": plugin_id,
        "kind": kind,
        "entrypoint": entrypoint,
        "description": description,
        "capabilities": sorted({capability.strip() for capability in capabilities or [] if capability.strip()}),
        "run_mode": run_mode,
        "enabled": enabled,
        "created_at": created_at,
        "updated_at": iso_now(),
    }
    config = {"schema_version": PLUGIN_REGISTRY_SCHEMA_VERSION, "plugins": sorted(existing.values(), key=lambda item: item["plugin_id"])}
    write_yaml(_config_path(project_dir), config)
    registry = build_plugin_registry(project_dir)
    validate_plugin_registry(project_dir)
    return registry


def build_plugin_registry(project_dir: Path) -> dict[str, Any]:
    """Build plugin registry artifacts from openrepro.plugins.yaml."""
    project_dir = Path(project_dir)
    config_path = _config_path(project_dir)
    entries = _entries(_config(project_dir))
    kind_counts = _count_by(entries, "kind")
    mode_counts = _count_by(entries, "run_mode")
    registry = {
        "schema_version": PLUGIN_REGISTRY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "ready" if entries else "empty",
        "config_path": str(config_path),
        "plugin_count": len(entries),
        "enabled_plugin_count": sum(1 for entry in entries if entry.get("enabled", True)),
        "kind_counts": kind_counts,
        "run_mode_counts": mode_counts,
        "plugins": entries,
        "guardrails": [
            "Registry generation does not import, load, or execute plugin code.",
            "Command plugins are declarations unless explicitly supervised by another workflow.",
            "Validation blocks unsafe command names for safe_command plugins.",
        ],
        "policy": "Plugin registries describe project extension points only; they do not execute extensions or verify scientific outputs.",
    }
    write_json(project_dir / "workspace" / "plugin_registry.json", registry)
    safe_write_text(project_dir / "workspace" / "PLUGIN_REGISTRY.md", _render_registry_markdown(registry))
    return registry


def validate_plugin_registry(project_dir: Path) -> dict[str, Any]:
    """Validate plugin declarations without executing them."""
    project_dir = Path(project_dir)
    entries = _entries(_config(project_dir))
    errors = []
    warnings = []
    seen: set[str] = set()
    for entry in entries:
        plugin_id = str(entry.get("plugin_id") or "")
        if plugin_id in seen:
            errors.append(_issue(plugin_id, "duplicate_plugin_id", "Plugin id appears more than once."))
        seen.add(plugin_id)
        if plugin_id != slugify(plugin_id):
            errors.append(_issue(plugin_id, "invalid_plugin_id", "Plugin id must be slug-safe lowercase text."))
        if entry.get("kind") not in PLUGIN_KINDS:
            errors.append(_issue(plugin_id, "invalid_kind", f"Kind must be one of: {', '.join(sorted(PLUGIN_KINDS))}."))
        if entry.get("run_mode") not in PLUGIN_RUN_MODES:
            errors.append(_issue(plugin_id, "invalid_run_mode", f"Run mode must be one of: {', '.join(sorted(PLUGIN_RUN_MODES))}."))
        if not str(entry.get("entrypoint") or "").strip():
            errors.append(_issue(plugin_id, "missing_entrypoint", "Entrypoint cannot be empty."))
        if entry.get("run_mode") == "safe_command":
            command_name = _command_name(str(entry.get("entrypoint") or ""))
            if command_name in FORBIDDEN_COMMANDS:
                errors.append(_issue(plugin_id, "unsafe_command", f"Command is not allowed for safe_command plugins: {command_name}."))
            if entry.get("kind") != "command":
                warnings.append(_issue(plugin_id, "safe_non_command", "safe_command run mode is intended for command plugins."))
        if entry.get("kind") == "provider" and entry.get("run_mode") == "safe_command":
            errors.append(_issue(plugin_id, "provider_execution", "Provider plugins must be declarations or externally supervised."))
    valid = not errors
    result = {
        "schema_version": PLUGIN_REGISTRY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "valid": valid,
        "status": "passed" if valid else "failed",
        "plugin_count": len(entries),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "policy": "Plugin validation checks declarations and command safety only; it does not execute plugins.",
    }
    write_json(project_dir / "workspace" / "plugin_validation.json", result)
    safe_write_text(project_dir / "workspace" / "PLUGIN_VALIDATION.md", _render_validation_markdown(result))
    return result


def plugin_registry_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing plugin registry summary without mutating files."""
    project_dir = Path(project_dir)
    config_path = _config_path(project_dir)
    registry_path = project_dir / "workspace" / "plugin_registry.json"
    validation_path = project_dir / "workspace" / "plugin_validation.json"
    registry = read_json(registry_path, default={}) or {}
    registry = registry if isinstance(registry, dict) else {}
    validation = read_json(validation_path, default={}) or {}
    validation = validation if isinstance(validation, dict) else {}
    return {
        "present": registry_path.exists(),
        "path": str(registry_path) if registry_path.exists() else None,
        "markdown_path": str(project_dir / "workspace" / "PLUGIN_REGISTRY.md") if registry_path.exists() else None,
        "config_path": str(config_path) if config_path.exists() else None,
        "validation_path": str(validation_path) if validation_path.exists() else None,
        "validation_markdown_path": str(project_dir / "workspace" / "PLUGIN_VALIDATION.md") if validation_path.exists() else None,
        "schema_version": registry.get("schema_version"),
        "status": registry.get("status", "present" if registry_path.exists() else "missing"),
        "plugin_count": int(registry.get("plugin_count", 0) or 0),
        "enabled_plugin_count": int(registry.get("enabled_plugin_count", 0) or 0),
        "validation_status": validation.get("status"),
        "validation_error_count": int(validation.get("error_count", 0) or 0),
        "sha256": sha256_file(registry_path) if registry_path.exists() else None,
    }


def _config_path(project_dir: Path) -> Path:
    return Path(project_dir) / "openrepro.plugins.yaml"


def _config(project_dir: Path) -> dict[str, Any]:
    data = read_yaml(_config_path(project_dir), default={}) or {}
    return data if isinstance(data, dict) else {}


def _entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    plugins = config.get("plugins", []) if isinstance(config, dict) else []
    entries = [entry for entry in plugins if isinstance(entry, dict)]
    normalized = []
    for entry in entries:
        normalized.append(
            {
                "plugin_id": str(entry.get("plugin_id") or ""),
                "kind": str(entry.get("kind") or ""),
                "entrypoint": str(entry.get("entrypoint") or ""),
                "description": str(entry.get("description") or ""),
                "capabilities": [str(item) for item in entry.get("capabilities", []) if str(item).strip()]
                if isinstance(entry.get("capabilities"), list)
                else [],
                "run_mode": str(entry.get("run_mode") or "declaration"),
                "enabled": bool(entry.get("enabled", True)),
                "created_at": entry.get("created_at"),
                "updated_at": entry.get("updated_at"),
            }
        )
    return sorted(normalized, key=lambda item: item["plugin_id"])


def _normalize_id(plugin_id: str) -> str:
    if not (plugin_id or "").strip():
        raise ValueError("Plugin id cannot be empty.")
    value = slugify(plugin_id)
    return value


def _normalize(value: str, allowed: set[str], label: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in allowed:
        raise ValueError(f"Plugin {label} must be one of: {', '.join(sorted(allowed))}")
    return normalized


def _command_name(entrypoint: str) -> str:
    parts = entrypoint.strip().split()
    if not parts:
        return ""
    if parts[0] == "openrepro" and len(parts) > 1:
        return parts[1]
    return parts[0]


def _count_by(entries: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(entry.get(key) or "none")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _issue(plugin_id: str, code: str, message: str) -> dict[str, str]:
    return {"plugin_id": plugin_id, "code": code, "message": message}


def _render_registry_markdown(registry: dict[str, Any]) -> str:
    lines = [
        "# Plugin Registry",
        "",
        f"- schema_version: {registry['schema_version']}",
        f"- status: {registry['status']}",
        f"- plugin_count: {registry['plugin_count']}",
        f"- enabled_plugin_count: {registry['enabled_plugin_count']}",
        f"- config_path: `{registry['config_path']}`",
        "",
        "| Plugin | Kind | Enabled | Run mode | Entrypoint | Capabilities |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for plugin in registry["plugins"]:
        lines.append(
            "| {plugin_id} | {kind} | {enabled} | {run_mode} | `{entrypoint}` | {capabilities} |".format(
                plugin_id=_cell(plugin.get("plugin_id")),
                kind=_cell(plugin.get("kind")),
                enabled=_cell(plugin.get("enabled")),
                run_mode=_cell(plugin.get("run_mode")),
                entrypoint=_cell(plugin.get("entrypoint")),
                capabilities=_cell(", ".join(plugin.get("capabilities", []))),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in registry["guardrails"])
    lines.extend(["", "## Policy", "", registry["policy"], ""])
    return "\n".join(lines)


def _render_validation_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Plugin Validation",
        "",
        f"- status: {result['status']}",
        f"- valid: {result['valid']}",
        f"- plugin_count: {result['plugin_count']}",
        f"- error_count: {result['error_count']}",
        f"- warning_count: {result['warning_count']}",
        "",
        "| Level | Plugin | Code | Message |",
        "| --- | --- | --- | --- |",
    ]
    for issue in result["errors"]:
        lines.append(f"| error | {_cell(issue.get('plugin_id'))} | {_cell(issue.get('code'))} | {_cell(issue.get('message'))} |")
    for issue in result["warnings"]:
        lines.append(f"| warning | {_cell(issue.get('plugin_id'))} | {_cell(issue.get('code'))} | {_cell(issue.get('message'))} |")
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
