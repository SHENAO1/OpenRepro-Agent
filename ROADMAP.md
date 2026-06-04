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

## Long-term ideas

- Paper-to-code workflows with human approval gates.
- Multi-agent task orchestration.
- Dataset and environment provenance tracking.
