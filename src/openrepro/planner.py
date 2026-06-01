"""Experiment plan generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import get_demo_config, load_project_config
from .document_loader import load_source_index
from .utils import iso_now, read_json, safe_write_text, write_json


def _validate_demo_config(config: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if int(config.get("code_length", 0) or 0) <= 0:
        issues.append("demo.code_length must be positive")
    if int(config.get("samples_per_chip", 0) or 0) <= 1:
        issues.append("demo.samples_per_chip must be greater than 1")
    if int(config.get("subcarrier_cycles_per_chip", 0) or 0) <= 0:
        issues.append("demo.subcarrier_cycles_per_chip must be positive")
    if float(config.get("noise_std", -1) or 0) < 0:
        issues.append("demo.noise_std must be non-negative")
    return issues


def validate_experiment_plan(project_dir: Path) -> dict[str, Any]:
    """Validate whether the project has enough evidence for the next experiment step."""
    project_dir = Path(project_dir)
    source_index = load_source_index(project_dir)
    sources = source_index.get("sources", [])
    formula_data = read_json(project_dir / "workspace" / "formula_candidates.json", default={}) or {}
    parameter_data = read_json(project_dir / "workspace" / "parameter_candidates.json", default={}) or {}
    formula_count = len(formula_data.get("candidates", []))
    parameter_count = len(parameter_data.get("candidates", []))
    pdf_sources = [source for source in sources if source.get("suffix") == ".pdf"]
    pdf_failures = [
        source.get("source_name")
        for source in pdf_sources
        if source.get("extraction_status") not in (None, "extracted")
    ]
    issues: list[str] = []
    warnings: list[str] = []

    if not sources:
        issues.append("No sources have been ingested.")
    if not (project_dir / "workspace" / "analysis_result.json").exists():
        warnings.append("Analysis has not been run yet.")
    if pdf_failures:
        warnings.append(f"PDF extraction needs review: {', '.join(str(name) for name in pdf_failures)}")
    if formula_count == 0:
        warnings.append("No formula candidates were detected.")
    if parameter_count == 0:
        warnings.append("No parameter candidates were detected.")

    issues.extend(_validate_demo_config(get_demo_config(project_dir)))
    result = {
        "schema_version": "0.4.0",
        "created_at": iso_now(),
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "source_count": len(sources),
        "pdf_source_count": len(pdf_sources),
        "formula_candidate_count": formula_count,
        "parameter_candidate_count": parameter_count,
    }
    write_json(project_dir / "workspace" / "experiment_plan_validation.json", result)
    return result


def generate_experiment_plan(project_dir: Path) -> Path:
    """Generate workspace/EXPERIMENT_PLAN.md from available project artifacts."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    config = load_project_config(project_dir)
    project_name = config.get("project_name", project_dir.name)
    source_index = load_source_index(project_dir)
    analysis: dict[str, Any] = read_json(project_dir / "workspace" / "analysis_result.json", default={}) or {}
    validation = validate_experiment_plan(project_dir)
    sources = source_index.get("sources", [])
    source_lines = "\n".join(f"- {s.get('source_name')} ({s.get('status')})" for s in sources) or "- 暂无资料"
    detected = ", ".join(analysis.get("detected_keywords", [])) or "待确认"

    plan = f"""# Experiment Plan

## 基本信息

- 项目名称：{project_name}
- 生成时间：{iso_now()}
- 计划版本：v0.4.0-template
- 分析关键词：{detected}
- 计划校验状态：{'通过' if validation['valid'] else '存在阻塞项'}

## 1. 实验目标

建立最小可运行论文复现闭环：导入资料、生成摘要、维护模型账本、运行 lightweight BOC-like Demo、保存数据/图表/报告/API usage/handoff。

## 2. 输入资料

{source_lines}

## 3. 待复现模型

- M001：BOC-like 信号与自相关函数候选模型。
- M002：后续从论文原文提取的真实数学模型（待确认）。

## 4. 待实现代码模块

- 文档加载：Markdown/txt 与 PDF 文本抽取已支持。
- 规则分析器：已支持关键词、段落、公式候选和参数候选抽取。
- Demo Runner：已支持 BOC-like 信号生成、自相关计算、产物保存。
- Sweep Runner：已支持噪声强度与随机种子参数扫掠。
- 后续：真实公式验证、论文级 benchmark。

## 5. 待输出图表

- correlation.png：Demo 自相关函数图。
- 后续可扩展：信号波形图、SNR 扫描图、消融实验图。

## 6. 待保存数据

- demo_signal.npy
- correlation.npy
- demo_metrics.json
- metadata.json
- manifest.json
- api_usage.jsonl / api_usage_summary.json

## 7. 评估指标

- signal_length
- correlation_peak
- correlation_peak_index
- run_time_seconds
- generated_at
- 后续：旁瓣水平、峰值比、捕获成功率、运行稳定性。

## 8. 风险

- v0.4.0 输出候选公式和候选参数，但模型账本仍需要人工核对。
- Demo 不是完整 BOC 捕获/跟踪算法。
- PDF 抽取依赖可读文本层，扫描件可能缺失论文关键信息。
- 没有真实 LLM API 调用，因此不会生成真实 Token 消耗统计。

## 9. v0.4.0 Demo、Sweep、Inspect 与 Benchmark 计划

1. 生成伪随机码。
2. 生成简单方波子载波。
3. 得到 BOC-like 调制信号。
4. 添加少量噪声。
5. 计算自相关函数。
6. 保存图表、数据、报告、metadata 和 API usage 占位统计。
7. 对 noise_std 和 seed 执行参数扫掠，生成 CSV、JSON 与趋势图。
8. 使用 benchmark runner 记录 workflow-compliance evidence。

## 10. 计划校验

```json
{validation}
```

## 11. 下一阶段建议

- 后续版本：加入真实 Provider、实验修复循环和更完整的 benchmark schema 执行器。

## 状态标注

- 已完成：实验计划模板生成。
- 部分完成：Demo 闭环计划和指标定义。
- 未完成：完整论文复现实验矩阵。
- 待确认：真实论文模型、数据集、参数和评估协议。
"""
    path = project_dir / "workspace" / "EXPERIMENT_PLAN.md"
    safe_write_text(path, plan)
    return path
