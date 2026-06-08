# Architecture

OpenRepro-Agent v1.37.0 uses a small modular CLI architecture.

## Modules

- `cli.py`: Typer command definitions and user-facing output.
- `project_manager.py`: project initialization and status checks.
- `document_loader.py`: source ingestion, PDF extraction, and source index management.
- `analyzer.py`: rule-based candidate analysis.
- `planner.py`: experiment plan generation and validation.
- `approval.py`: human approval artifacts for formula and parameter candidates.
- `demo_runner.py`: lightweight BOC-like signal demo and parameter sweep.
- `artifact_manager.py`: run directory, artifact manifest, and validation utilities.
- `asset_catalog.py`: unified source, data, experiment, run, report, handoff, workspace, and config asset catalog.
- `api_usage.py`: mock/cached usage record and summary schema.
- `provider.py`: provider interface, deterministic mock provider, opt-in OpenAI-compatible provider, and request-hash cache.
- `data_profile.py`: registered data profiling and lightweight schema warnings for CSV, TSV, JSON, and JSONL.
- `evidence_explorer.py`: static reviewer-facing evidence explorer for lineage, claims, data, runs, and artifact links.
- `evidence_query.py`: searchable evidence query artifacts over explorer claims, lineage nodes, runs, data, and artifact links.
- `candidate_review.py`: candidate listing and human review lifecycle.
- `experiment_scaffold.py`: human-gated experiment scaffolds from candidate evidence.
- `experiment_runner.py`: controlled execution for verified experiment scaffolds.
- `benchmark_runner.py`: workflow-compliance benchmark and benchmark-suite execution.
- `inspector.py`: project observability summary for humans and agents.
- `diagnostics.py`: failure classification and repair suggestions.
- `agent_adapter.py`: externally supervised agent runner adapter specs, validation, and trajectory handoff logs.
- `repair.py`: advisory repair plan generation.
- `repro_lock.py`: reproducibility lockfile generation and validation for config, data, dependencies, and experiment contracts.
- `run_compare.py`: run metric and manifest comparison.
- `run_index.py`: run-output indexing, static run explorer generation, and indexed run comparisons.
- `lineage.py`: run lineage hashes for manifests, configs, source index, and verified candidates.
- `pipeline_spec.py`: declarative pipeline spec export, planning, validation, and refresh helper.
- `workflow_registry.py`: registered workflow DAG metadata, state generation, step explanation, and safe derived-step execution.
- `workflow_preset.py`: goal-oriented workflow preset plans over the registered DAG.
- `report_generator.py`: project-level report creation.
- `handoff_generator.py`: multi-agent handoff generation.
- `config.py`: dataclass-based configuration defaults and YAML IO.
- `data_expectations.py`: lightweight data expectation suite generation and validation.
- `utils.py`: shared helper functions.

## Data flow

```text
sources/ + project_config.yaml
  → workspace/source_index.json
  → workspace/paper_summary.md + MODEL_LEDGER.md + analysis_result.json + paper_metadata.json
  → workspace/formula_candidates.json + parameter_candidates.json + model_ledger.json
  → workspace/EXPERIMENT_PLAN.md + experiment_plan_validation.json
  → workspace/candidate_reviews.json + CANDIDATE_REVIEWS.md
  → workspace/verified_candidates.json + VERIFIED_CANDIDATES.md
  → workspace/data_profile.json + DATA_PROFILE.md
  → workspace/data_expectations.json + DATA_EXPECTATION_RESULTS.md
  → experiments/<experiment_id>/...
  → openrepro.lock.json + workspace/repro_lock_validation.json
  → outputs/<timestamp>_<project>_<experiment_id>/...
  → outputs/<timestamp>_<project>/...
  → outputs/<timestamp>_<project>/manifest.json
  → workspace/inspect_summary.json
  → workspace/repair_plan.json + run_comparison.json
  → workspace/repair_dry_run.json + REPAIR_DRY_RUN.md
  → workspace/run_lineage.json + RUN_LINEAGE.md
  → workspace/agent_adapter.json + agent_trajectory.jsonl
  → reports/evidence_explorer/index.html
  → workspace/evidence_query.json + EVIDENCE_QUERY.md
  → workspace/workflow_preset.json + WORKFLOW_PRESET.md
  → openrepro.pipeline.yaml + workspace/pipeline_plan.json + pipeline_validation.json
  → workspace/asset_catalog.json + ASSET_CATALOG.md
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
