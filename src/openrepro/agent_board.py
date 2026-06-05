"""Static multi-agent task board generation."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .artifact_manager import sha256_file
from .multi_agent_plan import AGENT_ROSTER, generate_multi_agent_plan
from .multi_agent_plan_validation import validate_multi_agent_plan
from .utils import iso_now, read_json, relpath, safe_write_text, write_json

AGENT_BOARD_SCHEMA_VERSION = "1.24.0"


def generate_agent_board(project_dir: Path, export_zip: bool = False) -> dict[str, Any]:
    """Write reports/agent_board/index.html and reports/agent_board_manifest.json."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    plan = _plan(project_dir)
    validation = _validation(project_dir)
    lanes = _lanes(plan)
    status, top_command = _board_status(project_dir, plan, validation)
    board = {
        "schema_version": AGENT_BOARD_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": plan.get("project_name") or project_dir.name,
        "project_dir": str(project_dir),
        "status": status,
        "top_command": top_command,
        "agent_count": len(lanes),
        "task_count": int(plan.get("task_count", 0) or 0),
        "open_task_count": int(plan.get("open_task_count", 0) or 0),
        "human_input_task_count": sum(1 for task in plan.get("tasks", []) if isinstance(task, dict) and task.get("requires_human_input")),
        "validation_status": validation.get("status", "missing"),
        "validation_issue_count": int(validation.get("issue_count", 0) or 0),
        "validation_warning_count": int(validation.get("warning_count", 0) or 0),
        "lanes": lanes,
        "artifact_links": _artifact_links(project_dir),
        "source": {
            "multi_agent_plan_status": plan.get("status"),
            "multi_agent_plan_schema_version": plan.get("schema_version"),
            "multi_agent_plan_task_count": plan.get("task_count", 0),
            "multi_agent_plan_top_command": plan.get("top_command"),
            "multi_agent_plan_validation_status": validation.get("status", "missing"),
            "multi_agent_plan_validation_issue_count": validation.get("issue_count", 0),
        },
        "guardrails": [
            "Does not execute agent tasks.",
            "Does not run experiments.",
            "Does not create or close human review decisions.",
            "Does not add claim signoffs.",
            "Does not fabricate missing scientific artifacts.",
        ],
        "policy": "Agent boards visualize guarded coordination tasks only; they do not dispatch agents or prove scientific reproduction.",
    }
    board_dir = project_dir / "reports" / "agent_board"
    index_path = board_dir / "index.html"
    manifest_path = project_dir / "reports" / "agent_board_manifest.json"
    board["index_path"] = str(index_path)
    board["manifest_path"] = str(manifest_path)
    board["zip_path"] = str(project_dir / "reports" / "agent_board.zip") if export_zip else str(project_dir / "reports" / "agent_board.zip") if (project_dir / "reports" / "agent_board.zip").exists() else None
    safe_write_text(index_path, _render_html(board))
    write_json(manifest_path, board)
    if export_zip:
        board["zip_path"] = str(_export_zip(project_dir, board))
        write_json(manifest_path, board)
    return board


