# Architecture

OpenRepro-Agent v0.4.0 uses a small modular CLI architecture.

## Modules

- `cli.py`: Typer command definitions and user-facing output.
- `project_manager.py`: project initialization and status checks.
- `document_loader.py`: source ingestion, PDF extraction, and source index management.
- `analyzer.py`: rule-based candidate analysis.
- `planner.py`: experiment plan generation and validation.
- `approval.py`: human approval artifacts for formula and parameter candidates.
- `demo_runner.py`: lightweight BOC-like signal demo and parameter sweep.
- `artifact_manager.py`: run directory, artifact manifest, and validation utilities.
- `api_usage.py`: mock/cached usage record and summary schema.
- `provider.py`: provider interface, deterministic mock provider, opt-in OpenAI-compatible provider, and request-hash cache.
- `experiment_scaffold.py`: human-gated experiment scaffolds from candidate evidence.
- `benchmark_runner.py`: workflow-compliance benchmark and benchmark-suite execution.
- `inspector.py`: project observability summary for humans and agents.
- `diagnostics.py`: failure classification and repair suggestions.
- `repair.py`: advisory repair plan generation.
- `run_compare.py`: run metric and manifest comparison.
- `report_generator.py`: project-level report creation.
- `handoff_generator.py`: multi-agent handoff generation.
- `config.py`: dataclass-based configuration defaults and YAML IO.
- `utils.py`: shared helper functions.

## Data flow

```text
sources/ + project_config.yaml
  → workspace/source_index.json
  → workspace/paper_summary.md + MODEL_LEDGER.md + analysis_result.json
  → workspace/formula_candidates.json + parameter_candidates.json + model_ledger.json
  → workspace/EXPERIMENT_PLAN.md + experiment_plan_validation.json
  → workspace/verified_candidates.json + VERIFIED_CANDIDATES.md
  → experiments/<experiment_id>/...
  → outputs/<timestamp>_<project>/...
  → outputs/<timestamp>_<project>/manifest.json
  → workspace/inspect_summary.json
  → workspace/repair_plan.json + run_comparison.json
  → workspace/repair_dry_run.json + REPAIR_DRY_RUN.md
  → benchmarks/runs/<timestamp>_<task>/benchmark_result.json
  → benchmarks/runs/<timestamp>_<suite>_suite/benchmark_suite_result.json
  → benchmarks/runs/benchmark_index.json + benchmark_index.md
  → reports/report.md
  → handoff/*.md
```

## Design constraints

- No real LLM calls by default.
- Real provider calls require explicit opt-in and environment-backed secrets.
- No heavy web framework.
- Timestamped run directories prevent overwrites.
- All generated scientific claims must be marked as candidate/placeholder unless verified.
- Benchmark outputs describe workflow evidence only and must not claim paper reproduction success.
