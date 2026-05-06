"""Experiment plan generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_project_config
from .document_loader import load_source_index
from .utils import iso_now, read_json, safe_write_text


def generate_experiment_plan(project_dir: Path) -> Path:
    """Generate workspace/EXPERIMENT_PLAN.md from available project artifacts."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    config = load_project_config(project_dir)
    project_name = config.get("project_name", project_dir.name)
    source_index = load_source_index(project_dir)
    analysis: dict[str, Any] = read_json(project_dir / "workspace" / "analysis_result.json", default={}) or {}
    sources = source_index.get("sources", [])
    source_lines = "\n".join(f"- {s.get('source_name')} ({s.get('status')})" for s in sources) or "- 暂无资料"
    detected = ", ".join(analysis.get("detected_keywords", [])) or "待确认"

    plan = f"""# Experiment Plan

## 基本信息

- 项目名称：{project_name}
- 生成时间：{iso_now()}
- 计划版本：v0.1.0-template
- 分析关键词：{detected}

## 1. 实验目标

建立最小可运行论文复现闭环：导入资料、生成摘要、维护模型账本、运行 lightweight BOC-like Demo、保存数据/图表/报告/API usage/handoff。

## 2. 输入资料

{source_lines}

## 3. 待复现模型

- M001：BOC-like 信号与自相关函数候选模型。
- M002：后续从论文原文提取的真实数学模型（待确认）。

## 4. 待实现代码模块

- 文档加载：Markdown/txt 已支持；PDF 后续扩展。
- 规则分析器：已支持关键词与段落抽取。
- Demo Runner：已支持 BOC-like 信号生成、自相关计算、产物保存。
- 后续：真实公式解析、参数扫描、论文级 benchmark。

## 5. 待输出图表

- correlation.png：Demo 自相关函数图。
- 后续可扩展：信号波形图、SNR 扫描图、消融实验图。

## 6. 待保存数据

- demo_signal.npy
- correlation.npy
- demo_metrics.json
- metadata.json
- api_usage.jsonl / api_usage_summary.json

## 7. 评估指标

- signal_length
- correlation_peak
- correlation_peak_index
- run_time_seconds
- generated_at
- 后续：旁瓣水平、峰值比、捕获成功率、运行稳定性。

## 8. 风险

- v0.1.0 不执行真实论文公式抽取，模型账本需要人工核对。
- Demo 不是完整 BOC 捕获/跟踪算法。
- PDF 仅占位导入，可能缺失论文关键信息。
- 没有真实 LLM API 调用，因此不会生成真实 Token 消耗统计。

## 9. v0.1.0 Demo 计划

1. 生成伪随机码。
2. 生成简单方波子载波。
3. 得到 BOC-like 调制信号。
4. 添加少量噪声。
5. 计算自相关函数。
6. 保存图表、数据、报告、metadata 和 API usage 占位统计。

## 10. 下一阶段建议

- v0.2.0：增加 PDF 文本抽取、公式候选识别、参数表抽取。
- v0.3.0：加入可配置真实 Provider、实验修复循环、benchmark schema 执行器。

## 状态标注

- 已完成：实验计划模板生成。
- 部分完成：Demo 闭环计划和指标定义。
- 未完成：完整论文复现实验矩阵。
- 待确认：真实论文模型、数据集、参数和评估协议。
"""
    path = project_dir / "workspace" / "EXPERIMENT_PLAN.md"
    safe_write_text(path, plan)
    return path
