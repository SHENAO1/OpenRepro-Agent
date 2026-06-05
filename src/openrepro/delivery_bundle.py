"""Final delivery bundle generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .readiness_review_validation import readiness_review_validation_summary
from .review_action_plan import review_action_plan_summary
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

DELIVERY_BUNDLE_SCHEMA_VERSION = "1.22.1"


def generate_delivery_bundle(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write reports/delivery_bundle.json and Markdown, optionally zipped."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    bundle = build_delivery_bundle(project_dir)
    json_path = project_dir / "reports" / "delivery_bundle.json"
    markdown_path = project_dir / "reports" / "DELIVERY_BUNDLE.md"
    zip_path = project_dir / "reports" / "delivery_bundle.zip"
    bundle["path"] = str(json_path)
    bundle["markdown_path"] = str(markdown_path)
    bundle["zip_path"] = str(zip_path) if export_zip else str(zip_path) if zip_path.exists() else None
    write_json(json_path, bundle)
    safe_write_text(markdown_path, _render_markdown(bundle))
    if export_zip:
        bundle["zip_path"] = str(_export_zip(project_dir, bundle))
        write_json(json_path, bundle)
        safe_write_text(markdown_path, _render_markdown(bundle))
    return bundle


def build_delivery_bundle(project_dir: Path) -> dict[str, Any]:
    """Build final delivery bundle payload without writing files."""
    project_dir = Path(project_dir)
    files = [_file(project_dir, item) for item in _file_specs(project_dir)]
    required = [item for item in files if item["required"]]
    missing = [item for item in required if not item["present"]]
    validation = readiness_review_validation_summary(project_dir)
    action_plan = review_action_plan_summary(project_dir)
    status, top_command = _bundle_status(project_dir, missing, validation, action_plan)
    return {
        "schema_version": DELIVERY_BUNDLE_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": top_command,
        "required_file_count": len(required),
        "present_file_count": sum(1 for item in required if item["present"]),
        "missing_file_count": len(missing),
        "file_count": len(files),
        "zip_exportable_file_count": sum(1 for item in files if item["present"]),
        "files": files,
        "source": {
            "readiness_review_validation_status": validation["status"],
            "readiness_review_validation_issue_count": validation["issue_count"],
            "review_action_plan_status": action_plan["status"],
            "review_action_plan_open_action_count": action_plan["open_action_count"],
        },
        "guardrails": [
            "Does not run experiments.",
            "Does not create, edit, or close human review decisions.",
            "Does not fabricate missing scientific artifacts.",
        ],
        "policy": "Delivery bundles organize final workflow handoff files only; they do not claim scientific reproduction success.",
    }


def delivery_bundle_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing delivery bundle summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "reports" / "delivery_bundle.json"
    markdown_path = project_dir / "reports" / "DELIVERY_BUNDLE.md"
    zip_path = project_dir / "reports" / "delivery_bundle.zip"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "required_file_count": int(data.get("required_file_count", 0) or 0),
        "present_file_count": int(data.get("present_file_count", 0) or 0),
        "missing_file_count": int(data.get("missing_file_count", 0) or 0),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def _bundle_status(
    project_dir: Path,
    missing: list[dict[str, Any]],
    validation: dict[str, Any],
    action_plan: dict[str, Any],
) -> tuple[str, str | None]:
    if missing:
        return "needs_work", str(missing[0]["command"])
    if validation["status"] != "passed":
        command = validation.get("top_command") or f"openrepro validate-readiness-review {project_dir}"
        return "needs_work", str(command)
    if not action_plan["present"]:
        return "needs_work", f"openrepro review-action-plan {project_dir}"
    if action_plan["status"] not in {"complete", "ready"}:
        command = action_plan.get("top_command") or f"openrepro review-action-plan {project_dir}"
        return "needs_work", str(command)
    return "ready", None


def _file_specs(project_dir: Path) -> list[dict[str, Any]]:
    p = str(project_dir)
    return [
        _spec("report", "Project report", "reports/report.md", f"openrepro report {p}"),
        _spec("handoff_context", "Project context", "handoff/PROJECT_CONTEXT.md", f"openrepro handoff {p}"),
        _spec("handoff_code", "Code status", "handoff/CODE_STATUS.md", f"openrepro handoff {p}"),
        _spec("handoff_next_steps", "Next steps", "handoff/NEXT_STEPS.md", f"openrepro handoff {p}"),
        _spec("handoff_agent", "Agent handoff", "handoff/AGENT_HANDOFF.md", f"openrepro handoff {p}"),
        _spec("evidence_json", "Evidence package JSON", "reports/evidence_package.json", f"openrepro evidence-package {p} --zip"),
        _spec("evidence_md", "Evidence package Markdown", "reports/evidence_package.md", f"openrepro evidence-package {p} --zip"),
        _spec("evidence_zip", "Evidence package zip", "reports/evidence_package.zip", f"openrepro evidence-package {p} --zip"),
        _spec("reviewer_json", "Reviewer packet JSON", "reports/reviewer_packet.json", f"openrepro reviewer-packet {p} --zip"),
        _spec("reviewer_md", "Reviewer packet Markdown", "reports/reviewer_packet.md", f"openrepro reviewer-packet {p} --zip"),
        _spec("reviewer_zip", "Reviewer packet zip", "reports/reviewer_packet.zip", f"openrepro reviewer-packet {p} --zip"),
        _spec("review_site_index", "Review site index", "reports/review_site/index.html", f"openrepro review-site {p} --zip"),
        _spec("review_site_manifest", "Review site manifest", "reports/review_site_manifest.json", f"openrepro review-site {p} --zip"),
        _spec("review_site_zip", "Review site zip", "reports/review_site.zip", f"openrepro review-site {p} --zip"),
        _spec("dashboard_index", "Dashboard index", "reports/dashboard/index.html", f"openrepro dashboard {p} --zip"),
        _spec("dashboard_manifest", "Dashboard manifest", "reports/dashboard_manifest.json", f"openrepro dashboard {p} --zip"),
        _spec("dashboard_zip", "Dashboard zip", "reports/dashboard.zip", f"openrepro dashboard {p} --zip"),
        _spec("collaboration_json", "Collaboration pack JSON", "handoff/collaboration_pack.json", f"openrepro collaboration-pack {p} --zip"),
        _spec("collaboration_md", "Collaboration pack Markdown", "handoff/COLLABORATION_PACK.md", f"openrepro collaboration-pack {p} --zip"),
        _spec("collaboration_zip", "Collaboration pack zip", "handoff/collaboration_pack.zip", f"openrepro collaboration-pack {p} --zip"),
        _spec("refresh_json", "Refresh run JSON", "workspace/refresh_run.json", f"openrepro refresh {p} --zip"),
        _spec("refresh_md", "Refresh run Markdown", "workspace/REFRESH_RUN.md", f"openrepro refresh {p} --zip"),
        _spec("freshness_json", "Artifact freshness JSON", "workspace/artifact_freshness.json", f"openrepro freshness {p}"),
        _spec("freshness_md", "Artifact freshness Markdown", "workspace/ARTIFACT_FRESHNESS.md", f"openrepro freshness {p}"),
        _spec("readiness_json", "Readiness review JSON", "reports/readiness_review.json", f"openrepro readiness-review {p} --zip"),
        _spec("readiness_md", "Readiness review Markdown", "reports/READINESS_REVIEW.md", f"openrepro readiness-review {p} --zip"),
        _spec("readiness_zip", "Readiness review zip", "reports/readiness_review.zip", f"openrepro readiness-review {p} --zip"),
        _spec("readiness_validation_json", "Readiness validation JSON", "reports/readiness_review_validation.json", f"openrepro validate-readiness-review {p}"),
        _spec("readiness_validation_md", "Readiness validation Markdown", "reports/READINESS_REVIEW_VALIDATION.md", f"openrepro validate-readiness-review {p}"),
        _spec("review_action_json", "Review action plan JSON", "workspace/review_action_plan.json", f"openrepro review-action-plan {p}"),
        _spec("review_action_md", "Review action plan Markdown", "workspace/REVIEW_ACTION_PLAN.md", f"openrepro review-action-plan {p}"),
    ]


def _spec(file_id: str, label: str, path: str, command: str, required: bool = True) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "label": label,
        "path": path,
        "command": command,
        "required": required,
    }


def _file(project_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = project_dir / str(spec["path"])
    return {
        **spec,
        "present": path.exists() and path.is_file(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def _export_zip(project_dir: Path, bundle: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "delivery_bundle.zip"
    files = [
        project_dir / "reports" / "delivery_bundle.json",
        project_dir / "reports" / "DELIVERY_BUNDLE.md",
    ]
    files.extend(project_dir / str(item["path"]) for item in bundle.get("files", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _render_markdown(bundle: dict[str, Any]) -> str:
    rows = [
        "| File | Required | Present | Size | Path | Command |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in bundle["files"]:
        rows.append(
            "| {label} | {required} | {present} | {size} | `{path}` | `{command}` |".format(
                label=_cell(item["label"]),
                required=_cell(item["required"]),
                present=_cell(item["present"]),
                size=_cell(item["size_bytes"]),
                path=_cell(item["path"]),
                command=_cell(item["command"] if not item["present"] else ""),
            )
        )
    guardrails = "\n".join(f"- {item}" for item in bundle["guardrails"])
    return f"""# Delivery Bundle

- schema_version: {bundle['schema_version']}
- created_at: {bundle['created_at']}
- project_name: {bundle['project_name']}
- status: {bundle['status']}
- top_command: {bundle['top_command']}
- required_file_count: {bundle['required_file_count']}
- present_file_count: {bundle['present_file_count']}
- missing_file_count: {bundle['missing_file_count']}
- zip_path: {bundle.get('zip_path')}

## Source

- readiness_review_validation_status: {bundle['source']['readiness_review_validation_status']}
- readiness_review_validation_issue_count: {bundle['source']['readiness_review_validation_issue_count']}
- review_action_plan_status: {bundle['source']['review_action_plan_status']}
- review_action_plan_open_action_count: {bundle['source']['review_action_plan_open_action_count']}

## Files

{chr(10).join(rows)}

## Guardrails

{guardrails}

## Policy

{bundle['policy']}
"""


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/")
