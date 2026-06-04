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


def _has_run_command(project_dir: Path, command: str) -> bool:
    outputs = project_dir / "outputs"
    if not outputs.exists():
        return False
    for run_dir in outputs.iterdir():
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        if isinstance(manifest, dict) and manifest.get("command") == command:
            return True
    return False


def _experiment_inputs_summary(project_dir: Path) -> list[dict[str, Any]]:
    experiments = project_dir / "experiments"
    if not experiments.exists():
        return []
    summaries: list[dict[str, Any]] = []
    for exp_dir in sorted(path for path in experiments.iterdir() if path.is_dir()):
        inputs = read_json(exp_dir / "experiment_inputs.json", default={}) or {}
        if not isinstance(inputs, dict):
            inputs = {}
        completeness = inputs.get("input_completeness", {}) if inputs else {}
        summaries.append(
            {
                "experiment_id": exp_dir.name,
                "template": inputs.get("template"),
                "input_completeness": completeness.get("status", "missing"),
                "missing_required_inputs": completeness.get("missing", []),
                "parameter_values": inputs.get("parameter_values", {}),
            }
        )
    return summaries


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
    verified = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    reviews = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    repair = read_json(project_dir / "workspace" / "repair_dry_run.json", default={}) or {}
    lineage = read_json(project_dir / "workspace" / "run_lineage.json", default={}) or {}
    checkpoints = read_json(project_dir / "workspace" / "workflow_checkpoints.json", default={}) or {}
    advance = read_json(project_dir / "workspace" / "advance_plan.json", default={}) or {}
    review_board = read_json(project_dir / "workspace" / "review_board.json", default={}) or {}
    review_decisions = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    protocol = read_json(project_dir / "workspace" / "reproduction_protocol.json", default={}) or {}
    protocol_coverage = read_json(project_dir / "workspace" / "protocol_coverage.json", default={}) or {}
    protocol_plan = read_json(project_dir / "workspace" / "protocol_plan.json", default={}) or {}
    protocol_preflight = read_json(project_dir / "workspace" / "protocol_preflight.json", default={}) or {}
    claim_binder = read_json(project_dir / "workspace" / "claim_evidence_binder.json", default={}) or {}
    claim_binder_validation = read_json(project_dir / "workspace" / "claim_evidence_binder_validation.json", default={}) or {}
    claim_signoffs = read_json(project_dir / "workspace" / "claim_signoffs.json", default={}) or {}
    claim_signoff_validation = read_json(project_dir / "workspace" / "claim_signoff_validation.json", default={}) or {}
    claim_evidence_report = read_json(project_dir / "reports" / "claim_evidence_report.json", default={}) or {}
    claim_evidence_report_validation = read_json(project_dir / "reports" / "claim_evidence_report_validation.json", default={}) or {}
    reviewer_packet = read_json(project_dir / "reports" / "reviewer_packet.json", default={}) or {}
    scorecard = read_json(project_dir / "workspace" / "reproduction_scorecard.json", default={}) or {}
    gaps = read_json(project_dir / "workspace" / "reproduction_gaps.json", default={}) or {}
    experiment_inputs = _experiment_inputs_summary(project_dir)
    return f"""# Code Status

## CLI 模块状态

- `cli.py`：已完成 v1.15.0 命令入口。
- `project_manager.py`：已完成 init/status。
- `document_loader.py`：已完成 Markdown/txt 导入和 PDF 文本抽取。
- `analyzer.py`：已完成规则分析、公式候选和参数候选抽取。
- `approval.py`：已完成 verified candidate 审批产物。
- `candidate_review.py`：已完成候选 review 生命周期。
- `experiment_runner.py`：已完成 verified experiment 受控执行。
- `planner.py`：已完成实验计划模板与校验文件。
- `demo_runner.py`：已完成 lightweight BOC-like Demo 和参数扫掠。
- `benchmark_runner.py`：已完成 workflow-compliance benchmark runner。
- `diagnostics.py`：已完成失败分类与修复建议。
- `repair.py`：已完成 repair-plan 和 repair dry-run 预览。
- `lineage.py`：已完成 run lineage 产物。
- `checkpoints.py`：已完成 workflow checkpoint engine。
- `advance.py`：已完成 guided advance dry-run plan。
- `review_board.py`：已完成 human review board。
- `review_decisions.py`：已完成 human review decision loop。
- `reproduction_protocol.py`：已完成 reproduction protocol。
- `protocol_coverage.py`：已完成 protocol coverage。
- `protocol_plan.py`：已完成 protocol action plan。
- `protocol_preflight.py`：已完成 protocol preflight。
- `claim_evidence_binder.py`：已完成 claim evidence binder 与 validation。
- `claim_signoff.py`：已完成 human claim signoff loop。
- `claim_signoff_validation.py`：已完成 claim signoff freshness validation。
- `claim_evidence_report.py`：已完成 reviewer-facing claim evidence report。
- `claim_evidence_report_validation.py`：已完成 claim evidence report freshness validation。
- `reviewer_packet.py`：已完成 reviewer packet generation。
- `scorecard.py`：已完成 workflow readiness scorecard。
- `gaps.py`：已完成 actionable reproduction gaps。
- `doctor.py`：已完成项目健康检查。
- `report_generator.py`：已完成项目报告。
- `handoff_generator.py`：已完成多 Agent 交接文件生成。
- `api_usage.py`：已完成零 Token mock usage 统计。

## 当前项目状态

```json
{status}
```

## Verified Candidate 状态

```json
{verified}
```

## Candidate Review 状态

```json
{reviews}
```

## Repair Dry-Run 状态

```json
{repair}
```

## Run Lineage 状态

```json
{lineage}
```

## Workflow Checkpoints 状态

```json
{checkpoints}
```

## Advance Plan 状态

```json
{advance}
```

## Review Board 状态

```json
{review_board}
```

## Review Decisions 状态

```json
{review_decisions}
```

## Reproduction Protocol 状态

```json
{protocol}
```

## Protocol Coverage 状态

```json
{protocol_coverage}
```

## Protocol Plan 状态

```json
{protocol_plan}
```

## Protocol Preflight 状态

```json
{protocol_preflight}
```

## Claim Evidence Binder 状态

```json
{claim_binder}
```

## Claim Evidence Binder Validation 状态

```json
{claim_binder_validation}
```

## Claim Signoffs 状态

```json
{claim_signoffs}
```

## Claim Signoff Validation 状态

```json
{claim_signoff_validation}
```

## Claim Evidence Report 状态

```json
{claim_evidence_report}
```

## Claim Evidence Report Validation 状态

```json
{claim_evidence_report_validation}
```

## Reviewer Packet 状态

```json
{reviewer_packet}
```

## Readiness Scorecard 状态

```json
{scorecard}
```

## Reproduction Gaps 状态

```json
{gaps}
```

## Experiment Inputs 状态

```json
{experiment_inputs}
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
- 如果 repair dry-run 没有 diff，确认诊断问题是否为 manifest_mismatch 或 missing_manifest。

## 状态

- 已完成：错误记录模板创建。
- 部分完成：仅记录 v0.5.1 常见问题。
- 待确认：后续真实实验中的错误类型。
"""


