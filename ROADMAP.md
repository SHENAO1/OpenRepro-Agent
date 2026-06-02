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

## Long-term ideas

- Paper-to-code workflows with human approval gates.
- Multi-agent task orchestration.
- Reproduction scorecards.
- Dataset and environment provenance tracking.
