"""Multi-agent handoff file generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .artifact_manager import latest_run_dir, required_handoff_files
from .config import load_project_config
from .document_loader import load_source_index
from .project_manager import get_status
from .utils import iso_now, read_json, read_text, safe_write_text, truncate


def _source_lines(project_dir: Path) -> str:
    index = load_source_index(project_dir)
    sources = index.get("sources", [])
    if not sources:
        return "- 暂无导入资料"
    return "\n".join(
        f"- {item.get('source_name')} | status={item.get('status')} | note={item.get('note')}" for item in sources
    )


def _copy_or_placeholder(source: Path, title: str, placeholder: str) -> str:
    if source.exists():
        return source.read_text(encoding="utf-8")
    return f"# {title}\n\n{placeholder}\n\n## 状态\n\n- 已完成：文件模板已创建。\n- 部分完成：等待上游命令生成正式内容。\n- 未完成：正式分析内容。\n- 待确认：输入资料与复现目标。\n"


def _run_log_summary(project_dir: Path) -> str:
    latest = latest_run_dir(project_dir)
    if latest is None:
        return "# Run Log Summary\n\n暂无运行记录。\n\n## 下一步建议\n\n运行 `openrepro run-demo <project_name>` 生成 Demo 产物。\n"
    log_text = read_text(latest / "logs" / "run.log", default="未找到 run.log。")
    metrics = read_json(latest / "data" / "demo_metrics.json", default={}) or {}
    return f"""# Run Log Summary

## 最近一次运行目录

`{latest}`

## 日志摘要

```text
{truncate(log_text, 1600)}
```

## 指标摘要

```json
{metrics}
```

## 状态

- 已完成：最近一次 Demo 运行日志已记录。
- 部分完成：仅包含 lightweight Demo。
- 待确认：是否需要真实论文实验矩阵。
"""


def _code_status(project_dir: Path) -> str:
    status = get_status(project_dir).to_dict()
    return f"""# Code Status

## CLI 模块状态

- `cli.py`：已完成 v0.4.0 命令入口。
- `project_manager.py`：已完成 init/status。
- `document_loader.py`：已完成 Markdown/txt 导入和 PDF 文本抽取。
- `analyzer.py`：已完成规则分析、公式候选和参数候选抽取。
- `planner.py`：已完成实验计划模板与校验文件。
- `demo_runner.py`：已完成 lightweight BOC-like Demo 和参数扫掠。
- `benchmark_runner.py`：已完成 workflow-compliance benchmark runner。
- `diagnostics.py`：已完成失败分类与修复建议。
- `report_generator.py`：已完成项目报告。
- `handoff_generator.py`：已完成多 Agent 交接文件生成。
- `api_usage.py`：已完成零 Token mock usage 统计。

## 当前项目状态

```json
{status}
```

## 已完成

- [x] 最小 CLI 工程闭环
- [x] pytest 覆盖关键命令与产物

## 部分完成

- [ ] 真实论文公式和参数尚未人工验证

## 未完成

- [ ] Web UI
- [ ] 真实 LLM Provider
- [x] workflow-compliance benchmark runner

## 待确认

- 后续 API Provider 接入方式
- 真实论文复现任务范围
"""


def _error_notes(project_dir: Path) -> str:
    latest = latest_run_dir(project_dir)
    known = "暂无已知运行错误。"
    if latest is not None and not (latest / "figures" / "correlation.png").exists():
        known = "最近一次运行缺少 figures/correlation.png，请检查 matplotlib 环境。"
    return f"""# Error Notes

## 已知错误

{known}

## 排查建议

- 如果 CLI 找不到命令，确认已运行 `pip install -e \".[dev]\"`。
- 如果图表无法生成，确认 matplotlib 可用并使用非交互后端。
- 如果 analyze 输出为空，确认已导入 Markdown/txt，或 PDF 具有可抽取文本层。

## 状态

- 已完成：错误记录模板创建。
- 部分完成：仅记录 v0.4.0 常见问题。
- 待确认：后续真实实验中的错误类型。
"""


def _next_steps(project_dir: Path) -> str:
    status = get_status(project_dir)
    return f"""# Next Steps

## 当前建议

{status.next_step}

## v0.4.0 闭环检查

- ingest: {'已完成' if status.ingested else '未完成'}
- analyze: {'已完成' if status.analyzed else '未完成'}
- plan: {'已完成' if status.planned else '未完成'}
- run-demo: {'已完成' if status.latest_run_dir else '未完成'}
- report: {'已完成' if status.report_exists else '未完成'}
- handoff: {'已完成' if status.handoff_complete else '未完成'}

