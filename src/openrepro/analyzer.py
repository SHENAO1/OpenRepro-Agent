"""Rule-based analyzer for OpenRepro-Agent.

The analyzer deliberately avoids real LLM calls. It scans imported text and
PDF-extracted sources for keyword evidence, formula candidates, and parameter
candidates, then writes structured artifacts for downstream commands.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import load_project_config
from .document_loader import load_source_index, read_pdf_page_records, read_text_sources
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

FORMULA_HINTS = [
    "equation",
    "formula",
    "model",
    "where",
    "let",
    "定义",
    "方程",
    "公式",
    "模型",
]

PARAMETER_PATTERN = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9_ /().-]{1,48})\s*(?:=|:)\s*"
    r"(?P<value>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*(?P<unit>[A-Za-z/%._-]+)?"
)
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
CAPTION_PATTERN = re.compile(
    r"^\s*(?P<kind>fig(?:ure)?|table)\s*(?P<label>[A-Za-z0-9.:-]*)\s*[:.\-]?\s+(?P<text>.+)$",
    re.IGNORECASE,
)
SECTION_HINTS: dict[str, list[str]] = {
    "abstract": ["abstract", "摘要"],
    "introduction": ["introduction", "background", "引言", "背景"],
    "methods": ["method", "methods", "methodology", "algorithm", "材料", "方法", "算法"],
    "experiments": ["experiment", "experiments", "evaluation", "实验", "评估"],
    "results": ["result", "results", "结果"],
    "discussion": ["discussion", "分析", "讨论"],
    "conclusion": ["conclusion", "结论"],
}


def _source_path_for_doc(doc: dict[str, Any]) -> str:
    path = doc.get("path")
    if isinstance(path, Path):
        return str(path)
    return str(path or "")


def _chunk_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for doc in documents:
        raw_chunks = [item.strip() for item in re.split(r"\n+|(?<=[。.!?])\s+", doc["text"]) if item.strip()]
        current_section = "unknown"
        for index, chunk in enumerate(raw_chunks):
            section = _section_label(chunk) or current_section
            if _section_label(chunk):
                current_section = section
            chunks.append(
                {
                    "doc": doc,
                    "chunk_index": index,
                    "text": chunk,
                    "previous": raw_chunks[index - 1] if index > 0 else "",
                    "next": raw_chunks[index + 1] if index + 1 < len(raw_chunks) else "",
                    "section": section,
                }
            )
    return chunks


def _section_label(text: str) -> str | None:
    stripped = text.strip().strip("#").strip().lower()
    stripped = re.sub(r"^\d+(?:\.\d+)*\s+", "", stripped)
    for label, hints in SECTION_HINTS.items():
        if any(stripped == hint or stripped.startswith(f"{hint}:") or stripped.startswith(f"{hint} ") for hint in hints):
            return label
    return None


def _caption_index(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    for doc in documents:
        current_section = "unknown"
        for line_index, line in enumerate(doc["text"].splitlines(), start=1):
            section = _section_label(line)
            if section:
                current_section = section
            match = CAPTION_PATTERN.match(line)
            if not match:
                continue
            kind = "table" if match.group("kind").lower().startswith("table") else "figure"
            captions.append(
                {
                    "caption_id": f"C{len(captions) + 1:03d}",
                    "source_name": doc["name"],
                    "source_path": _source_path_for_doc(doc),
                    "line_index": line_index,
                    "kind": kind,
                    "label": match.group("label").strip() or None,
                    "section": current_section,
                    "text": truncate(match.group("text").strip(), 700),
                    "status": "caption_unverified",
                }
            )
    return captions


def _section_counts(chunks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        section = str(chunk.get("section") or "unknown")
        counts[section] = counts.get(section, 0) + 1
    return counts


def _page_number_for_evidence(project_dir: Path, source_name: str, evidence: str) -> int | None:
    if not evidence:
        return None
    for page_record in read_pdf_page_records(project_dir):
        if page_record.get("source_name") != source_name:
            continue
        page = page_record.get("page", {})
        page_text = str(page.get("text") or "")
        if evidence in page_text:
            return int(page.get("page_number") or 0) or None
    return None


def _evidence_quality(evidence: str, page_number: int | None, method: str) -> dict[str, Any]:
    score = 0.35
    reasons = []
    if len(evidence) >= 20:
        score += 0.2
        reasons.append("sufficient_context")
    if any(op in evidence for op in ["=", "^", "_", "\\sum", "Σ"]):
        score += 0.2
        reasons.append("contains_math_signal")
    if page_number is not None:
        score += 0.15
        reasons.append("page_anchored")
    if method.startswith("pdf_table"):
        score += 0.1
        reasons.append("table_anchored")
    return {"score": round(min(score, 1.0), 3), "reasons": reasons or ["rule_based_match"]}


def _candidate_risk(evidence_quality: dict[str, Any], provenance: dict[str, Any], context_window: str) -> dict[str, Any]:
    flags: list[str] = []
    if provenance.get("page_number") is None:
        flags.append("no_page_anchor")
    if provenance.get("section") in {None, "", "unknown"}:
        flags.append("unknown_section")
    if len(context_window.strip()) < 40:
        flags.append("thin_context")
    if float(evidence_quality.get("score", 0.0) or 0.0) < 0.55:
        flags.append("low_evidence_quality")
    flags.append("needs_human_review")
    if "low_evidence_quality" in flags or len(flags) >= 4:
        level = "high"
    elif len(flags) >= 2:
        level = "medium"
    else:
        level = "low"
    return {"risk_level": level, "risk_flags": flags}


def _provenance(
    project_dir: Path,
    doc: dict[str, Any],
    chunk_index: int | None,
    evidence: str,
    method: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_name = str(doc.get("name") or "")
    page_number = _page_number_for_evidence(project_dir, source_name, evidence)
    data: dict[str, Any] = {
        "source_name": source_name,
        "source_path": _source_path_for_doc(doc),
        "page_number": page_number,
        "chunk_index": chunk_index,
        "extraction_method": method,
    }
    if extra:
        data.update(extra)
    return data


def _normalize_unit(unit: str) -> str:
    normalized = unit.strip()
    aliases = {"sec": "s", "secs": "s", "second": "s", "seconds": "s", "hz": "Hz", "%": "%"}
    return aliases.get(normalized.lower(), normalized)


def _paper_metadata(project_name: str, documents: list[dict[str, Any]], combined_text: str) -> dict[str, Any]:
    dois = sorted(set(match.group(0).rstrip(".,;)") for match in DOI_PATTERN.finditer(combined_text)))
    return {
        "schema_version": "0.8.0",
        "created_at": iso_now(),
        "project_name": project_name,
        "title_guess": _guess_title(project_name, documents),
        "doi_candidates": dois,
        "source_count": len(documents),
        "sources": [
            {
                "source_name": doc["name"],
                "source_path": _source_path_for_doc(doc),
                "char_count": len(doc["text"]),
            }
            for doc in documents
        ],
        "policy": "Paper metadata is extracted heuristically and requires human confirmation.",
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


def _looks_like_formula(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 6:
        return False
    lower = stripped.lower()
    has_math_operator = any(op in stripped for op in ["=", "Σ", "\\sum", "^", "_", "[", "]"])
    has_formula_hint = any(hint in lower for hint in FORMULA_HINTS)
    has_inline_math = "$" in stripped or "\\(" in stripped or "\\[" in stripped
    return has_inline_math or (has_math_operator and (has_formula_hint or "=" in stripped))


def _extract_formula_candidates(project_dir: Path, documents: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in _chunk_documents(documents):
        evidence = truncate(chunk["text"], 500)
        if not evidence or evidence in seen or not _looks_like_formula(evidence):
            continue
        seen.add(evidence)
        context_window = truncate("\n".join(part for part in [chunk["previous"], evidence, chunk["next"]] if part), 900)
        provenance = _provenance(
            project_dir,
            chunk["doc"],
            chunk["chunk_index"],
            evidence,
            "rule_formula_pattern",
            extra={"section": chunk.get("section")},
        )
        evidence_quality = _evidence_quality(evidence, provenance.get("page_number"), "rule_formula_pattern")
        risk = _candidate_risk(evidence_quality, provenance, context_window)
        candidates.append(
            {
                "candidate_id": f"F{len(candidates) + 1:03d}",
                "source_name": chunk["doc"]["name"],
                "evidence": evidence,
                "context_before": truncate(chunk["previous"], 300),
                "context_after": truncate(chunk["next"], 300),
                "context_window": context_window,
                "section": chunk.get("section"),
                "provenance": provenance,
                "evidence_quality": evidence_quality,
                "risk_level": risk["risk_level"],
                "risk_flags": risk["risk_flags"],
                "status": "candidate_unverified",
                "extraction_method": "rule_formula_pattern",
            }
        )
        if len(candidates) >= limit:
            return candidates
    return candidates


def _extract_parameter_candidates_from_text(project_dir: Path, documents: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for chunk in _chunk_documents(documents):
        doc = chunk["doc"]
        for match in PARAMETER_PATTERN.finditer(chunk["text"]):
            name = " ".join(match.group("name").split())
            value = match.group("value")
            unit = match.group("unit") or ""
            key = (doc["name"], name.lower(), value)
            if key in seen:
                continue
            seen.add(key)
            evidence = truncate(match.group(0), 300)
            context_window = truncate("\n".join(part for part in [chunk["previous"], evidence, chunk["next"]] if part), 900)
            provenance = _provenance(
                project_dir,
                doc,
                chunk["chunk_index"],
                evidence,
                "rule_parameter_pattern",
                extra={"section": chunk.get("section")},
            )
            evidence_quality = _evidence_quality(evidence, provenance.get("page_number"), "rule_parameter_pattern")
            risk = _candidate_risk(evidence_quality, provenance, context_window)
            candidates.append(
                {
                    "candidate_id": f"P{len(candidates) + 1:03d}",
                    "source_name": doc["name"],
                    "name": name,
                    "value": value,
                    "value_numeric": float(value),
                    "unit": unit,
                    "unit_normalized": _normalize_unit(unit),
                    "evidence": evidence,
                    "context_before": truncate(chunk["previous"], 300),
                    "context_after": truncate(chunk["next"], 300),
                    "context_window": context_window,
                    "section": chunk.get("section"),
                    "provenance": provenance,
                    "evidence_quality": evidence_quality,
                    "risk_level": risk["risk_level"],
                    "risk_flags": risk["risk_flags"],
                    "status": "candidate_unverified",
                    "extraction_method": "rule_parameter_pattern",
                }
            )
            if len(candidates) >= limit:
                return candidates
    return candidates


def _extract_parameter_candidates_from_tables(
    project_dir: Path,
    existing_count: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    page_records = read_pdf_page_records(project_dir)
    for page_record in page_records:
        page = page_record.get("page", {})
        for table_index, table in enumerate(page.get("tables", []), start=1):
            for row_index, row in enumerate(table, start=1):
                cells = [str(cell).strip() for cell in row if str(cell).strip()]
                if len(cells) < 2 or not any(re.search(r"[-+]?\d", cell) for cell in cells[1:]):
                    continue
                name = cells[0]
                value = next((cell for cell in cells[1:] if re.search(r"[-+]?\d", cell)), cells[1])
                evidence = " | ".join(cells)
                doc = {
                    "name": page_record.get("source_name"),
                    "path": project_dir / str((page_record.get("record") or {}).get("copied_path", "")),
                }
                provenance = _provenance(
                    project_dir,
                    doc,
                    None,
                    str(value),
                    "pdf_table_candidate",
                    extra={
                        "page_number": page.get("page_number"),
                        "section": "tables",
                        "table_index": table_index,
                        "row_index": row_index,
                        "table_cells": cells,
                    },
                )
                evidence_quality = _evidence_quality(evidence, page.get("page_number"), "pdf_table_candidate")
                risk = _candidate_risk(evidence_quality, provenance, evidence)
                candidates.append(
                    {
                        "candidate_id": f"P{existing_count + len(candidates) + 1:03d}",
                        "source_name": page_record.get("source_name"),
                        "name": name,
                        "value": value,
                        "value_numeric": float(re.search(r"[-+]?\d+(?:\.\d+)?", value).group(0)) if re.search(r"[-+]?\d+(?:\.\d+)?", value) else None,
                        "unit": "",
                        "unit_normalized": "",
                        "evidence": evidence,
                        "page_number": page.get("page_number"),
                        "table_index": table_index,
                        "row_index": row_index,
                        "section": "tables",
                        "provenance": provenance,
                        "evidence_quality": evidence_quality,
                        "risk_level": risk["risk_level"],
                        "risk_flags": risk["risk_flags"],
                        "status": "candidate_unverified",
                        "extraction_method": "pdf_table_candidate",
                    }
                )
                if len(candidates) >= limit:
                    return candidates
    return candidates


def _build_structured_model_ledger(
    project_name: str,
    candidate_paragraphs: list[str],
    formula_candidates: list[dict[str, Any]],
    parameter_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    model_count = max(1, min(4, len(candidate_paragraphs) or len(formula_candidates) or 1))
    models: list[dict[str, Any]] = []
    formula_ids = [item["candidate_id"] for item in formula_candidates]
    parameter_ids = [item["candidate_id"] for item in parameter_candidates]
    for index in range(model_count):
        models.append(
            {
                "model_id": f"M{index + 1:03d}",
                "name": "paper model candidate" if formula_candidates else "placeholder model candidate",
                "source_evidence": candidate_paragraphs[index] if index < len(candidate_paragraphs) else "",
                "formula_candidate_ids": formula_ids[:5],
                "parameter_candidate_ids": parameter_ids[:8],
                "status": "candidate_unverified",
                "verification_notes": "Candidate extracted by rules; formulas and parameters require human review.",
            }
        )
    return {
        "schema_version": "0.4.0",
        "project_name": project_name,
        "created_at": iso_now(),
        "status": "candidate_unverified",
        "models": models,
    }


def _candidate_risk_counts(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    risk_levels: dict[str, int] = {}
    risk_flags: dict[str, int] = {}
    for candidate in candidates:
        level = str(candidate.get("risk_level") or "unknown")
        risk_levels[level] = risk_levels.get(level, 0) + 1
        for flag in candidate.get("risk_flags", []):
            label = str(flag)
            risk_flags[label] = risk_flags.get(label, 0) + 1
    return {"risk_levels": risk_levels, "risk_flags": risk_flags}


def _render_caption_index(captions: list[dict[str, Any]]) -> str:
    lines = [
        "# Caption Index",
        "",
        "| ID | Kind | Source | Section | Text |",
        "| --- | --- | --- | --- | --- |",
    ]
    for caption in captions:
        text = str(caption.get("text") or "").replace("|", "/")
        lines.append(
            f"| {caption['caption_id']} | {caption['kind']} | {caption['source_name']} | {caption['section']} | {text} |"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "Captions are rule-extracted evidence anchors and require human review.",
            "",
        ]
    )
    return "\n".join(lines)


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
    analyzer_version = (config.get("analysis") or {}).get("analyzer_version", "v1.21.1-rule")
    source_index = load_source_index(project_dir)
    documents = read_text_sources(project_dir)
    chunks = _chunk_documents(documents)

    combined_text = "\n\n".join(doc["text"] for doc in documents)
    detected_keywords = sorted(set(_detect_keywords(combined_text))) if combined_text else []
    title = _guess_title(project_name, documents)
    source_names = [doc["name"] for doc in documents]
    candidate_paragraphs = _extract_candidate_paragraphs(combined_text)
    formula_candidates = _extract_formula_candidates(project_dir, documents)
    text_parameter_candidates = _extract_parameter_candidates_from_text(project_dir, documents)
    table_parameter_candidates = _extract_parameter_candidates_from_tables(project_dir, len(text_parameter_candidates))
    parameter_candidates = text_parameter_candidates + table_parameter_candidates
    all_candidates = formula_candidates + parameter_candidates
    risk_counts = _candidate_risk_counts(all_candidates)
    captions = _caption_index(documents)
    section_counts = _section_counts(chunks)
    metadata = _paper_metadata(project_name, documents, combined_text)
    metadata["schema_version"] = "1.1.0"
    metadata["section_counts"] = section_counts
    metadata["caption_count"] = len(captions)
    structured_ledger = _build_structured_model_ledger(
        project_name,
        candidate_paragraphs,
        formula_candidates,
        parameter_candidates,
    )

    if not source_names:
        source_note = "No analyzable text source found. Add Markdown/txt notes or a PDF with extractable text."
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

## 公式候选

{chr(10).join(f"- {item['candidate_id']} ({item['status']}): {item['evidence']}" for item in formula_candidates[:10]) if formula_candidates else "- 暂无公式候选。"}

## 参数候选

{chr(10).join(f"- {item['candidate_id']} ({item['status']}): {item['name']} = {item['value']} {item.get('unit', '')}".rstrip() for item in parameter_candidates[:12]) if parameter_candidates else "- 暂无参数候选。"}

## 证据片段

{chr(10).join(f'- {p}' for p in candidate_paragraphs) if candidate_paragraphs else '- 暂无可用证据片段。'}

## v0.4.0 局限说明

- 本分析使用规则匹配与 Mock LLM 占位，不调用真实大模型 API。
- PDF 文本和表格由 pdfplumber 抽取，扫描件或复杂排版可能无法完整读取。
- 数学公式、参数、算法细节和实验设置均为候选，需要人工复核。
- Demo 仅是 lightweight BOC-like 信号闭环，不代表完整论文复现。
"""

    ledger_rows = []
    for model in structured_ledger["models"]:
        formula_lines = "\n".join(f"  - {item['candidate_id']}: {item['evidence']}" for item in formula_candidates[:5])
        parameter_lines = "\n".join(
            f"  - {item['candidate_id']}: {item['name']} = {item['value']} {item.get('unit', '')}".rstrip()
            for item in parameter_candidates[:8]
        )
        ledger_rows.append(
            f"""## {model['model_id']}: {model['name']}

- 模型编号：{model['model_id']}
- 状态：{model['status']}
- 来源证据：{model.get('source_evidence') or '暂无可分析证据段落。'}
- 公式候选：
{formula_lines or '  - 暂无公式候选。'}
- 参数候选：
{parameter_lines or '  - 暂无参数候选。'}
- 验证说明：{model['verification_notes']}
- 后续实现建议：人工核对候选公式和参数，再映射为可配置实验代码。
"""
        )

    model_ledger = f"""# Model Ledger

## 说明

该账本由 OpenRepro-Agent v0.4.0 的规则分析器生成，用于保存论文复现中的模型候选、公式候选、参数候选和人工复核状态。所有候选默认标记为 `candidate_unverified`。

{chr(10).join(ledger_rows)}

## 总体状态

- 已完成：生成模型候选账本模板。
- 部分完成：从资料中抽取有限证据片段、公式候选和参数候选。
- 未完成：严格公式验证、参数校准、完整算法实现。
- 待确认：所有数学模型和实验设置均需人工复核。
"""

    workspace = project_dir / "workspace"
    generated_files = [
        "workspace/paper_summary.md",
        "workspace/MODEL_LEDGER.md",
        "workspace/analysis_result.json",
        "workspace/formula_candidates.json",
        "workspace/parameter_candidates.json",
        "workspace/model_ledger.json",
        "workspace/paper_metadata.json",
        "workspace/caption_index.json",
        "workspace/CAPTION_INDEX.md",
    ]
    safe_write_text(workspace / "paper_summary.md", paper_summary)
    safe_write_text(workspace / "MODEL_LEDGER.md", model_ledger)
    write_json(
        workspace / "formula_candidates.json",
        {
            "schema_version": "0.4.0",
            "created_at": iso_now(),
            "status": "candidate_unverified",
            "risk_summary": _candidate_risk_counts(formula_candidates),
            "candidates": formula_candidates,
        },
    )
    write_json(
        workspace / "parameter_candidates.json",
        {
            "schema_version": "0.4.0",
            "created_at": iso_now(),
            "status": "candidate_unverified",
            "risk_summary": _candidate_risk_counts(parameter_candidates),
            "candidates": parameter_candidates,
        },
    )
    write_json(workspace / "model_ledger.json", structured_ledger)
    write_json(workspace / "paper_metadata.json", metadata)
    write_json(
        workspace / "caption_index.json",
        {
            "schema_version": "1.1.0",
            "created_at": iso_now(),
            "caption_count": len(captions),
            "captions": captions,
            "policy": "Captions are rule-extracted evidence anchors and require human review.",
        },
    )
    safe_write_text(workspace / "CAPTION_INDEX.md", _render_caption_index(captions))

    result = {
        "project_name": project_name,
        "sources": source_index.get("sources", []),
        "analyzable_sources": source_names,
        "detected_keywords": detected_keywords,
        "generated_files": generated_files,
        "created_at": iso_now(),
        "analyzer_version": analyzer_version,
        "analysis_mode": "rule_based_candidates",
        "formula_candidate_count": len(formula_candidates),
        "parameter_candidate_count": len(parameter_candidates),
        "model_candidate_count": len(structured_ledger["models"]),
        "paper_metadata": metadata,
        "doi_candidate_count": len(metadata["doi_candidates"]),
        "section_counts": section_counts,
        "caption_count": len(captions),
        "candidate_risk_counts": risk_counts,
        "high_risk_candidate_count": risk_counts["risk_levels"].get("high", 0),
        "limitations": [
            "No real LLM API call was made.",
            "PDF text extraction depends on pdfplumber and may miss scanned or complex layouts.",
            "Detected formulas, parameters, and models are candidates and require human verification.",
        ],
    }
    write_json(workspace / "analysis_result.json", result)
    return result