def agent_board_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing agent board summary without mutating files."""
    project_dir = Path(project_dir)
    index_path = project_dir / "reports" / "agent_board" / "index.html"
    manifest_path = project_dir / "reports" / "agent_board_manifest.json"
    zip_path = project_dir / "reports" / "agent_board.zip"
    data = read_json(manifest_path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": index_path.exists(),
        "path": str(index_path) if index_path.exists() else None,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if index_path.exists() else "missing"),
        "agent_count": int(data.get("agent_count", 0) or 0),
        "task_count": int(data.get("task_count", 0) or 0),
        "open_task_count": int(data.get("open_task_count", 0) or 0),
        "human_input_task_count": int(data.get("human_input_task_count", 0) or 0),
        "validation_status": data.get("validation_status", "missing" if not manifest_path.exists() else None),
        "top_command": data.get("top_command"),
        "sha256": sha256_file(index_path) if index_path.exists() else None,
    }


def _plan(project_dir: Path) -> dict[str, Any]:
    plan_path = project_dir / "workspace" / "multi_agent_plan.json"
    plan = read_json(plan_path, default={}) or {}
    if not isinstance(plan, dict) or not plan:
        plan = generate_multi_agent_plan(project_dir)
    return plan


def _validation(project_dir: Path) -> dict[str, Any]:
    validation_path = project_dir / "workspace" / "multi_agent_plan_validation.json"
    validation = read_json(validation_path, default={}) or {}
    if not isinstance(validation, dict) or not validation:
        validation = validate_multi_agent_plan(project_dir)
    return validation


def _board_status(project_dir: Path, plan: dict[str, Any], validation: dict[str, Any]) -> tuple[str, str | None]:
    if validation.get("status") != "passed":
        command = validation.get("top_command") or f"openrepro validate-multi-agent-plan {project_dir}"
        return "needs_validation", str(command)
    if plan.get("status") == "complete":
        return "complete", None
    return "ready", plan.get("top_command")


def _lanes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = [task for task in plan.get("tasks", []) if isinstance(task, dict)]
    lanes: list[dict[str, Any]] = []
    for agent in AGENT_ROSTER:
        agent_id = agent["agent_id"]
        agent_tasks = [task for task in tasks if task.get("agent_id") == agent_id]
        lanes.append(
            {
                "agent_id": agent_id,
                "label": agent["label"],
                "owns": agent["owns"],
                "task_count": len(agent_tasks),
                "open_task_count": sum(1 for task in agent_tasks if task.get("status") == "open"),
                "human_input_task_count": sum(1 for task in agent_tasks if task.get("requires_human_input")),
                "first_command": agent_tasks[0].get("command") if agent_tasks else None,
                "tasks": agent_tasks,
            }
        )
    return lanes


def _artifact_links(project_dir: Path) -> list[dict[str, Any]]:
    paths = [
        project_dir / "workspace" / "MULTI_AGENT_PLAN.md",
        project_dir / "workspace" / "multi_agent_plan.json",
        project_dir / "workspace" / "MULTI_AGENT_PLAN_VALIDATION.md",
        project_dir / "workspace" / "multi_agent_plan_validation.json",
        project_dir / "handoff" / "COLLABORATION_PACK.md",
        project_dir / "reports" / "DELIVERY_BUNDLE.md",
        project_dir / "reports" / "READINESS_REVIEW.md",
        project_dir / "reports" / "dashboard" / "index.html",
        project_dir / "reports" / "review_site" / "index.html",
        project_dir / "handoff" / "AGENT_HANDOFF.md",
    ]
    return [
        {
            "label": path.name,
            "path": relpath(path, project_dir),
            "present": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for path in paths
    ]


def _export_zip(project_dir: Path, board: dict[str, Any]) -> Path:
    zip_path = project_dir / "reports" / "agent_board.zip"
    files = [
        project_dir / "reports" / "agent_board" / "index.html",
        project_dir / "reports" / "agent_board_manifest.json",
    ]
    files.extend(project_dir / str(item["path"]) for item in board.get("artifact_links", []) if item.get("present"))
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted({path for path in files if path.exists() and path.is_file()}, key=lambda item: item.as_posix()):
            archive.write(path, relpath(path, project_dir).replace("\\", "/"))
    return zip_path


def _badge(value: Any) -> str:
    text = _cell(value)
    normalized = str(value).lower()
    if normalized in {"ready", "complete", "passed", "present", "open"}:
        kind = "good"
    elif normalized in {"missing", "failed", "needs_validation"}:
        kind = "bad"
    else:
        kind = "warn"
    return f'<span class="badge {kind}">{text}</span>'


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value))
    return escape(str(value))


def _artifact_link(item: dict[str, Any]) -> str:
    if not item.get("present"):
        return _cell(item.get("path"))
    href = escape(str(item.get("path")).replace("\\", "/"))
    return f'<a href="../../{href}">{_cell(item.get("path"))}</a>'


def _render_html(board: dict[str, Any]) -> str:
    lane_sections = "\n".join(_lane_html(lane) for lane in board["lanes"])
    artifact_rows = "\n".join(
        f"""
        <tr>
          <td>{_cell(item.get("label"))}</td>
          <td>{_badge("present" if item.get("present") else "missing")}</td>
          <td>{_artifact_link(item)}</td>
          <td><code>{_cell(item.get("sha256"))}</code></td>
        </tr>
        """
        for item in board["artifact_links"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepro Agent Board - {escape(board['project_name'])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #1b2430; --muted: #5b6878; --line: #d8e0ea; --soft: #f7f9fc; --good: #0f7b4f; --warn: #9a5b00; --bad: #b42318; --maintainer: #1f6feb; --reviewer: #7a3fb0; --experimenter: #0f766e; --next: #a15c07; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #ffffff; }}
    header {{ padding: 28px 32px 18px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 24px 28px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 32px 0 12px; font-size: 20px; }}
    h3 {{ margin: 0 0 8px; font-size: 17px; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 18px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; min-height: 82px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 22px; }}
    .board {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; align-items: start; }}
    .lane {{ border: 1px solid var(--line); border-top-width: 5px; border-radius: 8px; background: #fff; min-height: 180px; }}
    .lane.maintainer {{ border-top-color: var(--maintainer); }}
    .lane.reviewer {{ border-top-color: var(--reviewer); }}
    .lane.experimenter {{ border-top-color: var(--experimenter); }}
    .lane.next_agent {{ border-top-color: var(--next); }}
    .lane-head {{ padding: 14px 14px 8px; border-bottom: 1px solid var(--line); }}
    .lane-body {{ padding: 12px; }}
    .task {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin-bottom: 10px; background: #fbfcfe; }}
    .task-title {{ font-weight: 700; margin-bottom: 8px; }}
    .task-meta {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 700; }}
    .good {{ color: var(--good); background: #e9f7ef; }}
    .warn {{ color: var(--warn); background: #fff4df; }}
    .bad {{ color: var(--bad); background: #fdecec; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid var(--line); background: #fff; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    code {{ font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <header>
    <h1>OpenRepro Agent Board: {escape(board['project_name'])}</h1>
    <div>Status: {_badge(board['status'])}</div>
    <p>Generated at {escape(board['created_at'])}. {escape(board['policy'])}</p>
  </header>
  <main>
    <section>
      <h2>Overview</h2>
      <div class="metrics">
        <div class="metric"><span>Agents</span><strong>{_cell(board['agent_count'])}</strong></div>
        <div class="metric"><span>Tasks</span><strong>{_cell(board['task_count'])}</strong></div>
        <div class="metric"><span>Open tasks</span><strong>{_cell(board['open_task_count'])}</strong></div>
        <div class="metric"><span>Human input</span><strong>{_cell(board['human_input_task_count'])}</strong></div>
        <div class="metric"><span>Validation</span><strong>{_badge(board['validation_status'])}</strong></div>
        <div class="metric"><span>Validation issues</span><strong>{_cell(board['validation_issue_count'])}</strong></div>
      </div>
      <p>Top command: <code>{_cell(board.get('top_command'))}</code></p>
    </section>
    <section>
      <h2>Agent Lanes</h2>
      <div class="board">
        {lane_sections}
      </div>
    </section>
    <section>
      <h2>Artifacts</h2>
      <table><thead><tr><th>Artifact</th><th>Present</th><th>Path</th><th>SHA-256</th></tr></thead><tbody>{artifact_rows}</tbody></table>
    </section>
  </main>
</body>
</html>
"""


def _lane_html(lane: dict[str, Any]) -> str:
    tasks = lane.get("tasks", [])
    task_cards = "\n".join(_task_html(task) for task in tasks) or '<p>No open tasks in this lane.</p>'
    return f"""
    <article class="lane {escape(str(lane['agent_id']))}">
      <div class="lane-head">
        <h3>{escape(str(lane['label']))}</h3>
        <p>{escape(str(lane['owns']))}</p>
        <div>{_badge(str(lane.get('open_task_count', 0)) + ' open')}</div>
      </div>
      <div class="lane-body">{task_cards}</div>
    </article>
    """


def _task_html(task: dict[str, Any]) -> str:
    return f"""
    <div class="task">
      <div class="task-title">{_cell(task.get('task_id'))} · {_cell(task.get('title'))}</div>
      <div class="task-meta">
        {_badge(task.get('priority'))}
        {_badge(task.get('status'))}
        {_badge('human input' if task.get('requires_human_input') else 'safe derived')}
      </div>
      <div>Source: {_cell(task.get('source'))}</div>
      <div><code>{_cell(task.get('command'))}</code></div>
    </div>
    """