## 下一阶段建议

1. 人工核对 `workspace/MODEL_LEDGER.md` 中的模型变量和方程占位。
2. 将论文真实参数填入 `workspace/EXPERIMENT_PLAN.md`。
3. 使用 `openrepro validate` 校验最新运行 manifest。
4. 使用 `openrepro benchmark --task benchmarks/sample_task.json` 记录 workflow-compliance evidence。
"""


def _project_context(project_dir: Path) -> str:
    config = load_project_config(project_dir)
    status = get_status(project_dir)
    return f"""# Project Context

## 基本信息

- 项目名称：{config.get('project_name', project_dir.name)}
- OpenRepro-Agent 版本：{__version__}
- 项目创建时间：{config.get('created_at', 'unknown')}
- Handoff 更新时间：{iso_now()}

## 输入资料

{_source_lines(project_dir)}

## 当前状态

```json
{status.to_dict()}
```

## 已完成

- [x] 标准项目结构
- [x] 可运行 CLI 闭环基础设施

## 部分完成

- [ ] 论文理解与模型实现仍需人工确认

## 待确认

- 目标论文完整文本
- 复现实验范围
- 真实数据和参数
"""


def _agent_handoff(project_dir: Path) -> str:
    status = get_status(project_dir)
    latest = latest_run_dir(project_dir)
    return f"""# Agent Handoff

## 给 Claude Code / Codex / GitHub Copilot 的接续说明

这是 OpenRepro-Agent v{__version__} 生成的项目级交接文件。当前目标不是声称完成论文复现，而是维护一个最小可运行的科研复现工程闭环。

## 当前状态摘要

```json
{status.to_dict()}
```

## 最近运行目录

{f'`{latest}`' if latest else '暂无'}

## 接续开发重点

1. 先阅读 `handoff/PROJECT_CONTEXT.md`。
2. 核对 `handoff/PAPER_SUMMARY.md` 和 `handoff/MODEL_LEDGER.md`，不要把规则分析结果当作已验证事实。
3. 检查 `handoff/EXPERIMENT_PLAN.md` 中的 Demo 与后续真实复现实验差异。
4. 若要接入真实 LLM Provider，请扩展 `api_usage.py`，保留零 Token mock 统计原则。
5. 所有新增实验结果必须来自实际运行产物，不得虚构 benchmark 或 Token 消耗。

## 已完成

- [x] 项目初始化、导入、分析、计划、Demo、报告、handoff 命令接口
- [x] Lightweight BOC-like Demo 闭环
- [x] API usage 占位统计

## 部分完成

- [ ] 论文模型理解仅是规则/Mock 结果

## 未完成

- [x] PDF 文本抽取
- [x] 公式候选和参数候选抽取
- [ ] 自动公式验证
- [ ] 完整仿真代码生成与修复循环
- [ ] Benchmark 结果

## 待确认

- 论文具体公式和参数
- 后续版本 Provider 与缓存策略

## 下一步建议

{status.next_step}
"""


def generate_handoff(project_dir: Path) -> list[Path]:
    """Generate or update all project-level handoff files."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    handoff = project_dir / "handoff"
    handoff.mkdir(parents=True, exist_ok=True)
    content_map = {
        "PROJECT_CONTEXT.md": _project_context(project_dir),
        "PAPER_SUMMARY.md": _copy_or_placeholder(
            project_dir / "workspace" / "paper_summary.md",
            "Paper Summary",
            "尚未运行 analyze，无法提供论文结构摘要。",
        ),
        "MODEL_LEDGER.md": _copy_or_placeholder(
            project_dir / "workspace" / "MODEL_LEDGER.md",
            "Model Ledger",
            "尚未运行 analyze，无法提供模型账本。",
        ),
        "EXPERIMENT_PLAN.md": _copy_or_placeholder(
            project_dir / "workspace" / "EXPERIMENT_PLAN.md",
            "Experiment Plan",
            "尚未运行 plan，无法提供实验计划。",
        ),
        "CODE_STATUS.md": _code_status(project_dir),
        "RUN_LOG_SUMMARY.md": _run_log_summary(project_dir),
        "ERROR_NOTES.md": _error_notes(project_dir),
        "NEXT_STEPS.md": _next_steps(project_dir),
        "AGENT_HANDOFF.md": _agent_handoff(project_dir),
    }
    written: list[Path] = []
    for name in required_handoff_files():
        path = handoff / name
        safe_write_text(path, content_map[name])
        written.append(path)
    return written
