"""Project-level report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .artifact_manager import latest_run_dir
from .config import load_project_config
from .document_loader import load_source_index
from .utils import iso_now, read_json, read_text, safe_write_text, truncate


def _section_from_file(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    return truncate(path.read_text(encoding="utf-8"), 1800)


def _latest_run_summary(project_dir: Path) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    latest = latest_run_dir(project_dir)
    if latest is None:
        return "暂无 Demo 运行目录。", None, None
    metrics = read_json(latest / "data" / "demo_metrics.json", default=None)
    if metrics is None:
        sweep = read_json(latest / "data" / "sweep_results.json", default=None)
        if isinstance(sweep, dict):
            metrics = {
                "sweep_result_count": len(sweep.get("results", [])),
                "noise_std_values": sweep.get("noise_std_values", []),
                "seeds": sweep.get("seeds", []),
            }
    api_summary = read_json(latest / "api_usage" / "api_usage_summary.json", default=None)
    summary = f"最近一次运行目录：`{latest}`"
    return summary, metrics, api_summary


def _verified_candidates_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 verified candidate 记录。运行 `openrepro approve-candidates <project> --all --reviewer <name>` 后会生成审批摘要。"
    formula_ids = ", ".join(str(item) for item in data.get("formula_candidate_ids", [])) or "none"
    parameter_ids = ", ".join(str(item) for item in data.get("parameter_candidate_ids", [])) or "none"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- reviewer: {data.get('reviewer')}",
            f"- formula_candidate_count: {data.get('formula_candidate_count', 0)}",
            f"- parameter_candidate_count: {data.get('parameter_candidate_count', 0)}",
            f"- formula_candidate_ids: {formula_ids}",
            f"- parameter_candidate_ids: {parameter_ids}",
            f"- note: {data.get('verification_note')}",
        ]
    )


def _repair_dry_run_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "repair_dry_run.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 repair dry-run 记录。需要预览修复时运行 `openrepro repair <project> --dry-run`。"
    return "\n".join(
        [
            f"- created_at: {data.get('created_at')}",
            f"- healthy: {data.get('healthy')}",
            f"- action_count: {data.get('action_count', 0)}",
            f"- run_dir: `{data.get('run_dir')}`",
            f"- policy: {data.get('policy')}",
        ]
    )


def _scorecard_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "reproduction_scorecard.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 readiness scorecard。运行 `openrepro scorecard <project>` 后会生成工程准备度摘要。"
    return "\n".join(
        [
            f"- overall_score: {data.get('overall_score')}",
            f"- overall_status: {data.get('overall_status')}",
            f"- blocking_dimension_count: {data.get('blocking_dimension_count', 0)}",
            f"- partial_dimension_count: {data.get('partial_dimension_count', 0)}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _checkpoint_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "workflow_checkpoints.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 workflow checkpoints。运行 `openrepro checkpoints <project>` 后会生成统一阶段摘要。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- complete_count: {data.get('complete_count', 0)}",
            f"- partial_count: {data.get('partial_count', 0)}",
            f"- blocked_count: {data.get('blocked_count', 0)}",
            f"- missing_count: {data.get('missing_count', 0)}",
            f"- next_checkpoint: {data.get('next_checkpoint')}",
            f"- next_command: {data.get('next_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _gaps_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "reproduction_gaps.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 reproduction gaps。运行 `openrepro gaps <project>` 后会生成可执行缺口清单。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- open_count: {data.get('open_count', 0)}",
            f"- critical_count: {data.get('critical_count', 0)}",
            f"- high_count: {data.get('high_count', 0)}",
            f"- top_suggested_command: {data.get('top_suggested_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def generate_report(project_dir: Path) -> Path:
    """Generate reports/report.md."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    config = load_project_config(project_dir)
    project_name = config.get("project_name", project_dir.name)
    source_index = load_source_index(project_dir)
    sources = source_index.get("sources", [])
    source_lines = "\n".join(f"- {s.get('source_name')} — {s.get('status')}" for s in sources) or "- 暂无输入资料"

    analysis_summary = _section_from_file(project_dir / "workspace" / "paper_summary.md", "尚未生成 paper_summary.md。")
    ledger_summary = _section_from_file(project_dir / "workspace" / "MODEL_LEDGER.md", "尚未生成 MODEL_LEDGER.md。")
    plan_summary = _section_from_file(project_dir / "workspace" / "EXPERIMENT_PLAN.md", "尚未生成 EXPERIMENT_PLAN.md。")
    run_summary, metrics, api_summary = _latest_run_summary(project_dir)
    verified_block = _verified_candidates_block(project_dir)
    repair_block = _repair_dry_run_block(project_dir)
    checkpoint_block = _checkpoint_block(project_dir)
    scorecard_block = _scorecard_block(project_dir)
    gaps_block = _gaps_block(project_dir)

    metrics_block = "无"
    if metrics is not None:
        metrics_block = "\n".join(f"- {k}: {v}" for k, v in metrics.items())

    api_block = "无真实 API 调用；暂无统计文件。"
    if api_summary is not None:
        api_block = "\n".join(f"- {k}: {v}" for k, v in api_summary.items() if k != "providers")
        api_block += f"\n- providers: {api_summary.get('providers')}"

    latest = latest_run_dir(project_dir)
    output_paths = [
        "workspace/paper_summary.md",
        "workspace/MODEL_LEDGER.md",
        "workspace/EXPERIMENT_PLAN.md",
        "reports/report.md",
    ]
    if latest:
        output_paths.extend(
            [
                str(latest / "figures" / "correlation.png"),
                str(latest / "data" / "demo_metrics.json"),
                str(latest / "data" / "sweep_results.json"),
                str(latest / "reports" / "demo_report.md"),
                str(latest / "manifest.json"),
            ]
        )
    output_block = "\n".join(f"- `{p}`" for p in output_paths)

    report = f"""# OpenRepro-Agent Project Report

## 1. 项目名称

{project_name}

## 2. 当前版本

OpenRepro-Agent v{__version__}

报告生成时间：{iso_now()}

## 3. 输入资料

{source_lines}

## 4. 分析摘要

{analysis_summary}

## 5. 模型账本摘要

{ledger_summary}

## 6. 实验计划摘要

{plan_summary}

## 7. 最近一次 Demo 运行结果

{run_summary}

### Demo 指标

{metrics_block}

## 8. 输出产物路径

{output_block}

## 9. API 使用统计摘要

{api_block}

说明：当前版本默认使用 mock provider；真实 provider 需要显式 opt-in。mock 与 cached 事件不计为真实调用，也不会虚构 Token 消耗或成本。

## 10. Verified Candidate 审批摘要

{verified_block}

## 11. Repair Dry-Run 摘要

{repair_block}

## 12. Workflow Checkpoints 摘要

{checkpoint_block}

## 13. Reproduction Readiness Scorecard 摘要

{scorecard_block}

## 14. Reproduction Gaps 摘要

{gaps_block}

## 15. 当前局限

- 资料分析基于规则与 Mock LLM 占位。
- PDF 抽取依赖可读文本层，扫描件或复杂排版可能需要人工补录。
- Demo 是 lightweight BOC-like 自相关实验，不是完整论文复现。
- 没有声明 benchmark 成绩、用户数、Token 消耗或效率提升。

## 16. 下一阶段建议

- 补充论文原始 Markdown/txt/PDF 资料并人工核对模型账本。
- 将真实公式、参数表和实验设置写入 EXPERIMENT_PLAN.md。
- 使用 scaffold-experiment 生成需人工确认的实验代码起点。
- 使用 manifest 和 `openrepro validate` 校验运行产物。
- 使用 benchmark runner、benchmark suite 和 benchmark index 记录 workflow-compliance evidence。
- 在后续版本中加入真实 Provider、缓存统计与更完整的可复现实验 benchmark。
"""
    path = project_dir / "reports" / "report.md"
    safe_write_text(path, report)
    return path
