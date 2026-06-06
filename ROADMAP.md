# Roadmap

## v0.1.0 — Minimum runnable workflow

- [x] Python CLI with Typer
- [x] Project initialization
- [x] Markdown/txt ingestion
- [x] PDF placeholder ingestion
- [x] Rule/mock analysis
- [x] Model ledger
- [x] Experiment plan
- [x] Lightweight BOC-like demo
- [x] Reports and handoff files
- [x] Mock API usage accounting
- [x] pytest coverage

## v0.2.0 — Better paper and model extraction

- [x] Artifact manifest and run-evidence validation.
- [x] PDF text extraction with explicit provenance.
- [x] Formula candidate detection.
- [x] Parameter and table candidate extraction.
- [x] More structured model ledger schema.
- [x] Experiment plan validation.
- [x] More demo configurations and parameter sweeps.

Released in v0.2.0 with `openrepro validate` and `openrepro run-sweep`.

## v0.3.0 — Provider and benchmark layer

- [x] Provider interface with deterministic mock provider, real APIs disabled by default.
- [x] Cache-aware API usage tracking.
- [x] Benchmark runner based on `benchmarks/benchmark_schema.json`.
- [x] Experiment failure classification and repair suggestions.
- [x] Regression tests for generated artifacts.

Released in v0.3.0 with `openrepro benchmark` and `openrepro diagnose`.

## v0.3.1 — Stability and observability layer

- [x] Project inspection with `openrepro inspect` and `workspace/inspect_summary.json`.
- [x] All-run manifest validation with `openrepro validate --all`.
- [x] Benchmark index generation after each benchmark run.
- [x] Rebuildable benchmark indexes with `openrepro benchmark-index`.
- [x] Backward-compatible benchmark schema hardening for required/optional artifacts and metrics.

Released in v0.3.1 with project observability, benchmark indexing, and schema compatibility hardening.

## v0.4.0 — Opt-in provider and paper-to-code guardrails

- [x] OpenAI-compatible provider path with explicit opt-in and environment-backed secrets.
- [x] Provider configuration command that never stores API key values.
- [x] Human-gated experiment scaffolds from candidate formulas and parameters.
- [x] Benchmark suites with suite-level evidence and manifests.
- [x] Advisory repair plans from diagnosis output.
- [x] Run comparison artifacts for demo/sweep outputs.

Released in v0.4.0 with opt-in provider readiness, paper-to-code guardrails, benchmark suites, repair planning, and run comparison.

## v0.5.0 — Stronger paper-to-code and repair loop

- [x] Prompt/response redaction and stronger cache controls.
- [x] Human approval gates that can promote verified candidates into implementation-ready experiment scaffolds.
- [x] Controlled repair dry-run previews with manifest regeneration diffs.
- [x] Richer benchmark tasks with dataset/environment provenance.
- [x] Run lineage graphs and cross-run metric dashboards.

Implemented in v0.5.0 with `openrepro approve-candidates`, `workspace/verified_candidates.json`,
verified-input experiment scaffolds, and `openrepro repair --dry-run`.

## v0.5.1 — Status visibility layer

- [x] Surface verified candidate counts and approval status in `openrepro inspect`.
- [x] Surface latest repair dry-run status in `openrepro inspect`.
- [x] Include verified candidate and repair dry-run summaries in reports.
- [x] Include verified candidate and repair dry-run handoff files.
- [x] Suggest `approve-candidates` from project status after analysis/planning when candidates remain unapproved.

## v0.5.2 — Provider safety and cache policy

- [x] Redact likely secrets from provider prompt/response previews in usage records.
- [x] Store provider cache entries under provider/model/task namespaces.
- [x] Add cache policy fields: `cache_enabled`, `cache_ttl_seconds`, and `redact_prompts`.
- [x] Allow `configure-provider` to update cache and redaction policy.

## v0.6.0 — Provenance and run lineage

- [x] Add benchmark provenance fields for dataset, environment, dependencies, paper source, and runtime notes.
- [x] Include provenance completeness in benchmark reports, suite task results, and benchmark indexes.
- [x] Add `openrepro lineage` with `workspace/run_lineage.json` and `workspace/RUN_LINEAGE.md`.
- [x] Record run manifest, config, source index, and verified candidate hashes.

