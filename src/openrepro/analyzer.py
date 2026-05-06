"""Rule-based/mock analyzer for v0.1.0.

The analyzer deliberately avoids real LLM calls.  It scans imported Markdown/txt
files for keyword evidence and writes structured artifacts that downstream
commands can consume.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import load_project_config
from .document_loader import load_source_index, read_text_sources
from .utils import first_markdown_heading, iso_now, safe_write_text, truncate, write_json

KEYWORD_PATTERNS: dict[str, list[str]] = {
    "BOC modulation": ["boc", "binary offset carrier", "subcarrier"],
    "GNSS signal processing": ["gnss", "gps", "galileo", "navigation signal"],
    "correlation analysis": ["correlation", "autocorrelation", "cross-correlation", "相关"],
    "pseudo-random code": ["prn", "pseudo", "spreading", "扩频", "伪随机"],
    "acquisition/tracking": ["acquisition", "tracking", "捕获", "跟踪"],
    "noise/robustness": ["noise", "snr", "噪声", "鲁棒"],
    "evaluation metric": ["metric", "peak", "rmse", "accuracy", "指标"],
    "mathematical model": ["equation", "formula", "model", "方程", "模型"],
}


def _detect_keywords(text: str) -> list[str]:
    lower = text.lower()
    detected: list[str] = []
    for label, patterns in KEYWORD_PATTERNS.items():
        if any(pattern.lower() in lower for pattern in patterns):
            detected.append(label)
    return detected


def _extract_candidate_paragraphs(text: str, limit: int = 4) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    scored: list[tuple[int, str]] = []
    for para in paragraphs:
        score = sum(1 for patterns in KEYWORD_PATTERNS.values() for pat in patterns if pat.lower() in para.lower())
        if score > 0:
            scored.append((score, para))
    scored.sort(key=lambda item: item[0], reverse=True)
    candidates = [truncate(para, 700) for _, para in scored[:limit]]
    if not candidates and paragraphs:
        candidates = [truncate(paragraphs[0], 700)]
    return candidates


def _guess_title(project_name: str, documents: list[dict[str, Any]]) -> str:
    for doc in documents:
        heading = first_markdown_heading(doc["text"])
        if heading:
            return heading
    return f"{project_name} reproduction notes"


def analyze_project(project_dir: Path) -> dict[str, Any]:
    """Analyze imported text sources and generate summary/model ledger artifacts."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    config = load_project_config(project_dir)
    project_name = config.get("project_name", project_dir.name)
    analyzer_version = (config.get("analysis") or {}).get("analyzer_version", "v0.1.0-rule-mock")
    source_index = load_source_index(project_dir)
    documents = read_text_sources(project_dir)

    combined_text = "\n\n".join(doc["text"] for doc in documents)
    detected_keywords = sorted(set(_detect_keywords(combined_text))) if combined_text else []
    title = _guess_title(project_name, documents)
    source_names = [doc["name"] for doc in documents]
    candidate_paragraphs = _extract_candidate_paragraphs(combined_text)

    if not source_names:
        source_note = "No analyzable Markdown/txt source found. PDF files may have been copied as placeholders."
    else:
        source_note = ", ".join(source_names)

    likely_theme = "; ".join(detected_keywords[:5]) if detected_keywords else "待确认：需要更多 Markdown/txt 资料"

    paper_summary = f"""# Paper Summary

## 标题

{title}

## 输入资料列表

{source_note}

## 可能的研究主题

{likely_theme}

## 可能的系统模型

- 输入：伪随机扩频码、子载波、噪声参数、采样参数。
- 处理：BOC-like 调制或扩频信号生成，随后计算相关函数。
- 输出：相关峰值、峰值位置、相关函数曲线、可复现实验数据。

## 可能的算法模块

1. 文献资料解析与结构化摘要。
2. 数学模型账本维护。
3. 信号生成模块。
4. 相关函数计算模块。
5. 指标计算与报告生成模块。

## 可能的实验指标

- signal_length
- correlation_peak
- correlation_peak_index
- run_time_seconds
- 后续可扩展：峰均比、旁瓣水平、捕获概率、SNR 扫描结果。

## 证据片段

{chr(10).join(f'- {p}' for p in candidate_paragraphs) if candidate_paragraphs else '- 暂无可用证据片段。'}

## v0.1.0 局限说明

- 本分析使用规则匹配与 Mock LLM 占位，不调用真实大模型 API。
- PDF 仅支持复制占位，不做文本抽取。
- 数学公式、算法细节和实验设置需要人工复核。
- Demo 仅是 lightweight BOC-like 信号闭环，不代表完整论文复现。
"""

    ledger_rows = []
    if candidate_paragraphs:
        for i, para in enumerate(candidate_paragraphs, start=1):
            ledger_rows.append(
                f"""## M{i:03d}: BOC-like signal/correlation model candidate

- 模型编号：M{i:03d}
- 模型名称：BOC-like signal/correlation model candidate
- 来源段落：{para}
- 数学变量：`c[n]` 伪随机码；`s[n]` 子载波；`x[n]` 调制信号；`r[k]` 自相关函数；`σ` 噪声标准差。
- 方程占位：`x[n] = c[n] * s[n] + ε[n]`；`r[k] = Σ_n x[n] x[n-k]`。
- 参数说明：码长、每码片采样点数、子载波频率/周期数、噪声强度、随机种子。
- 已确认 / 待验证 / 假设：部分确认。文本中存在相关信号处理线索，但公式和参数需要从论文原文核对。
- 后续实现建议：将该候选模型映射为可配置 Python 函数，并增加单元测试和参数扫描。
"""
            )
    else:
        ledger_rows.append(
            """## M001: Placeholder model

- 模型编号：M001
- 模型名称：待确认论文模型
- 来源段落：暂无可分析 Markdown/txt 段落。
- 数学变量：待确认。
- 方程占位：待确认。
- 参数说明：待确认。
- 已确认 / 待验证 / 假设：未确认。
- 后续实现建议：导入 Markdown/txt 资料后重新运行 `openrepro analyze`。
"""
        )

    model_ledger = f"""# Model Ledger

## 说明

该账本由 OpenRepro-Agent v0.1.0 的规则分析器生成，用于保存论文复现中的模型候选、变量、方程占位和人工复核状态。

{chr(10).join(ledger_rows)}

## 总体状态

- 已完成：生成模型候选账本模板。
- 部分完成：从资料中抽取有限证据片段。
- 未完成：严格公式抽取、参数校准、完整算法实现。
- 待确认：所有数学模型和实验设置均需人工复核。
"""

    workspace = project_dir / "workspace"
    generated_files = [
        "workspace/paper_summary.md",
        "workspace/MODEL_LEDGER.md",
        "workspace/analysis_result.json",
    ]
    safe_write_text(workspace / "paper_summary.md", paper_summary)
    safe_write_text(workspace / "MODEL_LEDGER.md", model_ledger)

    result = {
        "project_name": project_name,
        "sources": source_index.get("sources", []),
        "analyzable_sources": source_names,
        "detected_keywords": detected_keywords,
        "generated_files": generated_files,
        "created_at": iso_now(),
        "analyzer_version": analyzer_version,
        "analysis_mode": "rule_based_mock",
        "limitations": [
            "No real LLM API call was made.",
            "PDF text extraction is not implemented in v0.1.0.",
            "Detected models are candidates and require human verification.",
        ],
    }
    write_json(workspace / "analysis_result.json", result)
    return result
