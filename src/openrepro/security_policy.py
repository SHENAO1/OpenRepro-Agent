"""Local security policy and audit helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .artifact_manager import sha256_file
from .utils import iso_now, read_json, read_text, safe_write_text, write_json

SECURITY_POLICY_SCHEMA_VERSION = "1.50.0"

DEFAULT_SECRET_PATTERNS = [
    {"name": "openai_style_key", "pattern": r"\bsk-[A-Za-z0-9_-]{16,}\b", "severity": "high"},
    {"name": "github_pat", "pattern": r"\bghp_[A-Za-z0-9_]{16,}\b", "severity": "high"},
    {"name": "aws_access_key", "pattern": r"\bAKIA[0-9A-Z]{16}\b", "severity": "high"},
    {"name": "private_key_block", "pattern": r"BEGIN (RSA |DSA |EC |OPENSSH |)?PRIVATE KEY", "severity": "critical"},
    {"name": "env_secret_assignment", "pattern": r"\b[A-Z0-9_]*(KEY|TOKEN|SECRET)\s*=\s*[^\s]+", "severity": "medium"},
]
DEFAULT_SCAN_ROOTS = ["sources", "workspace", "experiments", "reports", "handoff", ".github", "openrepro.plugins.yaml", "project_config.yaml"]
DEFAULT_EXCLUDE_DIRS = [".openrepro", "outputs", "__pycache__"]
SECURITY_OUTPUTS = {
    "workspace/security_policy.json",
    "workspace/SECURITY_POLICY.md",
    "workspace/security_audit.json",
    "workspace/SECURITY_AUDIT.md",
}


def init_security_policy(project_dir: Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Write the default project security policy."""
    project_dir = Path(project_dir)
    policy = _default_policy(project_dir)
    write_json(project_dir / "workspace" / "security_policy.json", policy, overwrite=overwrite)
    safe_write_text(project_dir / "workspace" / "SECURITY_POLICY.md", _render_policy_markdown(policy), overwrite=overwrite)
    return policy


def run_security_audit(project_dir: Path, *, strict: bool = False) -> dict[str, Any]:
    """Run a local security audit without printing secret values."""
    project_dir = Path(project_dir)
    policy = _policy(project_dir)
    findings = [
        *_secret_findings(project_dir, policy),
        *_validation_findings(project_dir),
        *_workflow_findings(project_dir),
        *_path_reference_findings(project_dir),
    ]
    severity_counts = _severity_counts(findings)
    high_count = severity_counts.get("high", 0) + severity_counts.get("critical", 0)
    medium_count = severity_counts.get("medium", 0)
    failed = high_count > 0 or (strict and medium_count > 0)
    result = {
        "schema_version": SECURITY_POLICY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "strict": strict,
        "status": "failed" if failed else "passed",
        "valid": not failed,
        "finding_count": len(findings),
        "critical_count": severity_counts.get("critical", 0),
        "high_count": severity_counts.get("high", 0),
        "medium_count": severity_counts.get("medium", 0),
        "low_count": severity_counts.get("low", 0),
        "severity_counts": severity_counts,
        "findings": findings,
        "policy_path": str(project_dir / "workspace" / "security_policy.json"),
        "guardrails": [
            "Secret findings include pattern names and locations only, never matched secret values.",
            "Security audit is local and static; it does not scan remote repositories or cloud services.",
            "Audit status is an engineering safety signal, not a guarantee that the project is secure.",
        ],
        "policy": "Security audits detect local workflow risks and likely secrets without executing project code.",
    }
    write_json(project_dir / "workspace" / "security_audit.json", result)
    safe_write_text(project_dir / "workspace" / "SECURITY_AUDIT.md", _render_audit_markdown(result))
    return result


