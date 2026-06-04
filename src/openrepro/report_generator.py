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


def _advance_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "advance_plan.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 advance plan。运行 `openrepro advance <project> --dry-run` 后会生成推进计划。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- dry_run: {data.get('dry_run')}",
            f"- action_count: {data.get('action_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- source: {data.get('source')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _review_board_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "review_board.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 review board。运行 `openrepro review-board <project>` 后会生成人工审阅面板。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- item_count: {data.get('item_count', 0)}",
            f"- critical_count: {data.get('critical_count', 0)}",
            f"- high_count: {data.get('high_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _review_decisions_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 review decisions。运行 `openrepro review-decision <project> --item-id <id> --decision needs_followup --reviewer <name>` 后会记录人工审阅决策。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- decision_count: {data.get('decision_count', 0)}",
            f"- closed_count: {data.get('closed_count', 0)}",
            f"- followup_count: {data.get('followup_count', 0)}",
            f"- deferred_count: {data.get('deferred_count', 0)}",
            f"- unresolved_item_count: {data.get('unresolved_item_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _protocol_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "reproduction_protocol.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 reproduction protocol。运行 `openrepro protocol <project>` 后会生成复现协议。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- criterion_count: {data.get('criterion_count', 0)}",
            f"- blocking_criterion_count: {data.get('blocking_criterion_count', 0)}",
            f"- target_claim_count: {len(data.get('target_claims', [])) if isinstance(data.get('target_claims'), list) else 0}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _protocol_coverage_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "protocol_coverage.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 protocol coverage。运行 `openrepro protocol-coverage <project>` 后会生成协议覆盖率摘要。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- coverage_score: {data.get('coverage_score')}",
            f"- dimension_count: {data.get('dimension_count', 0)}",
            f"- uncovered_count: {data.get('uncovered_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _protocol_plan_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "protocol_plan.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 protocol plan。运行 `openrepro protocol-plan <project>` 后会生成协议行动计划。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- action_count: {data.get('action_count', 0)}",
            f"- critical_count: {data.get('critical_count', 0)}",
            f"- high_count: {data.get('high_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _protocol_preflight_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "protocol_preflight.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 protocol preflight。运行 `openrepro protocol-preflight <project>` 后会生成协议预检摘要。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- check_count: {data.get('check_count', 0)}",
            f"- blocking_count: {data.get('blocking_count', 0)}",
            f"- warning_count: {data.get('warning_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _claim_evidence_binder_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "claim_evidence_binder.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 claim evidence binder。运行 `openrepro evidence-binder <project>` 后会生成 claim 证据绑定摘要。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- claim_count: {data.get('claim_count', 0)}",
            f"- complete_claim_count: {data.get('complete_claim_count', 0)}",
            f"- incomplete_claim_count: {data.get('incomplete_claim_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _claim_evidence_binder_validation_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "claim_evidence_binder_validation.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 claim evidence binder validation。运行 `openrepro validate-evidence-binder <project>` 后会生成 binder 校验摘要。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- valid: {data.get('valid')}",
            f"- issue_count: {data.get('issue_count', 0)}",
            f"- warning_count: {data.get('warning_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _claim_signoffs_block(project_dir: Path) -> str:
    data = read_json(project_dir / "workspace" / "claim_signoffs.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 claim signoffs。运行 `openrepro claim-signoff <project> --claim-id <id> --decision accepted_workflow_evidence --reviewer <name>` 后会生成 claim 签核摘要。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- claim_count: {data.get('claim_count', 0)}",
            f"- signoff_count: {data.get('signoff_count', 0)}",
            f"- signed_claim_count: {data.get('signed_claim_count', 0)}",
            f"- open_claim_count: {data.get('open_claim_count', 0)}",
            f"- accepted_count: {data.get('accepted_count', 0)}",
            f"- needs_more_evidence_count: {data.get('needs_more_evidence_count', 0)}",
            f"- top_command: {data.get('top_command')}",
            f"- policy: {data.get('policy')}",
        ]
    )


def _claim_evidence_report_block(project_dir: Path) -> str:
    data = read_json(project_dir / "reports" / "claim_evidence_report.json", default={}) or {}
    if not isinstance(data, dict) or not data:
        return "暂无 claim evidence report。运行 `openrepro claim-evidence-report <project>` 后会生成 claim 证据矩阵报告。"
    return "\n".join(
        [
            f"- status: {data.get('status')}",
            f"- claim_count: {data.get('claim_count', 0)}",
            f"- validation_status: {data.get('validation_status')}",
            f"- signoff_status: {data.get('signoff_status')}",
            f"- open_action_count: {data.get('open_action_count', 0)}",
            f"- top_command: {data.get('top_command')}",
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
    advance_block = _advance_block(project_dir)
    review_board_block = _review_board_block(project_dir)
    review_decisions_block = _review_decisions_block(project_dir)
    protocol_block = _protocol_block(project_dir)
    protocol_coverage_block = _protocol_coverage_block(project_dir)
    protocol_plan_block = _protocol_plan_block(project_dir)
    protocol_preflight_block = _protocol_preflight_block(project_dir)
    claim_binder_block = _claim_evidence_binder_block(project_dir)
    claim_binder_validation_block = _claim_evidence_binder_validation_block(project_dir)
    claim_signoffs_block = _claim_signoffs_block(project_dir)
    claim_evidence_report_block = _claim_evidence_report_block(project_dir)
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

## 13. Advance Plan 摘要

{advance_block}

## 14. Review Board 摘要

{review_board_block}

## 15. Review Decisions 摘要

{review_decisions_block}

## 16. Reproduction Protocol 摘要

{protocol_block}

## 17. Protocol Coverage 摘要

{protocol_coverage_block}

## 18. Protocol Plan 摘要

{protocol_plan_block}

## 19. Protocol Preflight 摘要

{protocol_preflight_block}

## 20. Claim Evidence Binder 摘要

{claim_binder_block}

## 21. Claim Evidence Binder Validation 摘要

{claim_binder_validation_block}

## 22. Claim Signoffs 摘要

{claim_signoffs_block}

## 23. Claim Evidence Report 摘要

{claim_evidence_report_block}

## 24. Reproduction Readiness Scorecard 摘要

{scorecard_block}

## 25. Reproduction Gaps 摘要

{gaps_block}

## 26. 当前局限

- 资料分析基于规则与 Mock LLM 占位。
- PDF 抽取依赖可读文本层，扫描件或复杂排版可能需要人工补录。
- Demo 是 lightweight BOC-like 自相关实验，不是完整论文复现。
- 没有声明 benchmark 成绩、用户数、Token 消耗或效率提升。

## 27. 下一阶段建议

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