def _next_steps(project_dir: Path) -> str:
    status = get_status(project_dir)
    return f"""# Next Steps

## 当前建议

{status.next_step}

## v1.15.0 闭环检查

- ingest: {'已完成' if status.ingested else '未完成'}
- analyze: {'已完成' if status.analyzed else '未完成'}
- plan: {'已完成' if status.planned else '未完成'}
- approve-candidates: {'已完成' if (project_dir / 'workspace' / 'verified_candidates.json').exists() else '未完成'}
- review-candidates: {'已完成' if (project_dir / 'workspace' / 'candidate_reviews.json').exists() else '未完成'}
- run-experiment: {'已完成' if _has_run_command(project_dir, 'run-experiment') else '未完成'}
- run-demo: {'已完成' if status.latest_run_dir else '未完成'}
- report: {'已完成' if status.report_exists else '未完成'}
- repair-dry-run: {'已完成' if (project_dir / 'workspace' / 'repair_dry_run.json').exists() else '未完成'}
- lineage: {'已完成' if (project_dir / 'workspace' / 'run_lineage.json').exists() else '未完成'}
- checkpoints: {'已完成' if (project_dir / 'workspace' / 'workflow_checkpoints.json').exists() else '未完成'}
- advance-plan: {'已完成' if (project_dir / 'workspace' / 'advance_plan.json').exists() else '未完成'}
- review-board: {'已完成' if (project_dir / 'workspace' / 'review_board.json').exists() else '未完成'}
- review-decisions: {'已完成' if (project_dir / 'workspace' / 'review_decisions.json').exists() else '未完成'}
- protocol: {'已完成' if (project_dir / 'workspace' / 'reproduction_protocol.json').exists() else '未完成'}
- protocol-coverage: {'已完成' if (project_dir / 'workspace' / 'protocol_coverage.json').exists() else '未完成'}
- protocol-plan: {'已完成' if (project_dir / 'workspace' / 'protocol_plan.json').exists() else '未完成'}
- protocol-preflight: {'已完成' if (project_dir / 'workspace' / 'protocol_preflight.json').exists() else '未完成'}
- evidence-binder: {'已完成' if (project_dir / 'workspace' / 'claim_evidence_binder.json').exists() else '未完成'}
- validate-evidence-binder: {'已完成' if (project_dir / 'workspace' / 'claim_evidence_binder_validation.json').exists() else '未完成'}
- claim-signoff: {'已完成' if (project_dir / 'workspace' / 'claim_signoffs.json').exists() else '未完成'}
- validate-claim-signoffs: {'已完成' if (project_dir / 'workspace' / 'claim_signoff_validation.json').exists() else '未完成'}
- claim-evidence-report: {'已完成' if (project_dir / 'reports' / 'claim_evidence_report.md').exists() else '未完成'}
- validate-claim-evidence-report: {'已完成' if (project_dir / 'reports' / 'claim_evidence_report_validation.md').exists() else '未完成'}
- reviewer-packet: {'已完成' if (project_dir / 'reports' / 'reviewer_packet.md').exists() else '未完成'}
- scorecard: {'已完成' if (project_dir / 'workspace' / 'reproduction_scorecard.json').exists() else '未完成'}
- gaps: {'已完成' if (project_dir / 'workspace' / 'reproduction_gaps.json').exists() else '未完成'}
- handoff: {'已完成' if status.handoff_complete else '未完成'}
- evidence-package: {'已完成' if status.evidence_package_exists else '未完成'}

## 下一阶段建议

1. 人工核对 `workspace/MODEL_LEDGER.md` 中的模型变量和方程占位。
2. 将论文真实参数填入 `workspace/EXPERIMENT_PLAN.md`。
3. 使用 `openrepro approve-candidates <project> --all --reviewer <name>` 记录审批产物。
4. 使用 `openrepro validate` 校验最新运行 manifest。
5. 使用 `openrepro repair <project> --dry-run` 预览可控修复。
6. 使用 `openrepro lineage <project>` 生成 run lineage。
7. 使用 `openrepro benchmark --task benchmarks/sample_task.json` 记录 workflow-compliance evidence。
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
    verified = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    reviews = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    repair = read_json(project_dir / "workspace" / "repair_dry_run.json", default={}) or {}
    lineage = read_json(project_dir / "workspace" / "run_lineage.json", default={}) or {}
    checkpoints = read_json(project_dir / "workspace" / "workflow_checkpoints.json", default={}) or {}
    advance = read_json(project_dir / "workspace" / "advance_plan.json", default={}) or {}
    review_board = read_json(project_dir / "workspace" / "review_board.json", default={}) or {}
    review_decisions = read_json(project_dir / "workspace" / "review_decisions.json", default={}) or {}
    protocol = read_json(project_dir / "workspace" / "reproduction_protocol.json", default={}) or {}
    protocol_coverage = read_json(project_dir / "workspace" / "protocol_coverage.json", default={}) or {}
    protocol_plan = read_json(project_dir / "workspace" / "protocol_plan.json", default={}) or {}
    protocol_preflight = read_json(project_dir / "workspace" / "protocol_preflight.json", default={}) or {}
    claim_binder = read_json(project_dir / "workspace" / "claim_evidence_binder.json", default={}) or {}
    claim_binder_validation = read_json(project_dir / "workspace" / "claim_evidence_binder_validation.json", default={}) or {}
    claim_signoffs = read_json(project_dir / "workspace" / "claim_signoffs.json", default={}) or {}
    claim_signoff_validation = read_json(project_dir / "workspace" / "claim_signoff_validation.json", default={}) or {}
    claim_evidence_report = read_json(project_dir / "reports" / "claim_evidence_report.json", default={}) or {}
    claim_evidence_report_validation = read_json(project_dir / "reports" / "claim_evidence_report_validation.json", default={}) or {}
    reviewer_packet = read_json(project_dir / "reports" / "reviewer_packet.json", default={}) or {}
    scorecard = read_json(project_dir / "workspace" / "reproduction_scorecard.json", default={}) or {}
    gaps = read_json(project_dir / "workspace" / "reproduction_gaps.json", default={}) or {}
    experiment_inputs = _experiment_inputs_summary(project_dir)
    return f"""# Agent Handoff