## v0.6.1 — Manifest-only repair apply

- [x] Add `openrepro repair --apply --only manifest --confirm`.
- [x] Regenerate missing or mismatched manifests from files already present on disk.
- [x] Write `workspace/repair_apply.json` and `workspace/REPAIR_APPLY.md`.
- [x] Keep apply mode from generating scientific artifacts, editing experiment code, or changing configuration values.

## v0.6.2 — Stability and health checks

- [x] Add `openrepro doctor` with dependency, project structure, config, and provider readiness checks.
- [x] Surface lineage status in `inspect`, `status`, and handoff files.
- [x] Add `handoff/RUN_LINEAGE.md` to generated handoff bundles.
- [x] Expand smoke tests to cover approval, lineage, repair dry-run/apply, and doctor commands.

## v0.7.0 — Controlled experiment execution

- [x] Add `openrepro run-experiment`.
- [x] Require `verified_inputs_ready`, runnable experiment config, and explicit `--confirm`.
- [x] Capture runner stdout/stderr, execution metadata, config snapshot, runner copy, report, and manifest.
- [x] Keep experiment runs as execution evidence only, not reproduction claims.

## v0.7.1 — Candidate review lifecycle

- [x] Add `openrepro list-candidates`.
- [x] Add `openrepro review-candidates`.
- [x] Support review statuses `verified_by_human`, `rejected_by_human`, and `needs_more_evidence`.
- [x] Write `workspace/candidate_reviews.json` and `workspace/CANDIDATE_REVIEWS.md`.
- [x] Sync `verified_by_human` reviews into verified candidate artifacts.

## v0.7.2 — Stabilization and release hygiene

- [x] Improve `openrepro status` next-step suggestions for candidate review, scaffold, and experiment-run flows.
- [x] Add candidate review and experiment-run counts to status and inspect output.
- [x] Keep smoke scripts aligned with the v0.7.x command set.
- [x] Add release tags for recent versions.

## v0.8.0 — Paper evidence provenance

- [x] Add `workspace/paper_metadata.json` with title and DOI candidates.
- [x] Add source path, chunk index, page number, context window, and evidence quality to formula candidates.
- [x] Add numeric values, normalized units, context window, and evidence quality to parameter candidates.
- [x] Preserve table/page provenance for PDF table-derived parameter candidates.

## v0.8.1 — Experiment templates and artifact expectations

- [x] Add `basic`, `boc-like`, and `numeric-sweep` templates for `openrepro scaffold-experiment`.
- [x] Generate runnable template starter code when verified inputs are available.
- [x] Align scaffold `expected_artifacts.json` with current `run-experiment` outputs.
- [x] Include template-required artifacts in `run-experiment` manifests.

## v0.8.2 — Template discovery and scaffold diagnostics

- [x] Add `openrepro list-templates`.
- [x] Centralize template metadata and artifact expectations.
- [x] Surface scaffold template counts and expected-artifact attention counts in `inspect` and `status`.
- [x] Diagnose legacy, missing, mismatched, or tampered `expected_artifacts.json` files.

## v0.9.0 — Verified candidates to experiment inputs

- [x] Generate `experiments/<id>/experiment_inputs.json`.
- [x] Map verified parameter candidates into template-readable `parameter_values`.
- [x] Add template input completeness checks.
- [x] Have template runners read `OPENREPRO_EXPERIMENT_INPUTS`.
- [x] Snapshot experiment inputs in run outputs and surface them in reports and handoff files.

## v0.9.1 — Environment snapshot and repeatability evidence

- [x] Write `configs/environment_snapshot.json` for experiment runs.
- [x] Record Python version, platform, dependency versions, random seed, and runner hash.
- [x] Include environment snapshots in run-experiment manifests.
- [x] Add same-seed repeatability checks against prior experiment runs.
- [x] Extend lineage with experiment config, inputs, environment, and runner hashes.

## v0.9.2 — Experiment input calibration

- [x] Add `openrepro validate-inputs`.
- [x] Add `openrepro set-input`.
- [x] Track input sources as `verified_candidate`, `manual_override`, or `default`.
- [x] Surface missing required input counts in `inspect` and `status`.
- [x] Record input validation details and warnings in run evidence.

