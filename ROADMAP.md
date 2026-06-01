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

- Real LLM Provider interface, disabled by default.
- Cache-aware API usage tracking.
- Benchmark runner based on `benchmarks/benchmark_schema.json`.
- Experiment failure classification and repair suggestions.
- Regression tests for generated artifacts.

## Long-term ideas

- Paper-to-code workflows with human approval gates.
- Multi-agent task orchestration.
- Reproduction scorecards.
- Dataset and environment provenance tracking.
