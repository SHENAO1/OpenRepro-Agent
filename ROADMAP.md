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

- Prompt/response redaction and stronger cache controls.
- [x] Human approval gates that can promote verified candidates into implementation-ready experiment scaffolds.
- [x] Controlled repair dry-run previews with manifest regeneration diffs.
- Richer benchmark tasks with dataset/environment provenance.
- Run lineage graphs and cross-run metric dashboards.

Implemented in v0.5.0 with `openrepro approve-candidates`, `workspace/verified_candidates.json`,
verified-input experiment scaffolds, and `openrepro repair --dry-run`.

## v0.5.1 — Status visibility layer

- [x] Surface verified candidate counts and approval status in `openrepro inspect`.
- [x] Surface latest repair dry-run status in `openrepro inspect`.
- [x] Include verified candidate and repair dry-run summaries in reports.
- [x] Include verified candidate and repair dry-run handoff files.
- [x] Suggest `approve-candidates` from project status after analysis/planning when candidates remain unapproved.

## Long-term ideas

- Paper-to-code workflows with human approval gates.
- Multi-agent task orchestration.
- Reproduction scorecards.
- Dataset and environment provenance tracking.