## v0.9.3 — Repeat experiment comparison

- [x] Add `openrepro rerun-experiment`.
- [x] Add `openrepro compare-experiments`.
- [x] Write same-experiment comparison JSON and Markdown artifacts.
- [x] Compare metric deltas, runner hashes, raw input hashes, normalized input hashes, and environment hashes.
- [x] Extend lineage with experiment repeat groups and repeat run indexes.

## v1.0.0 — Project evidence package

- [x] Add `openrepro evidence-package`.
- [x] Write `reports/evidence_package.json` and `reports/evidence_package.md`.
- [x] Summarize inspect output, workspace artifacts, experiment scaffolds, run manifests, lineage, benchmark indexes, reports, and handoff completeness.
- [x] Keep evidence package output limited to engineering evidence and explicit limitations.

## v1.0.1 — Evidence package stabilization

- [x] Add source fingerprints and artifact SHA-256 hashes.
- [x] Surface evidence package freshness in project status.
- [x] Add `openrepro evidence-package --zip`.
- [x] Add `handoff/EVIDENCE_PACKAGE.md`.
- [x] Add stale-package and zip-export tests.

## v1.1.0 — Paper evidence extraction upgrade

- [x] Add section-aware provenance for formula and parameter candidates.
- [x] Add caption indexing artifacts.
- [x] Add candidate risk flags and risk-level counts.
- [x] Surface high-risk candidates in `openrepro inspect`.
- [x] Include caption index evidence in evidence packages.

## v1.2.0 — Experiment spec contract

- [x] Add `experiments/<id>/experiment_spec.json`.
- [x] Add `openrepro validate-experiment-spec`.
- [x] Validate experiment specs before `run-experiment`.
- [x] Snapshot spec contracts into run outputs.
- [x] Include spec hashes in experiment comparison and lineage.

## v1.6.1 — Claim trace validation

- [x] Add `openrepro validate-claims`.
- [x] Add `openrepro trace-claims --validate`.
- [x] Write `workspace/claim_trace_validation.json` and `workspace/CLAIM_TRACE_VALIDATION.md`.
- [x] Detect missing, stale, or broken claim trace links across candidates, experiment specs, registered data, and runs.
- [x] Surface claim trace validation in status, inspect, diagnose, and evidence packages.

Released in v1.6.1 with claim trace freshness and link-integrity validation.

## v1.7.0 — Reproduction readiness scorecard

- [x] Add `openrepro scorecard`.
- [x] Write `workspace/reproduction_scorecard.json` and `workspace/REPRODUCTION_SCORECARD.md`.
- [x] Score workflow readiness across paper evidence, candidate review, data provenance, experiment specs, run evidence, quality gates, repeatability evidence, and claim trace health.
- [x] Surface scorecard summaries in status, inspect, handoff, and evidence packages.
- [x] Keep readiness scores limited to workflow evidence completeness rather than scientific reproduction success.

Released in v1.7.0 with project-level readiness scorecards.

## v1.7.1 — Actionable reproduction gaps

- [x] Add `openrepro gaps`.
- [x] Add `openrepro todo` as a to-do oriented alias.
- [x] Write `workspace/reproduction_gaps.json` and `workspace/REPRODUCTION_GAPS.md`.
- [x] Convert upstream workflow evidence gaps into severity-ranked suggested commands.
- [x] Surface gap counts in status, inspect, reports, handoff, and evidence packages.

Released in v1.7.1 with actionable workflow gap artifacts.

## v1.8.0 — Workflow checkpoint engine

- [x] Add `openrepro checkpoints`.
- [x] Write `workspace/workflow_checkpoints.json` and `workspace/WORKFLOW_CHECKPOINTS.md`.
- [x] Normalize major workflow stages into `complete`, `partial`, `blocked`, or `missing`.
- [x] Expose the next checkpoint and suggested command.
- [x] Surface checkpoint status in status, inspect, reports, handoff, and evidence packages.

Released in v1.8.0 with normalized workflow checkpoint status.

## v1.8.1 — Guided advance dry-run

