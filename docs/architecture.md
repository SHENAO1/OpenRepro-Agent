# Architecture

OpenRepro-Agent v1.55.0 uses a small modular CLI architecture.

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
- `asset_build.py`: asset-centric incremental build planning and guarded safe materialization through the workflow executor.
- `artifact_cache.py`: local content-addressed cache for observed project artifacts and cache validation.
- `artifact_cache_remote.py`: local remote cache configuration, push/pull transfer, and restore planning.
- `api_usage.py`: mock/cached usage record and summary schema.
- `provider.py`: provider interface, deterministic mock provider, opt-in OpenAI-compatible provider, and request-hash cache.
- `data_profile.py`: registered data profiling and lightweight schema warnings for CSV, TSV, JSON, and JSONL.
- `dataset_card.py`: dataset card generation and lightweight data quality gates over registered data.
- `evidence_explorer.py`: static reviewer-facing evidence explorer for lineage, claims, data, runs, and artifact links.
- `evidence_query.py`: searchable evidence query artifacts over explorer claims, lineage nodes, runs, data, and artifact links.
- `candidate_review.py`: candidate listing and human review lifecycle.
- `experiment_scaffold.py`: human-gated experiment scaffolds from candidate evidence.
- `experiment_runner.py`: controlled execution for verified experiment scaffolds.
- `benchmark_runner.py`: workflow-compliance benchmark and benchmark-suite execution.
- `openrepro_bench_lite.py`: built-in curated OpenRepro-Bench Lite task pack and summary generation.
- `inspector.py`: project observability summary for humans and agents.
- `diagnostics.py`: failure classification and repair suggestions.
- `agent_adapter.py`: externally supervised agent runner adapter specs, validation, and trajectory handoff logs.
- `agent_sandbox.py`: approved local sandbox execution for safe agent execution-plan steps.
- `ci_integration.py`: GitHub Actions workflow scaffolding and local CI configuration validation.
- `local_ui.py`: static local UI generation for workflow, asset, experiment, review, agent, and CI navigation.
- `repair.py`: advisory repair plan generation.
- `repro_lock.py`: reproducibility lockfile generation and validation for config, data, dependencies, and experiment contracts.
- `run_compare.py`: run metric and manifest comparison.
- `run_index.py`: run-output indexing, static run explorer generation, and indexed run comparisons.
- `experiment_tracking.py`: experiment-level tracking over indexed runs, metrics, quality gates, specs, and inputs.
- `experiment_evaluation.py`: metric threshold evaluation suites and experiment leaderboards.
- `lineage.py`: run lineage hashes for manifests, configs, source index, and verified candidates.
- `pipeline_spec.py`: declarative pipeline spec export, planning, validation, and refresh helper.
- `plugin_registry.py`: declarative plugin/provider extension registry and validation without dynamic code loading.
- `promotion.py`: promotion gate planning, dry-run recording, and release-state registry artifacts.
- `github_pr_summary.py`: local GitHub PR comment summary generation from project evidence and local git metadata.
- `security_policy.py`: local security policy initialization and static audit checks for likely secrets and workflow guardrails.
- `golden_path.py`: one-command starter workflow over the packaged random-search toy paper example.
- `integrations.py`: MLflow, Aim, DVC, and Hydra adapter exports plus supervised execution plans.
- `workflow_registry.py`: registered workflow DAG metadata, state generation, step explanation, and safe derived-step execution.
- `workflow_preset.py`: goal-oriented workflow preset plans over the registered DAG.
- `workflow_executor.py`: durable workflow execution sessions with events, logs, retries, and output hashes.
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
  → workspace/dataset_card.json + DATASET_CARD.md
  → workspace/data_quality_gate.json + DATA_QUALITY_GATE.md
  → experiments/<experiment_id>/...
  → openrepro.lock.json + workspace/repro_lock_validation.json
  → outputs/<timestamp>_<project>_<experiment_id>/...
  → outputs/<timestamp>_<project>/...
  → outputs/<timestamp>_<project>/manifest.json
  → workspace/inspect_summary.json
  → workspace/repair_plan.json + run_comparison.json
  → workspace/repair_dry_run.json + REPAIR_DRY_RUN.md
  → workspace/experiment_tracking.json + EXPERIMENT_TRACKING.md
  → workspace/evaluation_results.json + EXPERIMENT_LEADERBOARD.md
  → workspace/run_lineage.json + RUN_LINEAGE.md
  → workspace/agent_adapter.json + agent_trajectory.jsonl
  → workspace/agent_sandbox_run.json + agent_sandbox_trajectory.jsonl
  → .github/workflows/openrepro-ci.yml + workspace/ci_validation.json
  → openrepro.plugins.yaml + workspace/plugin_registry.json + plugin_validation.json
  → workspace/promotion_plan.json + promotion_registry.json
  → workspace/github_pr_summary.json + reports/pr_comment.md
  → workspace/security_policy.json + security_audit.json
  → workspace/golden_path.json + GOLDEN_PATH.md
  → integrations/* + workspace/integrations.json + INTEGRATIONS.md
  → workspace/integration_execution.json + INTEGRATION_EXECUTION.md
  → reports/evidence_explorer/index.html
  → workspace/evidence_query.json + EVIDENCE_QUERY.md
  → reports/local_ui/index.html + workspace/local_ui_summary.json
  → workspace/workflow_preset.json + WORKFLOW_PRESET.md
  → workspace/workflow_execution.json + workflow_events.jsonl
  → openrepro.pipeline.yaml + workspace/pipeline_plan.json + pipeline_validation.json
  → workspace/asset_catalog.json + ASSET_CATALOG.md
  → workspace/asset_build_plan.json + ASSET_BUILD_PLAN.md
  → workspace/artifact_cache.json + ARTIFACT_CACHE.md
  → workspace/artifact_cache_remotes.json + cache_restore_plan.json
  → benchmarks/runs/<timestamp>_<task>/benchmark_result.json
  → benchmarks/runs/<timestamp>_<suite>_suite/benchmark_suite_result.json
  → benchmarks/runs/benchmark_index.json + benchmark_index.md
  → benchmarks/openrepro_bench_lite/openrepro_bench_lite_summary.json + OPENREPRO_BENCH_LITE_SUMMARY.md
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