def security_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing security audit summary without mutating files."""
    project_dir = Path(project_dir)
    policy_path = project_dir / "workspace" / "security_policy.json"
    audit_path = project_dir / "workspace" / "security_audit.json"
    audit = read_json(audit_path, default={}) or {}
    audit = audit if isinstance(audit, dict) else {}
    return {
        "present": audit_path.exists(),
        "path": str(audit_path) if audit_path.exists() else None,
        "markdown_path": str(project_dir / "workspace" / "SECURITY_AUDIT.md") if audit_path.exists() else None,
        "policy_path": str(policy_path) if policy_path.exists() else None,
        "policy_markdown_path": str(project_dir / "workspace" / "SECURITY_POLICY.md") if policy_path.exists() else None,
        "schema_version": audit.get("schema_version"),
        "status": audit.get("status", "present" if audit_path.exists() else "missing"),
        "valid": audit.get("valid"),
        "finding_count": int(audit.get("finding_count", 0) or 0),
        "critical_count": int(audit.get("critical_count", 0) or 0),
        "high_count": int(audit.get("high_count", 0) or 0),
        "medium_count": int(audit.get("medium_count", 0) or 0),
        "sha256": sha256_file(audit_path) if audit_path.exists() else None,
    }


def _default_policy(project_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": SECURITY_POLICY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": Path(project_dir).name,
        "project_dir": str(Path(project_dir)),
        "scan_roots": DEFAULT_SCAN_ROOTS,
        "exclude_dirs": DEFAULT_EXCLUDE_DIRS,
        "max_file_bytes": 1_000_000,
        "secret_patterns": DEFAULT_SECRET_PATTERNS,
        "required_local_validations": ["plugin_validation", "ci_validation"],
        "policy": "Default policy scans project text artifacts for likely secrets and unsafe workflow declarations.",
    }


def _policy(project_dir: Path) -> dict[str, Any]:
    path = Path(project_dir) / "workspace" / "security_policy.json"
    data = read_json(path, default={}) or {}
    return data if isinstance(data, dict) and data.get("secret_patterns") else init_security_policy(project_dir)


def _secret_findings(project_dir: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    patterns = [
        {
            "name": str(item.get("name")),
            "regex": re.compile(str(item.get("pattern"))),
            "severity": str(item.get("severity") or "medium"),
        }
        for item in policy.get("secret_patterns", [])
        if isinstance(item, dict) and item.get("pattern")
    ]
    for path in _scan_files(project_dir, policy):
        text = read_text(path, default="")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if pattern["regex"].search(line):
                    findings.append(
                        _finding(
                            "secret_pattern",
                            pattern["severity"],
                            f"Potential secret matched pattern {pattern['name']}.",
                            path=path,
                            project_dir=project_dir,
                            line=line_number,
                            pattern=pattern["name"],
                        )
                    )
    return findings


def _validation_findings(project_dir: Path) -> list[dict[str, Any]]:
    findings = []
    plugin_validation = read_json(project_dir / "workspace" / "plugin_validation.json", default={}) or {}
    if isinstance(plugin_validation, dict) and plugin_validation and plugin_validation.get("status") != "passed":
        findings.append(_finding("plugin_validation_failed", "high", "Plugin validation is present but not passed.", path=project_dir / "workspace" / "plugin_validation.json", project_dir=project_dir))
    ci_validation = read_json(project_dir / "workspace" / "ci_validation.json", default={}) or {}
    if isinstance(ci_validation, dict) and ci_validation and ci_validation.get("status") != "passed":
        findings.append(_finding("ci_validation_failed", "medium", "Local CI validation is present but not passed.", path=project_dir / "workspace" / "ci_validation.json", project_dir=project_dir))
    return findings


def _workflow_findings(project_dir: Path) -> list[dict[str, Any]]:
    workflow = project_dir / ".github" / "workflows" / "openrepro-ci.yml"
    content = read_text(workflow, default="")
    if "pull_request_target" in content:
        return [_finding("pull_request_target", "high", "Workflow uses pull_request_target; review permissions and checkout safety.", path=workflow, project_dir=project_dir)]
    return []


def _path_reference_findings(project_dir: Path) -> list[dict[str, Any]]:
    findings = []
    plugins = read_json(project_dir / "workspace" / "plugin_registry.json", default={}) or {}
    entries = plugins.get("plugins", []) if isinstance(plugins, dict) else []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        entrypoint = str(entry.get("entrypoint") or "")
        if ".." in entrypoint or "~" in entrypoint:
            findings.append(
                _finding(
                    "unsafe_path_reference",
                    "medium",
                    f"Plugin entrypoint contains a relative parent or home reference: {entry.get('plugin_id')}.",
                    path=project_dir / "workspace" / "plugin_registry.json",
                    project_dir=project_dir,
                )
            )
    return findings


def _scan_files(project_dir: Path, policy: dict[str, Any]) -> list[Path]:
    max_bytes = int(policy.get("max_file_bytes", 1_000_000) or 1_000_000)
    roots = [project_dir / str(root) for root in policy.get("scan_roots", DEFAULT_SCAN_ROOTS)]
    exclude_dirs = set(str(item) for item in policy.get("exclude_dirs", DEFAULT_EXCLUDE_DIRS))
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = [path for path in root.rglob("*") if path.is_file()]
        else:
            continue
        for path in candidates:
            relative = _relative(path, project_dir)
            if relative in SECURITY_OUTPUTS:
                continue
            try:
                parts = path.relative_to(project_dir).parts
            except ValueError:
                parts = path.parts
            if any(part in exclude_dirs for part in parts):
                continue
            if path.stat().st_size > max_bytes:
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".npy", ".pdf"}:
                continue
            files.append(path)
    return sorted(set(files), key=lambda item: item.as_posix())


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity") or "medium")
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def _finding(
    code: str,
    severity: str,
    message: str,
    *,
    path: Path,
    project_dir: Path,
    line: int | None = None,
    pattern: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "path": _relative(path, project_dir),
        "line": line,
        "pattern": pattern,
    }


def _relative(path: Path, project_dir: Path) -> str:
    try:
        return path.relative_to(project_dir).as_posix()
    except ValueError:
        return str(path)


def _render_policy_markdown(policy: dict[str, Any]) -> str:
    lines = [
        "# Security Policy",
        "",
        f"- schema_version: {policy['schema_version']}",
        f"- scan_roots: {policy['scan_roots']}",
        f"- exclude_dirs: {policy['exclude_dirs']}",
        f"- max_file_bytes: {policy['max_file_bytes']}",
        "",
        "| Pattern | Severity |",
        "| --- | --- |",
    ]
    for item in policy["secret_patterns"]:
        lines.append(f"| {_cell(item.get('name'))} | {_cell(item.get('severity'))} |")
    lines.extend(["", "## Policy", "", policy["policy"], ""])
    return "\n".join(lines)


def _render_audit_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Security Audit",
        "",
        f"- schema_version: {result['schema_version']}",
        f"- status: {result['status']}",
        f"- valid: {result['valid']}",
        f"- strict: {result['strict']}",
        f"- finding_count: {result['finding_count']}",
        f"- critical_count: {result['critical_count']}",
        f"- high_count: {result['high_count']}",
        f"- medium_count: {result['medium_count']}",
        "",
        "| Severity | Code | Path | Line | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for finding in result["findings"]:
        lines.append(
            "| {severity} | {code} | `{path}` | {line} | {message} |".format(
                severity=_cell(finding.get("severity")),
                code=_cell(finding.get("code")),
                path=_cell(finding.get("path")),
                line=_cell(finding.get("line")),
                message=_cell(finding.get("message")),
            )
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in result["guardrails"])
    lines.extend(["", "## Policy", "", result["policy"], ""])
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "/")