- [x] Add `openrepro advance --dry-run`.
- [x] Write `workspace/advance_plan.json` and `workspace/ADVANCE_PLAN.md`.
- [x] Select the next command from open gaps or the next incomplete checkpoint.
- [x] Keep advance mode non-executing and explicit about placeholder commands.
- [x] Surface advance plan status in status, inspect, reports, handoff, and evidence packages.

Released in v1.8.1 with guided dry-run advance plans.

## v1.9.0 — Human review board

- [x] Add `openrepro review-board`.
- [x] Write `workspace/review_board.json` and `workspace/REVIEW_BOARD.md`.
- [x] Consolidate candidate, data, spec, claim trace, scorecard, gap, and advance review prompts.
- [x] Surface review board status in status, inspect, reports, handoff, and evidence packages.
- [x] Keep review board output advisory; it does not prove scientific reproduction success.

Released in v1.9.0 with a consolidated human review board.

## v1.9.1 — Review decision loop

- [x] Add `openrepro review-decision`.
- [x] Write `workspace/review_decisions.json` and `workspace/REVIEW_DECISIONS.md`.
- [x] Support `resolved`, `rejected`, `deferred`, and `needs_followup` decisions.
- [x] Track unresolved review board items after the latest human decision.
- [x] Surface review decision status in status, inspect, reports, handoff, and evidence packages.

Released in v1.9.1 with human review decision records.

## v1.10.0 — Reproduction protocol

- [x] Add `openrepro protocol`.
- [x] Write `workspace/reproduction_protocol.json` and `workspace/REPRODUCTION_PROTOCOL.md`.
- [x] Summarize target claims, required data, required experiments, and required runs.
- [x] Define acceptance criteria from claim trace, data, specs, runs, quality gates, scorecard, gaps, and review workflow state.
- [x] Surface protocol status in status, inspect, reports, handoff, and evidence packages.

Released in v1.10.0 with workflow-level reproduction protocols.

## v1.10.1 — Protocol coverage

- [x] Add `openrepro protocol-coverage`.
- [x] Write `workspace/protocol_coverage.json` and `workspace/PROTOCOL_COVERAGE.md`.
- [x] Check target claim, data, experiment, run, and acceptance-criteria coverage.
- [x] Surface protocol coverage status in status, inspect, reports, handoff, and evidence packages.
- [x] Keep coverage scores limited to workflow evidence completeness.

Released in v1.10.1 with protocol coverage checks.

## v1.11.0 — Protocol action plan

- [x] Add `openrepro protocol-plan`.
- [x] Write `workspace/protocol_plan.json` and `workspace/PROTOCOL_PLAN.md`.
- [x] Convert protocol coverage gaps into prioritized workflow actions.
- [x] Surface critical/high counts and top command in status, inspect, reports, handoff, and evidence packages.
- [x] Keep action plans advisory and non-executing.

Released in v1.11.0 with protocol action plans.

## v1.11.1 — Protocol preflight

- [x] Add `openrepro protocol-preflight`.
- [x] Write `workspace/protocol_preflight.json` and `workspace/PROTOCOL_PREFLIGHT.md`.
- [x] Check protocol readiness, coverage, action plan, data provenance, experiment specs, quality gates, and review decisions.
- [x] Surface preflight blockers and warnings in status, inspect, reports, handoff, and evidence packages.
- [x] Keep evidence package freshness as an advisory warning so preflight can run before packaging.

Released in v1.11.1 with protocol readiness preflight checks.

## v1.12.0 — Claim evidence binder

- [x] Add `openrepro evidence-binder`.
- [x] Write `workspace/claim_evidence_binder.json` and `workspace/CLAIM_EVIDENCE_BINDER.md`.
- [x] Bind each traced claim to experiments, runs, registered data, quality gates, protocol coverage, and review decisions.
- [x] Surface incomplete claim counts in status, inspect, reports, handoff, and evidence packages.
- [x] Keep claim binding limited to workflow evidence organization.

Released in v1.12.0 with claim evidence binders.

## v1.12.1 — Claim evidence binder validation