## 给 Claude Code / Codex / GitHub Copilot 的接续说明

这是 OpenRepro-Agent v{__version__} 生成的项目级交接文件。当前目标不是声称完成论文复现，而是维护一个最小可运行的科研复现工程闭环。

## 当前状态摘要

```json
{status.to_dict()}
```

## 最近运行目录

{f'`{latest}`' if latest else '暂无'}

## Verified Candidate 摘要

```json
{verified}
```

## Candidate Review 摘要

```json
{reviews}
```

## Repair Dry-Run 摘要

```json
{repair}
```

## Run Lineage 摘要

```json
{lineage}
```

## Workflow Checkpoints 摘要

```json
{checkpoints}
```

## Advance Plan 摘要

```json
{advance}
```

## Review Board 摘要

```json
{review_board}
```

## Review Decisions 摘要

```json
{review_decisions}
```

## Reproduction Protocol 摘要

```json
{protocol}
```

## Protocol Coverage 摘要

```json
{protocol_coverage}
```

## Protocol Plan 摘要

```json
{protocol_plan}
```

## Protocol Preflight 摘要

```json
{protocol_preflight}
```

## Claim Evidence Binder 摘要

```json
{claim_binder}
```

## Claim Evidence Binder Validation 摘要

```json
{claim_binder_validation}
```

