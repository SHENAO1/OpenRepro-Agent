"""Registered workflow DAG and safe step execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .utils import iso_now, read_json, safe_write_text, write_json

WORKFLOW_REGISTRY_SCHEMA_VERSION = "1.40.0"


@dataclass(frozen=True)
class WorkflowStep:
    """Static metadata for one workflow step."""

    step_id: str
    title: str
    stage: str
    description: str
    command: str
    outputs: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    safe: bool = True
    execution: str = "safe_derived"


WORKFLOW_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep(
        "init",
        "Initialize project",
        "setup",
        "Create the standard OpenRepro project layout and config.",
        "openrepro init <project>",
        ("project_config.yaml",),
        safe=False,
        execution="project_setup",
    ),
    WorkflowStep(
        "ingest",
        "Ingest sources",
        "paper",
        "Ingest Markdown, text, or PDF paper sources.",
        "openrepro ingest <project> --source <source>",
        ("workspace/source_index.json",),
        ("init",),
        safe=False,
        execution="requires_source_input",
    ),
    WorkflowStep(
        "analyze",
        "Analyze paper evidence",
        "paper",
        "Extract paper summary, formula candidates, parameter candidates, and metadata.",
        "openrepro analyze <project>",
        (
            "workspace/analysis_result.json",
            "workspace/formula_candidates.json",
            "workspace/parameter_candidates.json",
            "workspace/model_ledger.json",
        ),
        ("ingest",),
    ),
    WorkflowStep(
        "plan",
        "Generate experiment plan",
        "paper",
        "Create the initial experiment plan and plan validation artifacts.",
        "openrepro plan <project>",
        ("workspace/EXPERIMENT_PLAN.md", "workspace/experiment_plan_validation.json"),
        ("analyze",),
    ),
    WorkflowStep(
        "candidate_review",
        "Review candidates",
        "human_review",
        "Record human review decisions for formula and parameter candidates.",
        "openrepro review-candidates <project> --candidate-id <id> --status <status> --reviewer <name>",
        ("workspace/candidate_reviews.json",),
        ("analyze",),
        safe=False,
        execution="human_decision",
    ),
    WorkflowStep(
        "candidate_approval",
        "Approve candidates",
        "human_review",
        "Promote reviewed candidates into verified implementation inputs.",
        "openrepro approve-candidates <project> --all --reviewer <name>",
        ("workspace/verified_candidates.json",),
        ("candidate_review",),
        safe=False,
        execution="human_decision",
    ),
    WorkflowStep(
        "data_registry",
        "Register data",
        "data",
        "Register local data sources and provenance.",
        "openrepro register-data <project> --path <data> --role dataset",
        ("workspace/data_index.json",),
        ("init",),
        safe=False,
        execution="requires_data_input",
    ),
    WorkflowStep(
        "data_validation",
        "Validate data",
        "data",
        "Validate registered data presence and hashes.",
        "openrepro validate-data <project>",
        ("workspace/data_validation.json",),
        ("data_registry",),
    ),
    WorkflowStep(
        "data_profile",
        "Profile data",
        "data",
        "Profile registered data structure and lightweight schema warnings.",
        "openrepro data-profile <project>",
        ("workspace/data_profile.json", "workspace/DATA_PROFILE.md"),
        ("data_validation",),
    ),
    WorkflowStep(
        "data_expectations",
        "Data expectations",
        "data",
        "Run lightweight structural expectations for registered data.",
        "openrepro data-expectations run <project>",
        (
            "workspace/data_expectations.json",
            "workspace/DATA_EXPECTATIONS.md",
            "workspace/data_expectation_results.json",
            "workspace/DATA_EXPECTATION_RESULTS.md",
        ),
        ("data_profile",),
    ),
    WorkflowStep(
        "scaffold",
        "Scaffold experiment",
        "experiment",
        "Generate a human-gated experiment scaffold from verified inputs.",
        "openrepro scaffold-experiment <project> --experiment-id <id> --template <template>",
        ("experiments/*/runner.py", "experiments/*/experiment_spec.json"),
        ("candidate_approval",),
        safe=False,
        execution="code_generation",
    ),
    WorkflowStep(
        "inputs",
        "Validate inputs",
        "experiment",
        "Validate experiment input completeness.",
        "openrepro validate-inputs <project> --experiment-id <id>",
        ("workspace/experiment_input_validation.json",),
        ("scaffold",),
    ),
    WorkflowStep(
        "spec_validation",
        "Validate experiment specs",
        "experiment",
        "Validate experiment execution contracts.",
        "openrepro validate-experiment-spec <project> --experiment-id <id>",
        ("workspace/experiment_spec_validation.json",),
        ("scaffold",),
    ),
    WorkflowStep(
        "repro_lock",
        "Repro lock",
        "environment",
        "Lock registered data, project config, experiment contracts, and dependency versions.",
        "openrepro lock <project>",
        ("openrepro.lock.json", "workspace/REPRO_LOCK.md"),
        ("data_expectations", "spec_validation"),
    ),
    WorkflowStep(
        "repro_lock_validation",
        "Validate repro lock",
        "environment",
        "Validate the current project against the reproducibility lockfile.",
        "openrepro validate-lock <project>",
        ("workspace/repro_lock_validation.json", "workspace/REPRO_LOCK_VALIDATION.md"),
        ("repro_lock",),
    ),
    WorkflowStep(
        "run_experiment",
        "Run experiment",
        "execution",
        "Run a verified experiment scaffold with explicit confirmation.",
        "openrepro run-experiment <project> --experiment-id <id> --confirm",
        ("outputs/*/manifest.json",),
        ("inputs", "spec_validation", "data_validation", "repro_lock_validation"),
        safe=False,
        execution="runs_experiment",
    ),
    WorkflowStep(
        "quality_gates",
        "Evaluate quality gates",
        "evidence",
        "Evaluate quality gates for existing run evidence.",
        "openrepro quality-gate <project> --all",
        ("workspace/quality_gate_summary.json",),
        ("run_experiment",),
    ),
    WorkflowStep(
        "run_index",
        "Run index",
        "evidence",
        "Index run outputs, metrics, manifests, and quality gates.",
        "openrepro runs index <project>",
        ("workspace/run_index.json", "reports/run_explorer/index.html"),
        ("quality_gates",),
    ),
    WorkflowStep(
        "experiment_tracking",
        "Experiment tracking",
        "evidence",
        "Aggregate indexed runs into experiment-level tracking artifacts.",
        "openrepro experiments track <project>",
        ("workspace/experiment_tracking.json", "workspace/EXPERIMENT_TRACKING.md", "reports/experiments/index.html"),
        ("run_index",),
    ),
    WorkflowStep(
        "lineage",
        "Run lineage",
        "evidence",
        "Build run lineage hashes and repeat groups.",
        "openrepro lineage <project>",
        ("workspace/run_lineage.json",),
        ("experiment_tracking",),
    ),
    WorkflowStep(
        "claim_trace",
        "Trace claims",
        "claim_evidence",
        "Link claims to experiments, registered data, and runs.",
        "openrepro trace-claims <project>",
        ("workspace/claim_trace.json",),
        ("lineage",),
    ),
    WorkflowStep(
        "claim_trace_validation",
        "Validate claim trace",
        "claim_evidence",
        "Validate claim trace freshness and link integrity.",
        "openrepro validate-claims <project>",
        ("workspace/claim_trace_validation.json",),
        ("claim_trace",),
    ),
    WorkflowStep(
        "evidence_graph",
        "Evidence graph",
        "claim_evidence",
        "Build the unified claim, data, experiment, run, review, and artifact graph.",
        "openrepro evidence-graph <project>",
        ("workspace/evidence_graph.json", "workspace/EVIDENCE_GRAPH.md"),
        ("claim_trace_validation",),
    ),
    WorkflowStep(
        "scorecard",
        "Readiness scorecard",
        "review",
        "Score workflow evidence readiness.",
        "openrepro scorecard <project>",
        ("workspace/reproduction_scorecard.json",),
        ("evidence_graph",),
    ),
    WorkflowStep(
        "gaps",
        "Reproduction gaps",
        "review",
        "Convert evidence gaps into suggested next actions.",
        "openrepro gaps <project>",
        ("workspace/reproduction_gaps.json",),
        ("scorecard",),
    ),
    WorkflowStep(
        "checkpoints",
        "Workflow checkpoints",
        "review",
        "Normalize major workflow stage states.",
        "openrepro checkpoints <project>",
        ("workspace/workflow_checkpoints.json",),
        ("gaps",),
    ),
    WorkflowStep(
        "advance_plan",
        "Advance dry-run",
        "review",
        "Select the next safe command without executing it.",
        "openrepro advance <project> --dry-run",
        ("workspace/advance_plan.json",),
        ("checkpoints",),
    ),
    WorkflowStep(
        "review_board",
        "Review board",
        "review",
        "Build a consolidated human review board.",
        "openrepro review-board <project>",
        ("workspace/review_board.json",),
        ("advance_plan",),
    ),
    WorkflowStep(
        "review_decisions",
        "Review decisions",
        "human_review",
        "Record or summarize reviewer decisions.",
        "openrepro review-decision <project> --item-id <id> --decision <decision> --reviewer <name>",
        ("workspace/review_decisions.json",),
        ("review_board",),
        safe=False,
        execution="human_decision",
    ),
    WorkflowStep(
        "protocol",
        "Reproduction protocol",
        "protocol",
        "Generate an auditable reproduction protocol.",
        "openrepro protocol <project>",
        ("workspace/reproduction_protocol.json",),
        ("review_board",),
    ),
    WorkflowStep(
        "protocol_coverage",
        "Protocol coverage",
        "protocol",
        "Check protocol claim/data/experiment/run coverage.",
        "openrepro protocol-coverage <project>",
        ("workspace/protocol_coverage.json",),
        ("protocol",),
    ),
    WorkflowStep(
        "protocol_plan",
        "Protocol plan",
        "protocol",
        "Generate a protocol action plan.",
        "openrepro protocol-plan <project>",
        ("workspace/protocol_plan.json",),
        ("protocol_coverage",),
    ),
    WorkflowStep(
        "protocol_preflight",
        "Protocol preflight",
        "protocol",
        "Run protocol readiness preflight checks.",
        "openrepro protocol-preflight <project>",
        ("workspace/protocol_preflight.json",),
        ("protocol_plan",),
    ),
    WorkflowStep(
        "evidence_binder",
        "Claim evidence binder",
        "claim_evidence",
        "Bind each traced claim to workflow evidence.",
        "openrepro evidence-binder <project>",
        ("workspace/claim_evidence_binder.json",),
        ("protocol_preflight",),
    ),
    WorkflowStep(
        "evidence_binder_validation",
        "Validate evidence binder",
        "claim_evidence",
        "Validate binder freshness and consistency.",
        "openrepro validate-evidence-binder <project>",
        ("workspace/claim_evidence_binder_validation.json",),
        ("evidence_binder",),
    ),
    WorkflowStep(
        "claim_signoffs",
        "Claim signoff summary",
        "human_review",
        "Summarize claim signoffs without adding decisions.",
        "openrepro claim-signoff <project>",
        ("workspace/claim_signoffs.json",),
        ("evidence_binder_validation",),
    ),
    WorkflowStep(
        "claim_signoff_validation",
        "Validate claim signoffs",
        "human_review",
        "Validate claim signoff freshness and coverage.",
        "openrepro validate-claim-signoffs <project>",
        ("workspace/claim_signoff_validation.json",),
        ("claim_signoffs",),
    ),
    WorkflowStep(
        "claim_evidence_report",
        "Claim evidence report",
        "review",
        "Generate the reviewer-facing claim evidence matrix.",
        "openrepro claim-evidence-report <project>",
        ("reports/claim_evidence_report.json",),
        ("claim_signoff_validation",),
    ),
    WorkflowStep(
        "claim_evidence_report_validation",
        "Validate claim evidence report",
        "review",
        "Validate claim evidence report freshness.",
        "openrepro validate-claim-evidence-report <project>",
        ("reports/claim_evidence_report_validation.json",),
        ("claim_evidence_report",),
    ),
    WorkflowStep(
        "reviewer_packet",
        "Reviewer packet",
        "delivery",
        "Generate a reviewer packet for human claim evidence review.",
        "openrepro reviewer-packet <project>",
        ("reports/reviewer_packet.json",),
        ("claim_evidence_report_validation",),
    ),
    WorkflowStep(
        "timeline",
        "Project timeline",
        "delivery",
        "Generate a chronological project decision and evidence log.",
        "openrepro timeline <project>",
        ("workspace/project_timeline.json",),
        ("reviewer_packet",),
    ),
    WorkflowStep(
        "profile",
        "Project profile",
        "delivery",
        "Summarize reproduction scope and acceptance dimensions.",
        "openrepro profile <project>",
        ("workspace/project_profile.json",),
        ("timeline",),
    ),
    WorkflowStep(
        "acceptance",
        "Acceptance criteria",
        "delivery",
        "Evaluate workflow readiness acceptance criteria.",
        "openrepro acceptance <project>",
        ("workspace/acceptance_criteria.json",),
        ("profile",),
    ),
    WorkflowStep(
        "report",
        "Project report",
        "delivery",
        "Generate the project-level Markdown report.",
        "openrepro report <project>",
        ("reports/report.md",),
        ("acceptance",),
    ),
    WorkflowStep(
        "handoff",
        "Handoff files",
        "delivery",
        "Generate agent and human handoff files.",
        "openrepro handoff <project>",
        ("handoff/AGENT_HANDOFF.md",),
        ("report",),
    ),
    WorkflowStep(
        "evidence_package",
        "Evidence package",
        "delivery",
        "Generate the project-level evidence package.",
        "openrepro evidence-package <project>",
        ("reports/evidence_package.json",),
        ("handoff",),
    ),
    WorkflowStep(
        "review_site",
        "Review site",
        "delivery",
        "Generate the static review site.",
        "openrepro review-site <project>",
        ("reports/review_site/index.html", "reports/review_site_manifest.json"),
        ("evidence_package",),
    ),
    WorkflowStep(
        "collaboration_pack",
        "Collaboration pack",
        "delivery",
        "Generate role-based collaboration checklists.",
        "openrepro collaboration-pack <project>",
        ("handoff/collaboration_pack.json",),
        ("review_site",),
    ),
    WorkflowStep(
        "freshness",
        "Artifact freshness",
        "delivery",
        "Explain stale or missing derived artifacts.",
        "openrepro freshness <project>",
        ("workspace/artifact_freshness.json",),
        ("collaboration_pack",),
    ),
    WorkflowStep(
        "dashboard",
        "Project dashboard",
        "delivery",
        "Generate the static dashboard index.",
        "openrepro dashboard <project>",
        ("reports/dashboard/index.html", "reports/dashboard_manifest.json"),
        ("freshness",),
    ),
    WorkflowStep(
        "local_ui",
        "Local UI",
        "delivery",
        "Generate the static local UI console.",
        "openrepro serve build <project>",
        ("reports/local_ui/index.html", "reports/local_ui_manifest.json", "workspace/local_ui_summary.json"),
        ("dashboard",),
    ),
    WorkflowStep(
        "readiness_review",
        "Readiness review",
        "delivery",
        "Generate the final readiness review.",
        "openrepro readiness-review <project>",
        ("reports/readiness_review.json",),
        ("local_ui",),
    ),
    WorkflowStep(
        "readiness_review_validation",
        "Validate readiness review",
        "delivery",
        "Validate readiness review freshness.",
        "openrepro validate-readiness-review <project>",
        ("reports/readiness_review_validation.json",),
        ("readiness_review",),
    ),
    WorkflowStep(
        "review_action_plan",
        "Review action plan",
        "delivery",
        "Convert readiness blockers into role-based actions.",
        "openrepro review-action-plan <project>",
        ("workspace/review_action_plan.json",),
        ("readiness_review_validation",),
    ),
    WorkflowStep(
        "delivery_bundle",
        "Delivery bundle",
        "delivery",
        "Generate the final workflow delivery bundle.",
        "openrepro delivery-bundle <project>",
        ("reports/delivery_bundle.json",),
        ("review_action_plan",),
    ),
    WorkflowStep(
        "multi_agent_plan",
        "Multi-agent plan",
        "agent",
        "Generate a guarded multi-agent coordination plan.",
        "openrepro multi-agent-plan <project>",
        ("workspace/multi_agent_plan.json",),
        ("delivery_bundle",),
    ),
    WorkflowStep(
        "multi_agent_validation",
        "Validate multi-agent plan",
        "agent",
        "Validate guarded multi-agent tasks.",
        "openrepro validate-multi-agent-plan <project>",
        ("workspace/multi_agent_plan_validation.json",),
        ("multi_agent_plan",),
    ),
    WorkflowStep(
        "agent_board",
        "Agent board",
        "agent",
        "Generate a static multi-agent task board.",
        "openrepro agent-board <project>",
        ("reports/agent_board/index.html", "reports/agent_board_manifest.json"),
        ("multi_agent_validation",),
    ),
    WorkflowStep(
        "agent_dispatch",
        "Agent dispatch",
        "agent",
        "Generate per-agent dispatch task packs.",
        "openrepro agent-dispatch <project>",
        ("workspace/agent_dispatch.json",),
        ("agent_board",),
    ),
    WorkflowStep(
        "agent_exec_plan",
        "Agent execution dry-run",
        "agent",
        "Classify agent tasks into safe dry-run steps and blocked tasks.",
        "openrepro agent-exec-plan <project> --dry-run",
        ("workspace/agent_exec_plan.json",),
        ("agent_dispatch",),
    ),
    WorkflowStep(
        "agent_task_spec",
        "Agent task spec",
        "agent",
        "Generate runner-neutral supervised agent task contracts.",
        "openrepro agent-task-spec <project>",
        ("workspace/agent_task_spec.json", "workspace/agent_result_schema.json"),
        ("agent_exec_plan",),
    ),
    WorkflowStep(
        "agent_adapter",
        "Agent adapter",
        "agent",
        "Generate a supervised external-agent adapter spec.",
        "openrepro agent-adapter <project>",
        ("workspace/agent_adapter.json", "workspace/agent_trajectory.jsonl"),
        ("agent_task_spec",),
    ),
    WorkflowStep(
        "agent_adapter_validation",
        "Validate agent adapter",
        "agent",
        "Validate supervised external-agent adapter guardrails.",
        "openrepro validate-agent-adapter <project>",
        ("workspace/agent_adapter_validation.json", "workspace/AGENT_ADAPTER_VALIDATION.md"),
        ("agent_adapter",),
    ),
    WorkflowStep(
        "paper_lineage",
        "Paper lineage",
        "delivery",
        "Build the claim -> method -> data -> experiment -> metric graph.",
        "openrepro paper-lineage <project>",
        ("workspace/paper_lineage.json",),
        ("agent_adapter_validation",),
    ),
    WorkflowStep(
        "evidence_explorer",
        "Evidence explorer",
        "delivery",
        "Generate a static paper evidence review explorer.",
        "openrepro evidence-explorer <project>",
        ("reports/evidence_explorer/index.html", "reports/evidence_explorer_manifest.json"),
        ("paper_lineage",),
    ),
    WorkflowStep(
        "evidence_query",
        "Evidence query",
        "delivery",
        "Generate searchable evidence query artifacts from the paper evidence explorer.",
        "openrepro evidence-query <project>",
        ("workspace/evidence_query.json", "workspace/EVIDENCE_QUERY.md"),
        ("evidence_explorer",),
    ),
    WorkflowStep(
        "workflow_preset",
        "Workflow preset",
        "delivery",
        "Generate a goal-oriented workflow preset plan from the registered DAG.",
        "openrepro workflow preset <project> --preset delivery",
        ("workspace/workflow_preset.json", "workspace/WORKFLOW_PRESET.md"),
        ("evidence_query",),
    ),
    WorkflowStep(
        "pipeline_spec",
        "Pipeline spec",
        "delivery",
        "Export, plan, and validate the declarative OpenRepro pipeline spec.",
        "openrepro pipeline plan <project>",
        (
            "openrepro.pipeline.yaml",
            "workspace/pipeline_plan.json",
            "workspace/PIPELINE_PLAN.md",
            "workspace/pipeline_validation.json",
            "workspace/PIPELINE_VALIDATION.md",
        ),
        ("workflow_preset",),
    ),
    WorkflowStep(
        "asset_catalog",
        "Asset catalog",
        "delivery",
        "Build a unified catalog of source, data, experiment, run, report, handoff, and workspace assets.",
        "openrepro catalog build <project>",
        ("workspace/asset_catalog.json", "workspace/ASSET_CATALOG.md", "workspace/ASSET_CATALOG_GRAPH.md"),
        ("pipeline_spec",),
    ),
    WorkflowStep(
        "artifact_cache",
        "Artifact cache",
        "delivery",
        "Store observed project artifacts in a local content-addressed cache.",
        "openrepro cache add <project>",
        ("workspace/artifact_cache.json", "workspace/ARTIFACT_CACHE.md"),
        ("asset_catalog",),
    ),
)


def workflow_step_map() -> dict[str, WorkflowStep]:
    """Return workflow steps keyed by step id."""
    return {step.step_id: step for step in WORKFLOW_STEPS}


def generate_workflow_state(project_dir: Path) -> dict[str, Any]:
    """Write workspace/workflow_state.json and workspace/WORKFLOW_STATE.md."""
    project_dir = Path(project_dir)
    state = build_workflow_state(project_dir)
    write_json(project_dir / "workspace" / "workflow_state.json", state)
    safe_write_text(project_dir / "workspace" / "WORKFLOW_STATE.md", _render_state_markdown(state))
    return state


def build_workflow_state(project_dir: Path) -> dict[str, Any]:
    """Build current workflow DAG state without writing files."""
    project_dir = Path(project_dir)
    step_map = workflow_step_map()
    records = []
    statuses: dict[str, str] = {}
    for step in WORKFLOW_STEPS:
        present_outputs = [pattern for pattern in step.outputs if _pattern_exists(project_dir, pattern)]
        missing_outputs = [pattern for pattern in step.outputs if pattern not in present_outputs]
        missing_dependencies = [
            dependency
            for dependency in step.dependencies
            if statuses.get(dependency) != "complete" and not _step_outputs_complete(project_dir, step_map[dependency])
        ]
        status = _step_status(step, missing_outputs, missing_dependencies)
        statuses[step.step_id] = status
        records.append(
            {
                "step_id": step.step_id,
                "title": step.title,
                "stage": step.stage,
                "description": step.description,
                "command": step.command.replace("<project>", str(project_dir)),
                "status": status,
                "safe": step.safe,
                "execution": step.execution,
                "dependencies": list(step.dependencies),
                "missing_dependencies": missing_dependencies,
                "outputs": list(step.outputs),
                "present_outputs": present_outputs,
                "missing_outputs": missing_outputs,
                "runnable": status == "pending" and step.safe,
            }
        )
    counts = _status_counts(records)
    next_step = _next_step(records)
    return {
        "schema_version": WORKFLOW_REGISTRY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "status": "complete" if counts.get("complete", 0) == len(records) else "needs_work",
        "step_count": len(records),
        "complete_step_count": counts.get("complete", 0),
        "pending_step_count": counts.get("pending", 0),
        "blocked_step_count": counts.get("blocked", 0),
        "stale_step_count": counts.get("stale", 0),
        "unsafe_step_count": sum(1 for record in records if not record["safe"]),
        "runnable_step_count": sum(1 for record in records if record["runnable"]),
        "next_step": next_step,
        "top_command": next_step.get("command") if next_step else None,
        "steps": records,
        "guardrails": [
            "Workflow state is derived from declared output artifacts and dependencies.",
            "Unsafe steps are never executed by workflow run or resume.",
            "Human decisions, experiment execution, and repair apply remain explicit commands.",
        ],
    }


def workflow_state_summary(project_dir: Path) -> dict[str, Any]:
    """Return existing workflow state summary without mutating files."""
    project_dir = Path(project_dir)
    path = project_dir / "workspace" / "workflow_state.json"
    markdown_path = project_dir / "workspace" / "WORKFLOW_STATE.md"
    data = read_json(path, default={}) or {}
    data = data if isinstance(data, dict) else {}
    return {
        "present": path.exists(),
        "path": str(path) if path.exists() else None,
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "schema_version": data.get("schema_version"),
        "status": data.get("status", "present" if path.exists() else "missing"),
        "step_count": int(data.get("step_count", 0) or 0),
        "complete_step_count": int(data.get("complete_step_count", 0) or 0),
        "pending_step_count": int(data.get("pending_step_count", 0) or 0),
        "blocked_step_count": int(data.get("blocked_step_count", 0) or 0),
        "stale_step_count": int(data.get("stale_step_count", 0) or 0),
        "runnable_step_count": int(data.get("runnable_step_count", 0) or 0),
        "top_command": data.get("top_command"),
    }


def explain_workflow_step(project_dir: Path, step_id: str) -> dict[str, Any]:
    """Return the current record for one workflow step."""
    state = build_workflow_state(project_dir)
    for step in state["steps"]:
        if step["step_id"] == step_id:
            return {"schema_version": WORKFLOW_REGISTRY_SCHEMA_VERSION, "project_dir": str(project_dir), "step": step}
    raise ValueError(f"Unknown workflow step: {step_id}")


def run_workflow(
    project_dir: Path,
    step_id: str | None = None,
    *,
    confirm: bool = False,
    resume: bool = False,
    export_zip: bool = False,
) -> dict[str, Any]:
    """Run or dry-run safe registered workflow steps."""
    project_dir = Path(project_dir)
    state = build_workflow_state(project_dir)
    selected = _selected_run_steps(state, step_id=step_id, resume=resume)
    records = [_run_record(project_dir, step, confirm=confirm, export_zip=export_zip) for step in selected]
    result = _run_result(project_dir, selected, records, confirm=confirm, resume=resume, export_zip=export_zip)
    write_json(project_dir / "workspace" / "workflow_run.json", result)
    safe_write_text(project_dir / "workspace" / "WORKFLOW_RUN.md", _render_run_markdown(result))
    if confirm and any(record["status"] == "passed" for record in records):
        generate_workflow_state(project_dir)
    return result


def _selected_run_steps(state: dict[str, Any], step_id: str | None, resume: bool) -> list[dict[str, Any]]:
    steps = state["steps"]
    if step_id:
        for step in steps:
            if step["step_id"] == step_id:
                return [step]
        raise ValueError(f"Unknown workflow step: {step_id}")
    runnable = [step for step in steps if step["runnable"]]
    if resume:
        return runnable
    return runnable[:1]


def _run_record(project_dir: Path, step: dict[str, Any], *, confirm: bool, export_zip: bool) -> dict[str, Any]:
    started = iso_now()
    record = {
        "step_id": step["step_id"],
        "title": step["title"],
        "command": step["command"],
        "started_at": started,
        "finished_at": started,
        "duration_seconds": 0.0,
        "status": "dry_run",
        "message": "Pass --confirm to execute this safe derived step.",
    }
    if step["status"] == "complete":
        record["status"] = "skipped"
        record["message"] = "Step outputs are already present."
        return record
    if step["missing_dependencies"]:
        record["status"] = "blocked"
        record["message"] = "Missing dependencies: " + ", ".join(step["missing_dependencies"])
        return record
    if not step["safe"]:
        record["status"] = "blocked"
        record["message"] = "Step is not safe for workflow-managed execution."
        return record
    action = _workflow_actions(export_zip=export_zip).get(step["step_id"])
    if action is None:
        record["status"] = "blocked"
        record["message"] = "No workflow-managed action is registered for this step."
        return record
    if not confirm:
        return record
    start = perf_counter()
    try:
        action(project_dir)
    except Exception as exc:  # pragma: no cover - defensive reporting path
        record["status"] = "failed"
        record["message"] = str(exc)
    else:
        record["status"] = "passed"
        record["message"] = "Step completed."
    record["finished_at"] = iso_now()
    record["duration_seconds"] = round(perf_counter() - start, 6)
    return record


def _run_result(
    project_dir: Path,
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
    *,
    confirm: bool,
    resume: bool,
    export_zip: bool,
) -> dict[str, Any]:
    failed = [record for record in records if record["status"] == "failed"]
    blocked = [record for record in records if record["status"] == "blocked"]
    passed = [record for record in records if record["status"] == "passed"]
    return {
        "schema_version": WORKFLOW_REGISTRY_SCHEMA_VERSION,
        "created_at": iso_now(),
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "mode": "resume" if resume else "run",
        "confirmed": confirm,
        "export_zip": export_zip,
        "status": "failed" if failed else "blocked" if blocked and confirm else "complete" if passed else "dry_run",
        "selected_step_count": len(selected),
        "passed_step_count": len(passed),
        "blocked_step_count": len(blocked),
        "failed_step_count": len(failed),
        "top_failed_step": failed[0]["step_id"] if failed else None,
        "top_blocked_step": blocked[0]["step_id"] if blocked else None,
        "steps": records,
        "guardrails": [
            "Only safe derived workflow steps can execute through this command.",
            "Use the underlying explicit CLI command for experiments, repairs, or human decisions.",
        ],
    }


def _workflow_actions(export_zip: bool = False) -> dict[str, Callable[[Path], Any]]:
    from .acceptance_criteria import generate_acceptance_criteria
    from .advance import generate_advance_plan
    from .agent_adapter import generate_agent_adapter, validate_agent_adapter
    from .agent_board import generate_agent_board
    from .agent_dispatch import generate_agent_dispatch
    from .agent_exec_plan import generate_agent_exec_plan
    from .agent_task_spec import generate_agent_task_spec
    from .asset_catalog import generate_asset_catalog
    from .artifact_cache import add_artifact_cache
    from .checkpoints import generate_workflow_checkpoints
    from .claim_evidence_binder import generate_claim_evidence_binder, validate_claim_evidence_binder
    from .claim_evidence_report import generate_claim_evidence_report
    from .claim_evidence_report_validation import validate_claim_evidence_report
    from .claim_signoff import generate_claim_signoffs
    from .claim_signoff_validation import validate_claim_signoffs
    from .claim_trace import generate_claim_trace, validate_claim_trace
    from .collaboration_pack import generate_collaboration_pack
    from .dashboard import generate_dashboard
    from .data_expectations import run_data_expectations
    from .data_registry import validate_data_index
    from .data_profile import generate_data_profile
    from .delivery_bundle import generate_delivery_bundle
    from .evidence_explorer import generate_evidence_explorer
    from .evidence_graph import generate_evidence_graph
    from .evidence_query import query_evidence
    from .evidence_package import generate_evidence_package
    from .experiment_tracking import generate_experiment_tracking
    from .freshness import generate_artifact_freshness
    from .gaps import generate_reproduction_gaps
    from .handoff_generator import generate_handoff
    from .lineage import generate_run_lineage
    from .local_ui import generate_local_ui
    from .multi_agent_plan import generate_multi_agent_plan
    from .multi_agent_plan_validation import validate_multi_agent_plan
    from .paper_lineage import generate_paper_lineage
    from .pipeline_spec import refresh_pipeline_spec
    from .protocol_coverage import generate_protocol_coverage
    from .protocol_plan import generate_protocol_plan
    from .protocol_preflight import generate_protocol_preflight
    from .project_profile import generate_project_profile
    from .quality_gate import evaluate_all_quality_gates
    from .readiness_review import generate_readiness_review
    from .readiness_review_validation import validate_readiness_review
    from .report_generator import generate_report
    from .repro_lock import generate_repro_lock, validate_repro_lock
    from .reproduction_protocol import generate_reproduction_protocol
    from .review_action_plan import generate_review_action_plan
    from .review_board import generate_review_board
    from .review_decisions import generate_review_decisions
    from .review_site import generate_review_site
    from .reviewer_packet import generate_reviewer_packet
    from .run_index import generate_run_index
    from .scorecard import generate_reproduction_scorecard
    from .timeline import generate_project_timeline
    from .workflow_preset import generate_workflow_preset

    return {
        "data_validation": validate_data_index,
        "data_profile": generate_data_profile,
        "data_expectations": run_data_expectations,
        "repro_lock": generate_repro_lock,
        "repro_lock_validation": validate_repro_lock,
        "quality_gates": evaluate_all_quality_gates,
        "run_index": lambda project_dir: generate_run_index(project_dir, export_zip=export_zip),
        "experiment_tracking": lambda project_dir: generate_experiment_tracking(project_dir, export_zip=export_zip),
        "lineage": generate_run_lineage,
        "claim_trace": generate_claim_trace,
        "claim_trace_validation": validate_claim_trace,
        "evidence_graph": generate_evidence_graph,
        "scorecard": generate_reproduction_scorecard,
        "gaps": generate_reproduction_gaps,
        "checkpoints": generate_workflow_checkpoints,
        "advance_plan": lambda project_dir: generate_advance_plan(project_dir, dry_run=True),
        "review_board": generate_review_board,
        "protocol": generate_reproduction_protocol,
        "protocol_coverage": generate_protocol_coverage,
        "protocol_plan": generate_protocol_plan,
        "protocol_preflight": generate_protocol_preflight,
        "evidence_binder": generate_claim_evidence_binder,
        "evidence_binder_validation": validate_claim_evidence_binder,
        "claim_signoffs": generate_claim_signoffs,
        "claim_signoff_validation": validate_claim_signoffs,
        "claim_evidence_report": generate_claim_evidence_report,
        "claim_evidence_report_validation": validate_claim_evidence_report,
        "reviewer_packet": lambda project_dir: generate_reviewer_packet(project_dir, export_zip=export_zip),
        "timeline": generate_project_timeline,
        "profile": generate_project_profile,
        "acceptance": generate_acceptance_criteria,
        "report": generate_report,
        "handoff": generate_handoff,
        "evidence_package": lambda project_dir: generate_evidence_package(project_dir, export_zip=export_zip),
        "review_site": lambda project_dir: generate_review_site(project_dir, export_zip=export_zip),
        "collaboration_pack": lambda project_dir: generate_collaboration_pack(project_dir, export_zip=export_zip),
        "freshness": generate_artifact_freshness,
        "dashboard": lambda project_dir: generate_dashboard(project_dir, export_zip=export_zip),
        "local_ui": lambda project_dir: generate_local_ui(project_dir, export_zip=export_zip),
        "readiness_review": lambda project_dir: generate_readiness_review(project_dir, export_zip=export_zip),
        "readiness_review_validation": validate_readiness_review,
        "review_action_plan": generate_review_action_plan,
        "delivery_bundle": lambda project_dir: generate_delivery_bundle(project_dir, export_zip=export_zip),
        "multi_agent_plan": generate_multi_agent_plan,
        "multi_agent_validation": validate_multi_agent_plan,
        "agent_board": lambda project_dir: generate_agent_board(project_dir, export_zip=export_zip),
        "agent_dispatch": generate_agent_dispatch,
        "agent_exec_plan": lambda project_dir: generate_agent_exec_plan(project_dir, dry_run=True),
        "agent_task_spec": generate_agent_task_spec,
        "agent_adapter": generate_agent_adapter,
        "agent_adapter_validation": validate_agent_adapter,
        "paper_lineage": generate_paper_lineage,
        "evidence_explorer": lambda project_dir: generate_evidence_explorer(project_dir, export_zip=export_zip),
        "evidence_query": lambda project_dir: query_evidence(project_dir, kind="all", limit=50),
        "workflow_preset": lambda project_dir: generate_workflow_preset(project_dir, preset="delivery"),
        "pipeline_spec": refresh_pipeline_spec,
        "asset_catalog": generate_asset_catalog,
        "artifact_cache": add_artifact_cache,
    }


def _pattern_exists(project_dir: Path, pattern: str) -> bool:
    if any(char in pattern for char in "*?["):
        return any(project_dir.glob(pattern))
    return (project_dir / pattern).exists()


def _step_outputs_complete(project_dir: Path, step: WorkflowStep) -> bool:
    return bool(step.outputs) and all(_pattern_exists(project_dir, pattern) for pattern in step.outputs)


def _step_status(step: WorkflowStep, missing_outputs: list[str], missing_dependencies: list[str]) -> str:
    if not missing_outputs:
        if missing_dependencies:
            return "stale"
        return "complete"
    if missing_dependencies:
        return "blocked"
    return "pending"


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        counts[status] = counts.get(status, 0) + 1
    return counts


def _next_step(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in records:
        if record["status"] != "complete" and not record["missing_dependencies"]:
            return record
    return None


def _render_state_markdown(state: dict[str, Any]) -> str:
    lines = [
        "# Workflow State",
        "",
        f"- Project: `{state['project_name']}`",
        f"- Status: `{state['status']}`",
        f"- Steps: {state['complete_step_count']} complete / {state['step_count']} total",
        f"- Runnable safe steps: {state['runnable_step_count']}",
        f"- Top command: `{state['top_command']}`" if state.get("top_command") else "- Top command: None",
        "",
        "## Steps",
        "",
        "| Step | Stage | Status | Safe | Command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in state["steps"]:
        lines.append(
            f"| `{step['step_id']}` | {step['stage']} | `{step['status']}` | {step['safe']} | `{step['command']}` |"
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in state["guardrails"])
    lines.append("")
    return "\n".join(lines)


def _render_run_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Workflow Run",
        "",
        f"- Project: `{result['project_name']}`",
        f"- Mode: `{result['mode']}`",
        f"- Confirmed: {result['confirmed']}",
        f"- Status: `{result['status']}`",
        f"- Passed: {result['passed_step_count']}",
        f"- Blocked: {result['blocked_step_count']}",
        f"- Failed: {result['failed_step_count']}",
        "",
        "## Steps",
        "",
        "| Step | Status | Message |",
        "| --- | --- | --- |",
    ]
    for step in result["steps"]:
        message = str(step["message"]).replace("|", "\\|")
        lines.append(f"| `{step['step_id']}` | `{step['status']}` | {message} |")
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in result["guardrails"])
    lines.append("")
    return "\n".join(lines)