- [x] Add `openrepro validate-evidence-binder`.
- [x] Write `workspace/claim_evidence_binder_validation.json` and `workspace/CLAIM_EVIDENCE_BINDER_VALIDATION.md`.
- [x] Detect stale binders when claims, protocol coverage, review decisions, data, specs, or runs change.
- [x] Check claim counts, duplicate claim ids, and missing-evidence consistency.
- [x] Surface binder validation in status, inspect, reports, handoff, and evidence packages.

Released in v1.12.1 with claim evidence binder validation.

## v1.13.0 — Claim signoff loop

- [x] Add `openrepro claim-signoff`.
- [x] Write `workspace/claim_signoffs.json` and `workspace/CLAIM_SIGNOFFS.md`.
- [x] Support `accepted_workflow_evidence`, `needs_more_evidence`, `rejected`, and `deferred` decisions.
- [x] Track signed, unsigned, terminal, accepted, and open claim counts.
- [x] Surface claim signoff status in status, inspect, reports, handoff, and evidence packages.

Released in v1.13.0 with human signoffs for claim evidence binder records.

## v1.13.1 — Claim evidence report

- [x] Add `openrepro claim-evidence-report`.
- [x] Write `reports/claim_evidence_report.json` and `reports/claim_evidence_report.md`.
- [x] Combine claim binder evidence, binder validation, and latest human signoffs per claim.
- [x] Surface open actions and top command for reviewer handoff.
- [x] Surface claim evidence report status in status, inspect, reports, handoff, and evidence packages.

Released in v1.13.1 with reviewer-facing claim evidence reports.

## v1.14.0 — Claim signoff validation

- [x] Add `openrepro validate-claim-signoffs`.
- [x] Write `workspace/claim_signoff_validation.json` and `workspace/CLAIM_SIGNOFF_VALIDATION.md`.
- [x] Detect stale signoff snapshots, orphan signoffs, incomplete accepted claims, and failed binder validation.
- [x] Surface claim signoff validation status in status, inspect, reports, handoff, and evidence packages.
- [x] Keep validation scoped to workflow decision freshness, not scientific proof.

Released in v1.14.0 with claim signoff freshness validation.

## v1.14.1 — Claim evidence report validation

- [x] Add `openrepro validate-claim-evidence-report`.
- [x] Write `reports/claim_evidence_report_validation.json` and `reports/claim_evidence_report_validation.md`.
- [x] Detect stale reports when binder evidence, binder validation, or claim signoffs change.
- [x] Check claim row counts, open action counts, and ready-report consistency.
- [x] Surface claim evidence report validation status in status, inspect, reports, handoff, and evidence packages.

Released in v1.14.1 with claim evidence report freshness validation.

## v1.15.0 — Reviewer packet

- [x] Add `openrepro reviewer-packet`.
- [x] Write `reports/reviewer_packet.json`, `reports/reviewer_packet.md`, and optional `reports/reviewer_packet.zip`.
- [x] Summarize claim evidence, signoffs, validations, open actions, review order, and source artifact hashes.
- [x] Surface reviewer packet status in status, inspect, reports, handoff, and evidence packages.
- [x] Keep reviewer packets scoped to workflow review handoff, not scientific proof.

Released in v1.15.0 with reviewer packets for human claim evidence review.

## v1.16.0 — Static review site

- [x] Add `openrepro review-site`.
- [x] Write `reports/review_site/index.html`, `reports/review_site_manifest.json`, and optional `reports/review_site.zip`.
- [x] Summarize readiness, claim evidence, evidence package freshness, quality gates, open actions, blockers, and artifact links.
- [x] Surface review site status in status, inspect, reports, handoff, and evidence packages.
- [x] Keep review sites as static workflow handoff views, not scientific proof.

Released in v1.16.0 with a static human review site.

## v1.16.1 — Project timeline

- [x] Add `openrepro timeline`.
- [x] Write `workspace/project_timeline.json` and `workspace/PROJECT_TIMELINE.md`.
- [x] Consolidate source ingestion, reviews, signoffs, review decisions, runs, quality gates, and evidence artifacts into chronological events.
- [x] Surface timeline status in status, inspect, reports, handoff, evidence packages, and review sites.
- [x] Keep timeline records scoped to workflow history and decision audit, not scientific proof.

Released in v1.16.1 with project timelines and decision logs.

