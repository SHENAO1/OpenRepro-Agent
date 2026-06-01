"""Project initialization and status inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .artifact_manager import latest_run_dir, required_handoff_files
from .config import create_project_config, load_project_config, save_project_config
from .utils import ensure_dirs, iso_now, project_required_dirs, read_json, safe_write_text


@dataclass
class InitResult:
    project_dir: Path
    created: bool
    message: str
    next_steps: list[str]


@dataclass
class ProjectStatus:
    project_name: str
    project_dir: str
    exists: bool
    initialized: bool
    ingested: bool
    analyzed: bool
    planned: bool
    latest_run_dir: str | None
    report_exists: bool
    handoff_complete: bool
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _initial_project_context(project_name: str) -> str:
    return f"""# Project Context: {project_name}

## 项目状态

- 项目名称：{project_name}
- OpenRepro-Agent 版本：{__version__}
- 初始化时间：{iso_now()}
- 当前阶段：已初始化，等待导入论文资料

## 已完成

- [x] 创建标准项目目录
- [x] 写入 project_config.yaml
- [x] 创建初始 handoff 文件

## 部分完成

- [ ] 论文资料尚未导入
- [ ] 结构分析尚未执行
- [ ] Demo 实验尚未运行

## 待确认

- 论文标题、模型、公式、实验指标
- 是否需要真实 API Provider
- 后续复现实验范围

## 下一步建议

1. 运行 `openrepro ingest {project_name} --source examples/boc_notes.md` 导入资料。
2. 运行 `openrepro analyze {project_name}` 生成初步摘要与模型账本。
"""


def _initial_agent_handoff(project_name: str) -> str:
    return f"""# Agent Handoff: {project_name}

## 给下一位 Agent 的摘要

该项目已通过 OpenRepro-Agent v{__version__} 初始化，目前还没有导入论文资料。请先检查
`project_config.yaml`，再执行 ingest/analyze/plan/run-demo/report/handoff 闭环。

## 已完成

- [x] 项目目录初始化
- [x] 初始交接文件创建

## 部分完成

- [ ] 资料分析流程尚未执行

## 未完成

- [ ] 论文结构摘要
- [ ] 数学模型账本
- [ ] 实验计划
- [ ] Demo 运行产物
- [ ] 项目报告

## 待确认

- 论文来源文件
- 目标复现范围
- 是否需要将 mock analyzer 替换为真实 LLM Provider

## 下一步建议

从 `openrepro status {project_name}` 开始确认状态，然后按 CLI 快速开始顺序推进。
"""


def _initial_next_steps(project_name: str) -> str:
    return f"""# Next Steps: {project_name}

## 立即可执行

1. 导入资料：`openrepro ingest {project_name} --source examples/boc_notes.md`
2. 分析资料：`openrepro analyze {project_name}`
3. 生成计划：`openrepro plan {project_name}`
4. 运行 Demo：`openrepro run-demo {project_name}`
5. 生成报告：`openrepro report {project_name}`
6. 更新交接：`openrepro handoff {project_name}`

## 已完成

- [x] 初始化项目

## 部分完成

- [ ] 工程闭环等待执行

## 待确认

- 真实论文资料路径
- Demo 参数是否需要调整
"""


def init_project(project_name: str, base_dir: Path | None = None) -> InitResult:
    """Initialize an OpenRepro paper reproduction project."""
    base = Path.cwd() if base_dir is None else base_dir
    project_dir = base / project_name
    next_steps = [
        f"openrepro ingest {project_name} --source examples/boc_notes.md",
        f"openrepro analyze {project_name}",
        f"openrepro plan {project_name}",
        f"openrepro run-demo {project_name}",
    ]

    if project_dir.exists():
        return InitResult(
            project_dir=project_dir,
            created=False,
            message=f"Project '{project_name}' already exists. Existing files were not overwritten.",
            next_steps=next_steps,
        )

    ensure_dirs(project_required_dirs(project_dir))
    config = create_project_config(project_name)
    save_project_config(project_dir, config, overwrite=False)

    handoff_dir = project_dir / "handoff"
    safe_write_text(handoff_dir / "PROJECT_CONTEXT.md", _initial_project_context(project_name), overwrite=False)
    safe_write_text(handoff_dir / "AGENT_HANDOFF.md", _initial_agent_handoff(project_name), overwrite=False)
    safe_write_text(handoff_dir / "NEXT_STEPS.md", _initial_next_steps(project_name), overwrite=False)
    safe_write_text(project_dir / "logs" / "project.log", f"[{iso_now()}] project initialized\n", overwrite=False)

    return InitResult(
        project_dir=project_dir,
        created=True,
        message=f"Initialized OpenRepro-Agent project '{project_name}'.",
        next_steps=next_steps,
    )


def require_project(project_name: str | Path) -> Path:
    """Return a project path or raise FileNotFoundError when missing."""
    project_dir = Path(project_name)
    if not project_dir.exists() or not project_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    return project_dir


def get_status(project_name: str | Path) -> ProjectStatus:
    """Inspect a project's current workflow state."""
    project_dir = Path(project_name)
    exists = project_dir.exists() and project_dir.is_dir()
    initialized = exists and (project_dir / "project_config.yaml").exists()

    if not exists:
        return ProjectStatus(
            project_name=str(project_name),
            project_dir=str(project_dir),
            exists=False,
            initialized=False,
            ingested=False,
            analyzed=False,
            planned=False,
            latest_run_dir=None,
            report_exists=False,
            handoff_complete=False,
            next_step=f"Run: openrepro init {project_name}",
        )

    config = load_project_config(project_dir)
    detected_name = config.get("project_name", project_dir.name)
    source_index = read_json(project_dir / "workspace" / "source_index.json", default={}) or {}
    sources = source_index.get("sources", []) if isinstance(source_index, dict) else []
    ingested = len(sources) > 0
    analyzed = (project_dir / "workspace" / "paper_summary.md").exists() and (
        project_dir / "workspace" / "MODEL_LEDGER.md"
    ).exists()
    planned = (project_dir / "workspace" / "EXPERIMENT_PLAN.md").exists()
    latest = latest_run_dir(project_dir)
    report_exists = (project_dir / "reports" / "report.md").exists()
    handoff_complete = all((project_dir / "handoff" / name).exists() for name in required_handoff_files())

    if not ingested:
        next_step = f"Run: openrepro ingest {project_dir} --source <markdown_or_txt>"
    elif not analyzed:
        next_step = f"Run: openrepro analyze {project_dir}"
    elif not planned:
        next_step = f"Run: openrepro plan {project_dir}"
    elif latest is None:
        next_step = f"Run: openrepro run-demo {project_dir}"
    elif not report_exists:
        next_step = f"Run: openrepro report {project_dir}"
    elif not handoff_complete:
        next_step = f"Run: openrepro handoff {project_dir}"
    else:
        next_step = "Project v0.3.0 workflow is complete. Review manifests, reports, benchmarks, and handoff files."

    return ProjectStatus(
        project_name=detected_name,
        project_dir=str(project_dir),
        exists=exists,
        initialized=initialized,
        ingested=ingested,
        analyzed=analyzed,
        planned=planned,
        latest_run_dir=str(latest) if latest else None,
        report_exists=report_exists,
        handoff_complete=handoff_complete,
        next_step=next_step,
    )