## Claim Signoffs 摘要

```json
{claim_signoffs}
```

## Claim Signoff Validation 摘要

```json
{claim_signoff_validation}
```

## Claim Evidence Report 摘要

```json
{claim_evidence_report}
```

## Claim Evidence Report Validation 摘要

```json
{claim_evidence_report_validation}
```

## Reviewer Packet 摘要

```json
{reviewer_packet}
```

## Readiness Scorecard 摘要

```json
{scorecard}
```

## Reproduction Gaps 摘要

```json
{gaps}
```

## Experiment Inputs 摘要

```json
{experiment_inputs}
```

## 接续开发重点

1. 先阅读 `handoff/PROJECT_CONTEXT.md`。
2. 核对 `handoff/PAPER_SUMMARY.md` 和 `handoff/MODEL_LEDGER.md`，不要把规则分析结果当作已验证事实。
3. 检查 `handoff/EXPERIMENT_PLAN.md` 中的 Demo 与后续真实复现实验差异。
4. 检查 `handoff/VERIFIED_CANDIDATES.md` 和 `handoff/REPAIR_DRY_RUN.md`，确认审批与修复预览状态。
5. 检查 `handoff/RUN_LINEAGE.md`，确认 run provenance 是否齐全。
6. 若要接入真实 LLM Provider，请扩展 `api_usage.py`，保留零 Token mock 统计原则。
7. 所有新增实验结果必须来自实际运行产物，不得虚构 benchmark 或 Token 消耗。

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
        "VERIFIED_CANDIDATES.md": _copy_or_placeholder(
            project_dir / "workspace" / "VERIFIED_CANDIDATES.md",
            "Verified Candidates",
            "尚未运行 approve-candidates，暂无人工审批候选。",
        ),
        "CANDIDATE_REVIEWS.md": _copy_or_placeholder(
            project_dir / "workspace" / "CANDIDATE_REVIEWS.md",
            "Candidate Reviews",
            "尚未运行 review-candidates，暂无候选 review 历史。",
        ),
        "EXPERIMENT_PLAN.md": _copy_or_placeholder(
            project_dir / "workspace" / "EXPERIMENT_PLAN.md",
            "Experiment Plan",
            "尚未运行 plan，无法提供实验计划。",
        ),
        "CODE_STATUS.md": _code_status(project_dir),
        "RUN_LOG_SUMMARY.md": _run_log_summary(project_dir),
        "ERROR_NOTES.md": _error_notes(project_dir),
        "REPAIR_DRY_RUN.md": _copy_or_placeholder(
            project_dir / "workspace" / "REPAIR_DRY_RUN.md",
            "Repair Dry Run",
            "尚未运行 repair --dry-run，暂无修复预览。",
        ),
        "RUN_LINEAGE.md": _copy_or_placeholder(
            project_dir / "workspace" / "RUN_LINEAGE.md",
            "Run Lineage",
            "尚未运行 lineage，暂无运行谱系。",
        ),
        "WORKFLOW_CHECKPOINTS.md": _copy_or_placeholder(
            project_dir / "workspace" / "WORKFLOW_CHECKPOINTS.md",
            "Workflow Checkpoints",
            "尚未运行 checkpoints，暂无工作流 checkpoint 摘要。",
        ),
        "ADVANCE_PLAN.md": _copy_or_placeholder(
            project_dir / "workspace" / "ADVANCE_PLAN.md",
            "Advance Plan",
            "尚未运行 advance --dry-run，暂无推进计划。",
        ),
        "REVIEW_BOARD.md": _copy_or_placeholder(
            project_dir / "workspace" / "REVIEW_BOARD.md",
            "Review Board",
            "尚未运行 review-board，暂无人工审阅面板。",
        ),
        "REVIEW_DECISIONS.md": _copy_or_placeholder(
            project_dir / "workspace" / "REVIEW_DECISIONS.md",
            "Review Decisions",
            "尚未运行 review-decision 或 evidence-package，暂无人工审阅决策记录。",
        ),
        "REPRODUCTION_PROTOCOL.md": _copy_or_placeholder(
            project_dir / "workspace" / "REPRODUCTION_PROTOCOL.md",
            "Reproduction Protocol",
            "尚未运行 protocol，暂无复现协议。",
        ),
        "PROTOCOL_COVERAGE.md": _copy_or_placeholder(
            project_dir / "workspace" / "PROTOCOL_COVERAGE.md",
            "Protocol Coverage",
            "尚未运行 protocol-coverage，暂无协议覆盖率摘要。",
        ),
        "PROTOCOL_PLAN.md": _copy_or_placeholder(
            project_dir / "workspace" / "PROTOCOL_PLAN.md",
            "Protocol Plan",
            "尚未运行 protocol-plan，暂无协议行动计划。",
        ),
        "PROTOCOL_PREFLIGHT.md": _copy_or_placeholder(
            project_dir / "workspace" / "PROTOCOL_PREFLIGHT.md",
            "Protocol Preflight",
            "尚未运行 protocol-preflight，暂无协议预检摘要。",
        ),
        "CLAIM_EVIDENCE_BINDER.md": _copy_or_placeholder(
            project_dir / "workspace" / "CLAIM_EVIDENCE_BINDER.md",
            "Claim Evidence Binder",
            "尚未运行 evidence-binder，暂无 claim 证据绑定摘要。",
        ),
        "CLAIM_EVIDENCE_BINDER_VALIDATION.md": _copy_or_placeholder(
            project_dir / "workspace" / "CLAIM_EVIDENCE_BINDER_VALIDATION.md",
            "Claim Evidence Binder Validation",
            "尚未运行 validate-evidence-binder，暂无 claim 证据绑定校验摘要。",
        ),
        "CLAIM_SIGNOFFS.md": _copy_or_placeholder(
            project_dir / "workspace" / "CLAIM_SIGNOFFS.md",
            "Claim Signoffs",
            "尚未运行 claim-signoff，暂无 claim 签核摘要。",
        ),
        "CLAIM_SIGNOFF_VALIDATION.md": _copy_or_placeholder(
            project_dir / "workspace" / "CLAIM_SIGNOFF_VALIDATION.md",
            "Claim Signoff Validation",
            "尚未运行 validate-claim-signoffs，暂无 claim signoff 校验摘要。",
        ),
        "CLAIM_EVIDENCE_REPORT.md": _copy_or_placeholder(
            project_dir / "reports" / "claim_evidence_report.md",
            "Claim Evidence Report",
            "尚未运行 claim-evidence-report，暂无 claim evidence report。",
        ),
        "CLAIM_EVIDENCE_REPORT_VALIDATION.md": _copy_or_placeholder(
            project_dir / "reports" / "claim_evidence_report_validation.md",
            "Claim Evidence Report Validation",
            "尚未运行 validate-claim-evidence-report，暂无 claim evidence report 校验摘要。",
        ),
        "REVIEWER_PACKET.md": _copy_or_placeholder(
            project_dir / "reports" / "reviewer_packet.md",
            "Reviewer Packet",
            "尚未运行 reviewer-packet，暂无 reviewer packet。",
        ),
        "REPRODUCTION_SCORECARD.md": _copy_or_placeholder(
            project_dir / "workspace" / "REPRODUCTION_SCORECARD.md",
            "Reproduction Readiness Scorecard",
            "尚未运行 scorecard，暂无复现准备度评分卡。",
        ),
        "REPRODUCTION_GAPS.md": _copy_or_placeholder(
            project_dir / "workspace" / "REPRODUCTION_GAPS.md",
            "Reproduction Gaps",
            "尚未运行 gaps，暂无复现缺口清单。",
        ),
        "EVIDENCE_PACKAGE.md": _copy_or_placeholder(
            project_dir / "reports" / "evidence_package.md",
            "Evidence Package",
            "尚未运行 evidence-package，暂无项目级证据包。",
        ),
        "NEXT_STEPS.md": _next_steps(project_dir),
        "AGENT_HANDOFF.md": _agent_handoff(project_dir),
    }
    written: list[Path] = []
    for name in required_handoff_files():
        path = handoff / name
        safe_write_text(path, content_map[name])
        written.append(path)
    return written