## v1.17.0 — Collaboration pack

- [x] Add `openrepro collaboration-pack`.
- [x] Write `handoff/collaboration_pack.json`, `handoff/COLLABORATION_PACK.md`, and optional `handoff/collaboration_pack.zip`.
- [x] Split collaboration work into maintainer, reviewer, experimenter, and next-agent checklists.
- [x] Summarize unresolved decisions, next safe commands, readiness state, and files to inspect first.
- [x] Surface collaboration pack status in status, inspect, reports, handoff, and evidence packages.

Released in v1.17.0 with role-based collaboration packs.

## v1.18.0 — Refresh pipeline

- [x] Add `openrepro refresh`.
- [x] Write `workspace/refresh_run.json`, `workspace/REFRESH_RUN.md`, and optional `workspace/refresh_run.zip`.
- [x] Refresh derived workflow artifacts without running experiments, adding signoffs, or closing review decisions.
- [x] Record per-step status, failed step count, top failed step, guardrails, and policy.
- [x] Surface refresh run status in status, inspect, reports, handoff, and evidence packages.

Released in v1.18.0 with a safe derived-artifact refresh pipeline.

## v1.18.1 — Artifact freshness graph

- [x] Add `openrepro freshness`.
- [x] Write `workspace/artifact_freshness.json` and `workspace/ARTIFACT_FRESHNESS.md`.
- [x] Compare evidence package source fingerprints against current project evidence.
- [x] Explain stale or missing review sites, timelines, reviewer packets, collaboration packs, refresh runs, protocol preflight, and review decisions.
- [x] Surface top stale node, top stale reason, and suggested command in status, inspect, reports, handoff, and evidence packages.

Released in v1.18.1 with artifact freshness reasons and dependency edges.

## v1.19.0 — Project dashboard index

- [x] Add `openrepro dashboard`.
- [x] Write `reports/dashboard/index.html`, `reports/dashboard_manifest.json`, and optional `reports/dashboard.zip`.
- [x] Combine readiness score, artifact freshness, refresh run, collaboration pack, timeline, reviewer packet, review site, evidence package, and handoff links.
- [x] Surface dashboard status in status, inspect, reports, handoff, review sites, and evidence packages.
- [x] Keep dashboards as static project handoff views, not scientific proof.

Released in v1.19.0 with a static project dashboard.

## v1.20.0 — Project reproduction profile

- [x] Add `openrepro profile`.
- [x] Write `workspace/project_profile.json` and `workspace/PROJECT_PROFILE.md`.
- [x] Summarize project type, reproduction goal, target claims, required data, required experiments, and acceptance dimensions.
- [x] Surface project profile status in status, inspect, reports, handoff, freshness, dashboards, refresh runs, and evidence packages.
- [x] Keep profiles as scope and acceptance definitions, not scientific proof.

Released in v1.20.0 with an auditable project reproduction profile.

## v1.20.1 — Acceptance criteria

- [x] Add `openrepro acceptance`.
- [x] Write `workspace/acceptance_criteria.json` and `workspace/ACCEPTANCE_CRITERIA.md`.
- [x] Evaluate claim review, data provenance, experiment scaffolds, input/spec readiness, run evidence, quality gates, claim trace validation, scorecard gaps, and protocol readiness.
- [x] Surface acceptance criteria status in status, inspect, reports, handoff, freshness, dashboards, refresh runs, and evidence packages.
- [x] Keep acceptance criteria as workflow readiness checks, not scientific proof.

Released in v1.20.1 with project-level acceptance criteria.

## v1.21.0 — Readiness review

- [x] Add `openrepro readiness-review`.
- [x] Write `reports/readiness_review.json`, `reports/READINESS_REVIEW.md`, and optional `reports/readiness_review.zip`.
- [x] Check profile, acceptance criteria, evidence package freshness, artifact freshness, refresh run, dashboard, collaboration pack, review site, reviewer packet, scorecard, gaps, protocol preflight, and review decisions.
- [x] Surface readiness review status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep readiness reviews as final workflow handoff reports, not scientific proof.

Released in v1.21.0 with final readiness review reports.

## v1.21.1 — Readiness review validation

