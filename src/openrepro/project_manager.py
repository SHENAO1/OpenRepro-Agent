"""Project initialization and status inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .artifact_manager import latest_run_dir, required_handoff_files
from .checkpoints import checkpoint_summary
from .claim_trace import claim_trace_summary
from .config import create_project_config, load_project_config, save_project_config
from .data_registry import data_index_summary
from .evidence_fingerprint import evidence_package_status
from .experiment_spec import inspect_experiment_specs
from .experiment_templates import inspect_experiment_scaffolds
from .gaps import gaps_summary
from .quality_gate import latest_experiment_quality_gate_summary, latest_quality_gate_summary
from .scorecard import scorecard_summary
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
    elif not report_exists:
        next_step = f"Run: openrepro report {project_dir}"
    elif not handoff_complete:
        next_step = f"Run: openrepro handoff {project_dir}"
    elif not evidence_package_exists:
        next_step = f"Run: openrepro evidence-package {project_dir}"
    elif evidence_status["stale"]:
        next_step = f"Run: openrepro evidence-package {project_dir} --zip"
    else:
        next_step = "Project v1.8.0 workflow is complete. Review workflow checkpoints, reproduction gaps, the readiness scorecard, validated claim traceability, quality gate repair plans, batch quality gates, registered data provenance, fresh experiment specs, section-aware paper evidence, caption indexes, high-risk candidates, the fresh evidence package, experiment comparisons, repeat lineage, calibrated inputs, environment snapshots, templates, runs, reports, and handoff files."

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
        latest_run_dir=str(latest) if latest else None,
        lineage_exists=lineage_exists,
        report_exists=report_exists,
        handoff_complete=handoff_complete,
        evidence_package_exists=evidence_package_exists,
        evidence_package_status=str(evidence_status["status"]),
        evidence_package_stale=bool(evidence_status["stale"]),
        next_step=next_step,
    )
