"""Project initialization and status inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .acceptance_criteria import acceptance_criteria_summary
from .advance import advance_summary
from .artifact_manager import latest_run_dir, required_handoff_files
from .checkpoints import checkpoint_summary
from .claim_evidence_binder import claim_evidence_binder_summary, claim_evidence_binder_validation_summary
from .claim_evidence_report import claim_evidence_report_summary
from .claim_evidence_report_validation import claim_evidence_report_validation_summary
from .claim_signoff import claim_signoff_summary
from .claim_signoff_validation import claim_signoff_validation_summary
from .claim_trace import claim_trace_summary
from .collaboration_pack import collaboration_pack_summary
from .config import create_project_config, load_project_config, save_project_config
from .dashboard import dashboard_summary
from .data_registry import data_index_summary
from .evidence_fingerprint import evidence_package_status
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .freshness import artifact_freshness_summary
from .gaps import gaps_summary
from .protocol_coverage import protocol_coverage_summary
from .protocol_plan import protocol_plan_summary
from .protocol_preflight import protocol_preflight_summary
from .project_profile import project_profile_summary
from .quality_gate import latest_experiment_quality_gate_summary, latest_quality_gate_summary
from .readiness_review import readiness_review_summary
from .readiness_review_validation import readiness_review_validation_summary
from .refresh import refresh_run_summary
from .review_board import review_board_summary
from .review_decisions import review_decision_summary
from .review_site import review_site_summary
from .reviewer_packet import reviewer_packet_summary
from .reproduction_protocol import protocol_summary
from .scorecard import scorecard_summary
from .review_action_plan import review_action_plan_summary
from .timeline import project_timeline_summary
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
    candidate_review_count: int
    experiment_scaffold_count: int
    experiment_template_counts: dict[str, int]
    experiment_missing_required_input_count: int
    experiment_expected_artifacts_attention_count: int
    experiment_spec_status_counts: dict[str, int]
    experiment_spec_stale_count: int
    experiment_spec_invalid_count: int
    experiment_spec_missing_count: int
    data_registered_count: int
    data_invalid_count: int
    data_missing_count: int
    data_hash_mismatch_count: int
    experiment_run_count: int
    latest_quality_gate_status: str
    latest_quality_gate_failed_check_count: int | None
    latest_experiment_quality_gate_status: str
    latest_experiment_quality_gate_failed_check_count: int | None
    claim_trace_exists: bool
    claim_trace_claim_count: int
    claim_trace_validation_status: str
    claim_trace_validation_issue_count: int
    scorecard_exists: bool
    scorecard_overall_score: float
    scorecard_status: str
    gaps_exists: bool
    gaps_open_count: int
    gaps_status: str
    checkpoint_exists: bool
    checkpoint_status: str
    checkpoint_next_checkpoint: str | None
    advance_exists: bool
    advance_status: str
    advance_action_count: int
    advance_top_command: str | None
    review_board_exists: bool
    review_board_status: str
    review_board_item_count: int
    review_board_top_command: str | None
    review_decisions_exists: bool
    review_decision_status: str
    review_decision_count: int
    review_decision_closed_count: int
    review_decision_unresolved_item_count: int
    review_decision_top_command: str | None
    protocol_exists: bool
    protocol_status: str
    protocol_criterion_count: int
    protocol_blocking_criterion_count: int
    protocol_top_command: str | None
    protocol_coverage_exists: bool
    protocol_coverage_status: str
    protocol_coverage_score: float
    protocol_coverage_uncovered_count: int
    protocol_coverage_top_command: str | None
    protocol_plan_exists: bool
    protocol_plan_status: str
    protocol_plan_action_count: int
    protocol_plan_top_command: str | None
    protocol_preflight_exists: bool
    protocol_preflight_status: str
    protocol_preflight_check_count: int
    protocol_preflight_blocking_count: int
    protocol_preflight_warning_count: int
    protocol_preflight_top_command: str | None
    claim_evidence_binder_exists: bool
    claim_evidence_binder_status: str
    claim_evidence_binder_claim_count: int
    claim_evidence_binder_incomplete_claim_count: int
    claim_evidence_binder_top_command: str | None
    claim_evidence_binder_validation_exists: bool
    claim_evidence_binder_validation_status: str
    claim_evidence_binder_validation_issue_count: int
    claim_evidence_binder_validation_top_command: str | None
    claim_signoff_exists: bool
    claim_signoff_status: str
    claim_signoff_signed_claim_count: int
    claim_signoff_open_claim_count: int
    claim_signoff_top_command: str | None
    claim_signoff_validation_exists: bool
    claim_signoff_validation_status: str
    claim_signoff_validation_issue_count: int
    claim_signoff_validation_top_command: str | None
    claim_evidence_report_exists: bool
    claim_evidence_report_status: str
    claim_evidence_report_open_action_count: int
    claim_evidence_report_top_command: str | None
    claim_evidence_report_validation_exists: bool
    claim_evidence_report_validation_status: str
    claim_evidence_report_validation_issue_count: int
    claim_evidence_report_validation_top_command: str | None
    reviewer_packet_exists: bool
    reviewer_packet_status: str
    reviewer_packet_open_action_count: int
    reviewer_packet_validation_issue_count: int
    reviewer_packet_top_command: str | None
    review_site_exists: bool
    review_site_status: str
    review_site_open_action_count: int
    review_site_blocker_count: int
    review_site_top_command: str | None
    project_timeline_exists: bool
    project_timeline_status: str
    project_timeline_event_count: int
    project_timeline_human_decision_count: int
    project_timeline_latest_event_title: str | None
    collaboration_pack_exists: bool
    collaboration_pack_status: str
    collaboration_pack_unresolved_decision_count: int
    collaboration_pack_next_safe_command_count: int
    collaboration_pack_top_command: str | None
    refresh_run_exists: bool
    refresh_run_status: str
    refresh_run_step_count: int
    refresh_run_failed_step_count: int
    refresh_run_top_failed_step: str | None
    refresh_run_top_command: str | None
    artifact_freshness_exists: bool
    artifact_freshness_status: str
    artifact_freshness_stale_node_count: int
    artifact_freshness_top_stale_node: str | None
    artifact_freshness_top_stale_reason: str | None
    artifact_freshness_top_command: str | None
    dashboard_exists: bool
    dashboard_status: str
    dashboard_top_command: str | None
    dashboard_readiness_score: float | None
    dashboard_stale_node_count: int
    project_profile_exists: bool
    project_profile_status: str
    project_profile_target_claim_count: int
    project_profile_required_data_count: int
    project_profile_required_experiment_count: int
    project_profile_acceptance_dimension_count: int
    project_profile_top_command: str | None
    acceptance_criteria_exists: bool
    acceptance_criteria_status: str
    acceptance_criteria_count: int
    acceptance_criteria_passed_count: int
    acceptance_criteria_needs_work_count: int
    acceptance_criteria_top_command: str | None
    readiness_review_exists: bool
    readiness_review_status: str
    readiness_review_check_count: int
    readiness_review_blocker_count: int
    readiness_review_open_action_count: int
    readiness_review_top_command: str | None
    readiness_review_validation_exists: bool
    readiness_review_validation_status: str
    readiness_review_validation_issue_count: int
    readiness_review_validation_warning_count: int
    readiness_review_validation_top_command: str | None
    review_action_plan_exists: bool
    review_action_plan_status: str
    review_action_plan_action_count: int
    review_action_plan_open_action_count: int
    review_action_plan_top_command: str | None
    review_action_plan_top_role: str | None
    latest_run_dir: str | None
    lineage_exists: bool
    report_exists: bool
    handoff_complete: bool
    evidence_package_exists: bool
    evidence_package_status: str
    evidence_package_stale: bool
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


def _candidate_count(project_dir: Path, filename: str) -> int:
    data = read_json(project_dir / "workspace" / filename, default={}) or {}
    return len(data.get("candidates", [])) if isinstance(data, dict) else 0


def _verified_candidate_count(project_dir: Path) -> int:
    data = read_json(project_dir / "workspace" / "verified_candidates.json", default={}) or {}
    if not isinstance(data, dict):
        return 0
    return int(data.get("formula_candidate_count", 0) or 0) + int(data.get("parameter_candidate_count", 0) or 0)


def _candidate_review_count(project_dir: Path) -> int:
    data = read_json(project_dir / "workspace" / "candidate_reviews.json", default={}) or {}
    reviews = data.get("reviews", []) if isinstance(data, dict) else []
    return len(reviews)


def _experiment_run_count(project_dir: Path) -> int:
    outputs = project_dir / "outputs"
    if not outputs.exists():
        return 0
    count = 0
    for run_dir in outputs.iterdir():
        manifest = read_json(run_dir / "manifest.json", default={}) or {}
        if isinstance(manifest, dict) and manifest.get("command") == "run-experiment":
            count += 1
    return count


def _has_experiment_scaffold(project_dir: Path) -> bool:
    experiments = project_dir / "experiments"
    return experiments.exists() and any(path.is_dir() for path in experiments.iterdir())


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
            candidate_review_count=0,
            experiment_scaffold_count=0,
            experiment_template_counts={},
            experiment_missing_required_input_count=0,
            experiment_expected_artifacts_attention_count=0,
            experiment_spec_status_counts={},
            experiment_spec_stale_count=0,
            experiment_spec_invalid_count=0,
            experiment_spec_missing_count=0,
            data_registered_count=0,
            data_invalid_count=0,
            data_missing_count=0,
            data_hash_mismatch_count=0,
            experiment_run_count=0,
            latest_quality_gate_status="missing",
            latest_quality_gate_failed_check_count=None,
            latest_experiment_quality_gate_status="missing",
            latest_experiment_quality_gate_failed_check_count=None,
            claim_trace_exists=False,
            claim_trace_claim_count=0,
            claim_trace_validation_status="missing",
            claim_trace_validation_issue_count=0,
            scorecard_exists=False,
            scorecard_overall_score=0.0,
            scorecard_status="missing",
            gaps_exists=False,
            gaps_open_count=0,
            gaps_status="missing",
            checkpoint_exists=False,
            checkpoint_status="missing",
            checkpoint_next_checkpoint=None,
            advance_exists=False,
            advance_status="missing",
            advance_action_count=0,
            advance_top_command=None,
            review_board_exists=False,
            review_board_status="missing",
            review_board_item_count=0,
            review_board_top_command=None,
            review_decisions_exists=False,
            review_decision_status="missing",
            review_decision_count=0,
            review_decision_closed_count=0,
            review_decision_unresolved_item_count=0,
            review_decision_top_command=None,
            protocol_exists=False,
            protocol_status="missing",
            protocol_criterion_count=0,
            protocol_blocking_criterion_count=0,
            protocol_top_command=None,
            protocol_coverage_exists=False,
            protocol_coverage_status="missing",
            protocol_coverage_score=0.0,
            protocol_coverage_uncovered_count=0,
            protocol_coverage_top_command=None,
            protocol_plan_exists=False,
            protocol_plan_status="missing",
            protocol_plan_action_count=0,
            protocol_plan_top_command=None,
            protocol_preflight_exists=False,
            protocol_preflight_status="missing",
            protocol_preflight_check_count=0,
            protocol_preflight_blocking_count=0,
            protocol_preflight_warning_count=0,
            protocol_preflight_top_command=None,
            claim_evidence_binder_exists=False,
            claim_evidence_binder_status="missing",
            claim_evidence_binder_claim_count=0,
            claim_evidence_binder_incomplete_claim_count=0,
            claim_evidence_binder_top_command=None,
            claim_evidence_binder_validation_exists=False,
            claim_evidence_binder_validation_status="missing",
            claim_evidence_binder_validation_issue_count=0,
            claim_evidence_binder_validation_top_command=None,
            claim_signoff_exists=False,
            claim_signoff_status="missing",
            claim_signoff_signed_claim_count=0,
            claim_signoff_open_claim_count=0,
            claim_signoff_top_command=None,
            claim_signoff_validation_exists=False,
            claim_signoff_validation_status="missing",
            claim_signoff_validation_issue_count=0,
            claim_signoff_validation_top_command=None,
            claim_evidence_report_exists=False,
            claim_evidence_report_status="missing",
            claim_evidence_report_open_action_count=0,
            claim_evidence_report_top_command=None,
            claim_evidence_report_validation_exists=False,
            claim_evidence_report_validation_status="missing",
            claim_evidence_report_validation_issue_count=0,
            claim_evidence_report_validation_top_command=None,
            reviewer_packet_exists=False,
            reviewer_packet_status="missing",
            reviewer_packet_open_action_count=0,
            reviewer_packet_validation_issue_count=0,
            reviewer_packet_top_command=None,
            review_site_exists=False,
            review_site_status="missing",
            review_site_open_action_count=0,
            review_site_blocker_count=0,
            review_site_top_command=None,
            project_timeline_exists=False,
            project_timeline_status="missing",
            project_timeline_event_count=0,
            project_timeline_human_decision_count=0,
            project_timeline_latest_event_title=None,
            collaboration_pack_exists=False,
            collaboration_pack_status="missing",
            collaboration_pack_unresolved_decision_count=0,
            collaboration_pack_next_safe_command_count=0,
            collaboration_pack_top_command=None,
            refresh_run_exists=False,
            refresh_run_status="missing",
            refresh_run_step_count=0,
            refresh_run_failed_step_count=0,
            refresh_run_top_failed_step=None,
            refresh_run_top_command=None,
            artifact_freshness_exists=False,
            artifact_freshness_status="missing",
            artifact_freshness_stale_node_count=0,
            artifact_freshness_top_stale_node=None,
            artifact_freshness_top_stale_reason=None,
            artifact_freshness_top_command=None,
            dashboard_exists=False,
            dashboard_status="missing",
            dashboard_top_command=None,
            dashboard_readiness_score=None,
            dashboard_stale_node_count=0,
            project_profile_exists=False,
            project_profile_status="missing",
            project_profile_target_claim_count=0,
            project_profile_required_data_count=0,
            project_profile_required_experiment_count=0,
            project_profile_acceptance_dimension_count=0,
            project_profile_top_command=None,
            acceptance_criteria_exists=False,
            acceptance_criteria_status="missing",
            acceptance_criteria_count=0,
            acceptance_criteria_passed_count=0,
            acceptance_criteria_needs_work_count=0,
            acceptance_criteria_top_command=None,
            readiness_review_exists=False,
            readiness_review_status="missing",
            readiness_review_check_count=0,
            readiness_review_blocker_count=0,
            readiness_review_open_action_count=0,
            readiness_review_top_command=None,
            readiness_review_validation_exists=False,
            readiness_review_validation_status="missing",
            readiness_review_validation_issue_count=0,
            readiness_review_validation_warning_count=0,
            readiness_review_validation_top_command=None,
            review_action_plan_exists=False,
            review_action_plan_status="missing",
            review_action_plan_action_count=0,
            review_action_plan_open_action_count=0,
            review_action_plan_top_command=None,
            review_action_plan_top_role=None,
            latest_run_dir=None,
            lineage_exists=False,
            report_exists=False,
            handoff_complete=False,
            evidence_package_exists=False,
            evidence_package_status="missing",
            evidence_package_stale=True,
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
    candidate_count = _candidate_count(project_dir, "formula_candidates.json") + _candidate_count(
        project_dir,
        "parameter_candidates.json",
    )
    verified_candidate_count = _verified_candidate_count(project_dir)
    candidate_review_count = _candidate_review_count(project_dir)
    scaffold_summary = inspect_experiment_scaffolds(project_dir)
    spec_summary = inspect_experiment_specs(project_dir)
    data_summary = data_index_summary(project_dir)
    experiment_run_count = _experiment_run_count(project_dir)
    has_experiment_scaffold = _has_experiment_scaffold(project_dir)
    latest = latest_run_dir(project_dir)
    quality_gate = latest_quality_gate_summary(project_dir)
    experiment_quality_gate = latest_experiment_quality_gate_summary(project_dir)
    trace_summary = claim_trace_summary(project_dir)
    scorecard = scorecard_summary(project_dir)
    gaps = gaps_summary(project_dir)
    checkpoints = checkpoint_summary(project_dir)
    advance = advance_summary(project_dir)
    review_board = review_board_summary(project_dir)
    review_decisions = review_decision_summary(project_dir)
    protocol = protocol_summary(project_dir)
    protocol_coverage = protocol_coverage_summary(project_dir)
    protocol_plan = protocol_plan_summary(project_dir)
    protocol_preflight = protocol_preflight_summary(project_dir)
    claim_binder = claim_evidence_binder_summary(project_dir)
    binder_validation = claim_evidence_binder_validation_summary(project_dir)
    claim_signoff = claim_signoff_summary(project_dir)
    claim_signoff_validation = claim_signoff_validation_summary(project_dir)
    claim_evidence_report = claim_evidence_report_summary(project_dir)
    claim_evidence_report_validation = claim_evidence_report_validation_summary(project_dir)
    reviewer_packet = reviewer_packet_summary(project_dir)
    review_site = review_site_summary(project_dir)
    project_timeline = project_timeline_summary(project_dir)
    collaboration_pack = collaboration_pack_summary(project_dir)
    refresh_run = refresh_run_summary(project_dir)
    artifact_freshness = artifact_freshness_summary(project_dir)
    dashboard = dashboard_summary(project_dir)
    project_profile = project_profile_summary(project_dir)
    acceptance = acceptance_criteria_summary(project_dir)
    readiness_review = readiness_review_summary(project_dir)
    readiness_review_validation = readiness_review_validation_summary(project_dir)
    review_action_plan = review_action_plan_summary(project_dir)
    lineage_exists = (project_dir / "workspace" / "run_lineage.json").exists()
    report_exists = (project_dir / "reports" / "report.md").exists()
    handoff_complete = all((project_dir / "handoff" / name).exists() for name in required_handoff_files())
    evidence_package_exists = (project_dir / "reports" / "evidence_package.json").exists() and (
        project_dir / "reports" / "evidence_package.md"
    ).exists()
    evidence_status = evidence_package_status(project_dir)

    if not ingested:
        next_step = f"Run: openrepro ingest {project_dir} --source <markdown_or_txt>"
    elif not analyzed:
        next_step = f"Run: openrepro analyze {project_dir}"
    elif not planned:
        next_step = f"Run: openrepro plan {project_dir}"
    elif candidate_count > 0 and candidate_review_count == 0 and verified_candidate_count == 0:
        next_step = f"Run: openrepro list-candidates {project_dir}"
    elif candidate_count > 0 and verified_candidate_count == 0:
        next_step = f"Run: openrepro review-candidates {project_dir} --candidate-id <id> --status verified_by_human --reviewer <name>"
    elif not has_experiment_scaffold:
        next_step = f"Run: openrepro scaffold-experiment {project_dir} --experiment-id <id>"
    elif scaffold_summary["expected_artifacts_attention_count"] > 0:
        next_step = f"Run: openrepro inspect {project_dir}"
    elif spec_summary["invalid_count"] > 0 or spec_summary["missing_count"] > 0:
        next_step = f"Run: openrepro validate-experiment-spec {project_dir} --experiment-id <id>"
    elif spec_summary["stale_count"] > 0:
        next_step = f"Run: openrepro validate-experiment-spec {project_dir} --experiment-id <id>"
    elif data_summary["invalid_count"] > 0:
        next_step = f"Run: openrepro validate-data {project_dir}"
    elif experiment_run_count == 0:
        next_step = f"Run: openrepro run-experiment {project_dir} --experiment-id <id> --confirm"
    elif latest is None:
        next_step = f"Run: openrepro run-demo {project_dir}"
    elif experiment_quality_gate["status"] in {"missing", "failed"}:
        run_arg = f" --run-dir {experiment_quality_gate['run_dir']}" if experiment_quality_gate.get("run_dir") else ""
        next_step = f"Run: openrepro quality-gate {project_dir}{run_arg}"
    elif quality_gate["status"] in {"missing", "failed"}:
        next_step = f"Run: openrepro quality-gate {project_dir}"
    elif not lineage_exists:
        next_step = f"Run: openrepro lineage {project_dir}"
    elif not trace_summary["present"]:
        next_step = f"Run: openrepro trace-claims {project_dir}"
    elif trace_summary["validation_status"] != "passed":
        next_step = f"Run: openrepro validate-claims {project_dir}"
    elif not scorecard["present"]:
        next_step = f"Run: openrepro scorecard {project_dir}"
    elif not gaps["present"]:
        next_step = f"Run: openrepro gaps {project_dir}"
    elif gaps["open_count"] > 0:
        command = str(gaps["top_suggested_command"] or f"openrepro gaps {project_dir}")
        next_step = f"Run: {command}"
    elif not checkpoints["present"]:
        next_step = f"Run: openrepro checkpoints {project_dir}"
    elif not advance["present"]:
        next_step = f"Run: openrepro advance {project_dir} --dry-run"
    elif not review_board["present"]:
        next_step = f"Run: openrepro review-board {project_dir}"
    elif review_board["item_count"] > 0 and review_decisions["unresolved_item_count"] > 0:
        command = str(review_decisions["top_command"] or f"openrepro review-decision {project_dir} --item-id <item_id> --decision needs_followup --reviewer <name>")
        next_step = f"Run: {command}"
    elif not protocol["present"]:
        next_step = f"Run: openrepro protocol {project_dir}"
    elif protocol["blocking_criterion_count"] > 0:
        command = str(protocol["top_command"] or f"openrepro protocol {project_dir}")
        next_step = f"Run: {command}"
    elif not protocol_coverage["present"]:
        next_step = f"Run: openrepro protocol-coverage {project_dir}"
    elif not protocol_plan["present"]:
        next_step = f"Run: openrepro protocol-plan {project_dir}"
    elif protocol_plan["action_count"] > 0:
        command = str(protocol_plan["top_command"] or f"openrepro protocol-plan {project_dir}")
        next_step = f"Run: {command}"
    elif not protocol_preflight["present"]:
        next_step = f"Run: openrepro protocol-preflight {project_dir}"
    elif protocol_preflight["blocking_count"] > 0:
        command = str(protocol_preflight["top_command"] or f"openrepro protocol-preflight {project_dir}")
        next_step = f"Run: {command}"
    elif not claim_binder["present"]:
        next_step = f"Run: openrepro evidence-binder {project_dir}"
    elif claim_binder["incomplete_claim_count"] > 0:
        command = str(claim_binder["top_command"] or f"openrepro evidence-binder {project_dir}")
        next_step = f"Run: {command}"
    elif not binder_validation["present"]:
        next_step = f"Run: openrepro validate-evidence-binder {project_dir}"
    elif binder_validation["status"] != "passed":
        command = str(binder_validation["top_command"] or f"openrepro evidence-binder {project_dir}")
        next_step = f"Run: {command}"
    elif not claim_signoff["present"]:
        command = str(claim_signoff["top_command"] or f"openrepro claim-signoff {project_dir}")
        next_step = f"Run: {command}"
    elif claim_signoff["open_claim_count"] > 0:
        command = str(claim_signoff["top_command"] or f"openrepro claim-signoff {project_dir}")
        next_step = f"Run: {command}"
    elif not claim_signoff_validation["present"]:
        next_step = f"Run: openrepro validate-claim-signoffs {project_dir}"
    elif claim_signoff_validation["status"] != "passed":
        command = str(claim_signoff_validation["top_command"] or f"openrepro validate-claim-signoffs {project_dir}")
        next_step = f"Run: {command}"
    elif not claim_evidence_report["present"]:
        next_step = f"Run: openrepro claim-evidence-report {project_dir}"
    elif claim_evidence_report["status"] != "ready":
        command = str(claim_evidence_report["top_command"] or f"openrepro claim-evidence-report {project_dir}")
        next_step = f"Run: {command}"
    elif not claim_evidence_report_validation["present"]:
        next_step = f"Run: openrepro validate-claim-evidence-report {project_dir}"
    elif claim_evidence_report_validation["status"] != "passed":
        command = str(claim_evidence_report_validation["top_command"] or f"openrepro validate-claim-evidence-report {project_dir}")
        next_step = f"Run: {command}"
    elif not reviewer_packet["present"]:
        next_step = f"Run: openrepro reviewer-packet {project_dir}"
    elif reviewer_packet["status"] != "ready":
        command = str(reviewer_packet["top_command"] or f"openrepro reviewer-packet {project_dir}")
        next_step = f"Run: {command}"
    elif not project_timeline["present"]:
        next_step = f"Run: openrepro timeline {project_dir}"
    elif project_timeline["status"] != "ready":
        next_step = f"Run: openrepro timeline {project_dir}"
    elif not project_profile["present"]:
        next_step = f"Run: openrepro profile {project_dir}"
    elif project_profile["status"] not in {"ready", "ready_with_open_work"}:
        command = str(project_profile["top_command"] or f"openrepro profile {project_dir}")
        next_step = f"Run: {command}"
    elif not acceptance["present"]:
        next_step = f"Run: openrepro acceptance {project_dir}"
    elif acceptance["status"] != "ready":
        command = str(acceptance["top_command"] or f"openrepro acceptance {project_dir}")
        next_step = f"Run: {command}"
    elif not report_exists:
        next_step = f"Run: openrepro report {project_dir}"
    elif not handoff_complete:
        next_step = f"Run: openrepro handoff {project_dir}"
    elif not evidence_package_exists:
        next_step = f"Run: openrepro evidence-package {project_dir}"
    elif evidence_status["stale"]:
        next_step = f"Run: openrepro evidence-package {project_dir} --zip"
    elif not review_site["present"]:
        next_step = f"Run: openrepro review-site {project_dir} --zip"
    elif review_site["status"] != "ready":
        command = str(review_site["top_command"] or f"openrepro review-site {project_dir} --zip")
        next_step = f"Run: {command}"
    elif not collaboration_pack["present"]:
        next_step = f"Run: openrepro collaboration-pack {project_dir} --zip"
    elif collaboration_pack["status"] != "ready":
        command = str(collaboration_pack["top_command"] or f"openrepro collaboration-pack {project_dir} --zip")
        next_step = f"Run: {command}"
    elif not refresh_run["present"]:
        next_step = f"Run: openrepro refresh {project_dir} --zip"
    elif refresh_run["status"] != "complete":
        command = str(refresh_run["top_command"] or f"openrepro refresh {project_dir} --zip")
        next_step = f"Run: {command}"
    elif not artifact_freshness["present"]:
        next_step = f"Run: openrepro freshness {project_dir}"
    elif artifact_freshness["status"] != "current":
        command = str(artifact_freshness["top_command"] or f"openrepro freshness {project_dir}")
        next_step = f"Run: {command}"
    elif not dashboard["present"]:
        next_step = f"Run: openrepro dashboard {project_dir} --zip"
    elif dashboard["status"] != "ready":
        command = str(dashboard["top_command"] or f"openrepro dashboard {project_dir} --zip")
        next_step = f"Run: {command}"
    elif not readiness_review["present"]:
        next_step = f"Run: openrepro readiness-review {project_dir} --zip"
    elif readiness_review["status"] != "ready_for_human_review":
        command = str(readiness_review["top_command"] or f"openrepro readiness-review {project_dir} --zip")
        next_step = f"Run: {command}"
    elif not readiness_review_validation["present"]:
        next_step = f"Run: openrepro validate-readiness-review {project_dir}"
    elif readiness_review_validation["status"] != "passed":
        command = str(readiness_review_validation["top_command"] or f"openrepro validate-readiness-review {project_dir}")
        next_step = f"Run: {command}"
    elif not review_action_plan["present"]:
        next_step = f"Run: openrepro review-action-plan {project_dir}"
    elif review_action_plan["status"] not in {"complete", "ready"}:
        command = str(review_action_plan["top_command"] or f"openrepro review-action-plan {project_dir}")
        next_step = f"Run: {command}"
    else:
        next_step = "Project v1.22.0 workflow is complete. Review the role-based action plan, validated readiness review, acceptance criteria, project profile, static dashboard, artifact freshness graph, refresh run, collaboration pack, project timeline, static review site, reviewer packet, validated claim evidence reports, validated claim signoffs, the validated claim evidence binder, protocol preflight, protocol action plan, protocol coverage, reproduction protocol, human review decisions, review board, advance dry-run plan, workflow checkpoints, reproduction gaps, the readiness scorecard, validated claim traceability, quality gate repair plans, batch quality gates, registered data provenance, fresh experiment specs, section-aware paper evidence, caption indexes, high-risk candidates, the fresh evidence package, experiment comparisons, repeat lineage, calibrated inputs, environment snapshots, templates, runs, reports, and handoff files."

    return ProjectStatus(
        project_name=detected_name,
        project_dir=str(project_dir),
        exists=exists,
        initialized=initialized,
        ingested=ingested,
        analyzed=analyzed,
        planned=planned,
        candidate_review_count=candidate_review_count,
        experiment_scaffold_count=scaffold_summary["scaffold_count"],
        experiment_template_counts=scaffold_summary["template_counts"],
        experiment_missing_required_input_count=scaffold_summary["missing_required_input_count"],
        experiment_expected_artifacts_attention_count=scaffold_summary["expected_artifacts_attention_count"],
        experiment_spec_status_counts=spec_summary["status_counts"],
        experiment_spec_stale_count=spec_summary["stale_count"],
        experiment_spec_invalid_count=spec_summary["invalid_count"],
        experiment_spec_missing_count=spec_summary["missing_count"],
        data_registered_count=data_summary["registered_count"],
        data_invalid_count=data_summary["invalid_count"],
        data_missing_count=data_summary["missing_count"],
        data_hash_mismatch_count=data_summary["hash_mismatch_count"],
        experiment_run_count=experiment_run_count,
        latest_quality_gate_status=str(quality_gate["status"]),
        latest_quality_gate_failed_check_count=quality_gate["failed_check_count"],
        latest_experiment_quality_gate_status=str(experiment_quality_gate["status"]),
        latest_experiment_quality_gate_failed_check_count=experiment_quality_gate["failed_check_count"],
        claim_trace_exists=bool(trace_summary["present"]),
        claim_trace_claim_count=trace_summary["claim_count"],
        claim_trace_validation_status=str(trace_summary["validation_status"]),
        claim_trace_validation_issue_count=trace_summary["validation_issue_count"],
        scorecard_exists=bool(scorecard["present"]),
        scorecard_overall_score=float(scorecard["overall_score"]),
        scorecard_status=str(scorecard["overall_status"]),
        gaps_exists=bool(gaps["present"]),
        gaps_open_count=gaps["open_count"],
        gaps_status=str(gaps["status"]),
        checkpoint_exists=bool(checkpoints["present"]),
        checkpoint_status=str(checkpoints["status"]),
        checkpoint_next_checkpoint=checkpoints["next_checkpoint"],
        advance_exists=bool(advance["present"]),
        advance_status=str(advance["status"]),
        advance_action_count=advance["action_count"],
        advance_top_command=advance["top_command"],
        review_board_exists=bool(review_board["present"]),
        review_board_status=str(review_board["status"]),
        review_board_item_count=review_board["item_count"],
        review_board_top_command=review_board["top_command"],
        review_decisions_exists=bool(review_decisions["present"]),
        review_decision_status=str(review_decisions["status"]),
        review_decision_count=review_decisions["decision_count"],
        review_decision_closed_count=review_decisions["closed_count"],
        review_decision_unresolved_item_count=review_decisions["unresolved_item_count"],
        review_decision_top_command=review_decisions["top_command"],
        protocol_exists=bool(protocol["present"]),
        protocol_status=str(protocol["status"]),
        protocol_criterion_count=protocol["criterion_count"],
        protocol_blocking_criterion_count=protocol["blocking_criterion_count"],
        protocol_top_command=protocol["top_command"],
        protocol_coverage_exists=bool(protocol_coverage["present"]),
        protocol_coverage_status=str(protocol_coverage["status"]),
        protocol_coverage_score=protocol_coverage["coverage_score"],
        protocol_coverage_uncovered_count=protocol_coverage["uncovered_count"],
        protocol_coverage_top_command=protocol_coverage["top_command"],
        protocol_plan_exists=bool(protocol_plan["present"]),
        protocol_plan_status=str(protocol_plan["status"]),
        protocol_plan_action_count=protocol_plan["action_count"],
        protocol_plan_top_command=protocol_plan["top_command"],
        protocol_preflight_exists=bool(protocol_preflight["present"]),
        protocol_preflight_status=str(protocol_preflight["status"]),
        protocol_preflight_check_count=protocol_preflight["check_count"],
        protocol_preflight_blocking_count=protocol_preflight["blocking_count"],
        protocol_preflight_warning_count=protocol_preflight["warning_count"],
        protocol_preflight_top_command=protocol_preflight["top_command"],
        claim_evidence_binder_exists=bool(claim_binder["present"]),
        claim_evidence_binder_status=str(claim_binder["status"]),
        claim_evidence_binder_claim_count=claim_binder["claim_count"],
        claim_evidence_binder_incomplete_claim_count=claim_binder["incomplete_claim_count"],
        claim_evidence_binder_top_command=claim_binder["top_command"],
        claim_evidence_binder_validation_exists=bool(binder_validation["present"]),
        claim_evidence_binder_validation_status=str(binder_validation["status"]),
        claim_evidence_binder_validation_issue_count=binder_validation["issue_count"],
        claim_evidence_binder_validation_top_command=binder_validation["top_command"],
        claim_signoff_exists=bool(claim_signoff["present"]),
        claim_signoff_status=str(claim_signoff["status"]),
        claim_signoff_signed_claim_count=claim_signoff["signed_claim_count"],
        claim_signoff_open_claim_count=claim_signoff["open_claim_count"],
        claim_signoff_top_command=claim_signoff["top_command"],
        claim_signoff_validation_exists=bool(claim_signoff_validation["present"]),
        claim_signoff_validation_status=str(claim_signoff_validation["status"]),
        claim_signoff_validation_issue_count=claim_signoff_validation["issue_count"],
        claim_signoff_validation_top_command=claim_signoff_validation["top_command"],
        claim_evidence_report_exists=bool(claim_evidence_report["present"]),
        claim_evidence_report_status=str(claim_evidence_report["status"]),
        claim_evidence_report_open_action_count=claim_evidence_report["open_action_count"],
        claim_evidence_report_top_command=claim_evidence_report["top_command"],
        claim_evidence_report_validation_exists=bool(claim_evidence_report_validation["present"]),
        claim_evidence_report_validation_status=str(claim_evidence_report_validation["status"]),
        claim_evidence_report_validation_issue_count=claim_evidence_report_validation["issue_count"],
        claim_evidence_report_validation_top_command=claim_evidence_report_validation["top_command"],
        reviewer_packet_exists=bool(reviewer_packet["present"]),
        reviewer_packet_status=str(reviewer_packet["status"]),
        reviewer_packet_open_action_count=reviewer_packet["open_action_count"],
        reviewer_packet_validation_issue_count=reviewer_packet["validation_issue_count"],
        reviewer_packet_top_command=reviewer_packet["top_command"],
        review_site_exists=bool(review_site["present"]),
        review_site_status=str(review_site["status"]),
        review_site_open_action_count=review_site["open_action_count"],
        review_site_blocker_count=review_site["blocker_count"],
        review_site_top_command=review_site["top_command"],
        project_timeline_exists=bool(project_timeline["present"]),
        project_timeline_status=str(project_timeline["status"]),
        project_timeline_event_count=project_timeline["event_count"],
        project_timeline_human_decision_count=project_timeline["human_decision_count"],
        project_timeline_latest_event_title=project_timeline["latest_event_title"],
        collaboration_pack_exists=bool(collaboration_pack["present"]),
        collaboration_pack_status=str(collaboration_pack["status"]),
        collaboration_pack_unresolved_decision_count=collaboration_pack["unresolved_decision_count"],
        collaboration_pack_next_safe_command_count=collaboration_pack["next_safe_command_count"],
        collaboration_pack_top_command=collaboration_pack["top_command"],
        refresh_run_exists=bool(refresh_run["present"]),
        refresh_run_status=str(refresh_run["status"]),
        refresh_run_step_count=refresh_run["step_count"],
        refresh_run_failed_step_count=refresh_run["failed_step_count"],
        refresh_run_top_failed_step=refresh_run["top_failed_step"],
        refresh_run_top_command=refresh_run["top_command"],
        artifact_freshness_exists=bool(artifact_freshness["present"]),
        artifact_freshness_status=str(artifact_freshness["status"]),
        artifact_freshness_stale_node_count=artifact_freshness["stale_node_count"],
        artifact_freshness_top_stale_node=artifact_freshness["top_stale_node"],
        artifact_freshness_top_stale_reason=artifact_freshness["top_stale_reason"],
        artifact_freshness_top_command=artifact_freshness["top_command"],
        dashboard_exists=bool(dashboard["present"]),
        dashboard_status=str(dashboard["status"]),
        dashboard_top_command=dashboard["top_command"],
        dashboard_readiness_score=dashboard["readiness_score"],
        dashboard_stale_node_count=int(dashboard["stale_node_count"] or 0),
        project_profile_exists=bool(project_profile["present"]),
        project_profile_status=str(project_profile["status"]),
        project_profile_target_claim_count=int(project_profile["target_claim_count"] or 0),
        project_profile_required_data_count=int(project_profile["required_data_count"] or 0),
        project_profile_required_experiment_count=int(project_profile["required_experiment_count"] or 0),
        project_profile_acceptance_dimension_count=int(project_profile["acceptance_dimension_count"] or 0),
        project_profile_top_command=project_profile["top_command"],
        acceptance_criteria_exists=bool(acceptance["present"]),
        acceptance_criteria_status=str(acceptance["status"]),
        acceptance_criteria_count=int(acceptance["criteria_count"] or 0),
        acceptance_criteria_passed_count=int(acceptance["passed_count"] or 0),
        acceptance_criteria_needs_work_count=int(acceptance["needs_work_count"] or 0),
        acceptance_criteria_top_command=acceptance["top_command"],
        readiness_review_exists=bool(readiness_review["present"]),
        readiness_review_status=str(readiness_review["status"]),
        readiness_review_check_count=int(readiness_review["check_count"] or 0),
        readiness_review_blocker_count=int(readiness_review["blocker_count"] or 0),
        readiness_review_open_action_count=int(readiness_review["open_action_count"] or 0),
        readiness_review_top_command=readiness_review["top_command"],
        readiness_review_validation_exists=bool(readiness_review_validation["present"]),
        readiness_review_validation_status=str(readiness_review_validation["status"]),
        readiness_review_validation_issue_count=int(readiness_review_validation["issue_count"] or 0),
        readiness_review_validation_warning_count=int(readiness_review_validation["warning_count"] or 0),
        readiness_review_validation_top_command=readiness_review_validation["top_command"],
        review_action_plan_exists=bool(review_action_plan["present"]),
        review_action_plan_status=str(review_action_plan["status"]),
        review_action_plan_action_count=int(review_action_plan["action_count"] or 0),
        review_action_plan_open_action_count=int(review_action_plan["open_action_count"] or 0),
        review_action_plan_top_command=review_action_plan["top_command"],
        review_action_plan_top_role=review_action_plan["top_role"],
        latest_run_dir=str(latest) if latest else None,
        lineage_exists=lineage_exists,
        report_exists=report_exists,
        handoff_complete=handoff_complete,
        evidence_package_exists=evidence_package_exists,
        evidence_package_status=str(evidence_status["status"]),
        evidence_package_stale=bool(evidence_status["stale"]),
        next_step=next_step,
    )