- [x] Add `openrepro validate-readiness-review`.
- [x] Write `reports/readiness_review_validation.json` and `reports/READINESS_REVIEW_VALIDATION.md`.
- [x] Validate readiness review freshness against current project state and check internal count/status consistency.
- [x] Surface readiness review validation status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep readiness review validation as report freshness evidence, not scientific proof.

Released in v1.21.1 with readiness review freshness validation.

## v1.22.0 — Review action plan

- [x] Add `openrepro review-action-plan`.
- [x] Write `workspace/review_action_plan.json` and `workspace/REVIEW_ACTION_PLAN.md`.
- [x] Convert blocked readiness review checks into role-based actions with priority, command, status, and source check.
- [x] Surface review action plan status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep review action plans advisory: they do not execute commands or close human decisions.

Released in v1.22.0 with role-based review action plans.

## v1.22.1 — Final delivery bundle

- [x] Add `openrepro delivery-bundle`.
- [x] Write `reports/delivery_bundle.json`, `reports/DELIVERY_BUNDLE.md`, and optional `reports/delivery_bundle.zip`.
- [x] Check final handoff, evidence package, reviewer packet, review site, dashboard, collaboration pack, readiness review validation, and review action plan files.
- [x] Surface delivery bundle status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep delivery bundles as workflow handoff manifests, not scientific proof.

Released in v1.22.1 with final workflow delivery bundles.

## v1.23.0 — Multi-agent coordination plan

- [x] Add `openrepro multi-agent-plan`.
- [x] Write `workspace/multi_agent_plan.json` and `workspace/MULTI_AGENT_PLAN.md`.
- [x] Define maintainer, reviewer, experimenter, and next-agent roles with task ownership.
- [x] Convert review actions, collaboration checklists, delivery bundle state, and project status into guarded agent tasks.
- [x] Surface multi-agent plan status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep multi-agent plans advisory: they do not execute agents, run experiments, close decisions, or add signoffs.

Released in v1.23.0 with guarded multi-agent coordination plans.

## v1.23.1 — Multi-agent plan validation

- [x] Add `openrepro validate-multi-agent-plan`.
- [x] Write `workspace/multi_agent_plan_validation.json` and `workspace/MULTI_AGENT_PLAN_VALIDATION.md`.
- [x] Check required fields, task counts, current-project freshness, agent IDs, priorities, task status, and unsafe commands.
- [x] Surface validation status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep validation read-only: it does not execute agents, repair plans, run experiments, close decisions, or add signoffs.

Released in v1.23.1 with guarded multi-agent plan validation.

## v1.24.0 — Static agent board

- [x] Add `openrepro agent-board`.
- [x] Write `reports/agent_board/index.html`, `reports/agent_board_manifest.json`, and optional `reports/agent_board.zip`.
- [x] Display guarded tasks by maintainer, reviewer, experimenter, and next-agent lanes.
- [x] Surface agent board status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep agent boards as static workflow views: they do not dispatch agents or execute task commands.

Released in v1.24.0 with a static multi-agent task board.

## v1.24.1 — Agent dispatch pack

- [x] Add `openrepro agent-dispatch`.
- [x] Write `workspace/agent_dispatch.json`, `workspace/AGENT_DISPATCH.md`, and per-role `workspace/agents/<agent>/TASKS.md` files.
- [x] Split guarded multi-agent tasks into maintainer, reviewer, experimenter, and next-agent task packs.
- [x] Surface dispatch pack status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep dispatch packs advisory: they do not dispatch agents or execute task commands.

Released in v1.24.1 with per-agent task dispatch packs.

## v1.25.0 — Safe agent execution dry-run

- [x] Add `openrepro agent-exec-plan --dry-run`.
- [x] Write `workspace/agent_exec_plan.json` and `workspace/AGENT_EXEC_PLAN.md`.
- [x] Classify dispatch tasks into safe derived-artifact dry-run steps versus blocked tasks.
- [x] Allow only safe derived artifact commands and block experiments, reruns, claim signoffs, review decisions, repair apply, human-input tasks, and placeholder commands.
- [x] Surface execution dry-run status in status, inspect, reports, handoff, refresh runs, and CLI output.

Released in v1.25.0 with safe agent execution dry-run plans.

## v1.26.0 — Paper lineage graph

- [x] Add `openrepro paper-lineage`.
- [x] Write `workspace/paper_lineage.json` and `workspace/PAPER_LINEAGE.md`.
- [x] Build a claim -> method -> data -> experiment -> metric graph from existing workflow artifacts.
- [x] Surface paper lineage status in status, inspect, reports, handoff, refresh runs, and CLI output.
- [x] Keep paper lineage as evidence organization only, not scientific reproduction proof.

Released in v1.26.0 with paper-level lineage graphs.

## v1.27.0 — Workflow registry and DAG state

- [x] Add `openrepro workflow status`.
- [x] Add `openrepro workflow explain`.
- [x] Add `openrepro workflow run` and `openrepro workflow resume` with dry-run-by-default behavior.
- [x] Write `workspace/workflow_state.json`, `workspace/WORKFLOW_STATE.md`, `workspace/workflow_run.json`, and `workspace/WORKFLOW_RUN.md`.
- [x] Register major workflow steps with declared dependencies, outputs, safety flags, and command hints.
- [x] Keep workflow-managed execution limited to safe derived artifacts and block experiments, human decisions, repair apply, and input-gathering steps.

Released in v1.27.0 with a registered workflow DAG and safe derived-step execution shell.

## v1.28.0 — Run index and explorer

- [x] Add `openrepro runs index`.
- [x] Add `openrepro runs list`, `openrepro runs show`, and `openrepro runs compare`.
- [x] Write `workspace/run_index.json`, `workspace/RUN_INDEX.md`, `reports/run_explorer/index.html`, and `reports/run_explorer_manifest.json`.
- [x] Add optional `reports/run_explorer.zip` export.
- [x] Summarize run manifests, commands, experiments, quality gates, metrics, artifact links, and SHA-256 fingerprints.
- [x] Refresh registered data validation and run index before lineage.

Released in v1.28.0 with a local run index, static run explorer, and indexed run comparisons.

## v1.29.0 — Reproducibility lockfile

- [x] Add `openrepro lock`.
- [x] Add `openrepro validate-lock`.
- [x] Write `openrepro.lock.json`, `workspace/REPRO_LOCK.md`, `workspace/repro_lock_validation.json`, and `workspace/REPRO_LOCK_VALIDATION.md`.
- [x] Lock project configuration, registered data hashes, Python/platform metadata, dependency versions, and experiment contract hashes.
- [x] Detect data hash drift, config drift, experiment contract drift, and optional strict dependency drift.
- [x] Refresh the lockfile and lock validation before run evidence refresh.

Released in v1.29.0 with project reproducibility lockfiles and validation.

## v1.30.0 — Supervised agent adapter

- [x] Add `openrepro agent-adapter`.
- [x] Add `openrepro validate-agent-adapter`.
- [x] Write `workspace/agent_adapter.json`, `workspace/AGENT_ADAPTER.md`, `workspace/agent_adapter_validation.json`, `workspace/AGENT_ADAPTER_VALIDATION.md`, and `workspace/agent_trajectory.jsonl`.
- [x] Convert safe dry-run agent execution steps into externally supervised runner handoff records.
- [x] Require approval and external supervision for every adapter step.
- [x] Keep experiments, repairs, human decisions, claim signoffs, and blocked tasks out of adapter execution.

Released in v1.30.0 with supervised external-agent adapter specs.

## v1.31.0 — Static evidence explorer

- [x] Add `openrepro evidence-explorer`.
- [x] Write `reports/evidence_explorer/index.html`, `reports/evidence_explorer_manifest.json`, and optional `reports/evidence_explorer.zip`.
- [x] Combine paper lineage, claim evidence binder records, registered data, run index rows, and artifact links into a static reviewer-facing evidence browser.
- [x] Refresh the evidence explorer after paper lineage.
- [x] Keep evidence explorers as navigation for workflow evidence only, not scientific verification.

Released in v1.31.0 with a static paper evidence explorer.

## Long-term ideas

- Paper-to-code workflows with human approval gates.
- Multi-agent execution adapters for externally supervised agent runners.
- Dataset and environment provenance tracking.
