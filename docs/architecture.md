# Architecture

OpenRepro-Agent v0.2.0 uses a small modular CLI architecture.

## Modules

- `cli.py`: Typer command definitions and user-facing output.
- `project_manager.py`: project initialization and status checks.
- `document_loader.py`: source ingestion, PDF extraction, and source index management.
- `analyzer.py`: rule-based candidate analysis.
- `planner.py`: experiment plan generation and validation.
- `demo_runner.py`: lightweight BOC-like signal demo and parameter sweep.
- `artifact_manager.py`: run directory, artifact manifest, and validation utilities.
- `api_usage.py`: mock usage record and summary schema.
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
  → outputs/<timestamp>_<project>/...
  → outputs/<timestamp>_<project>/manifest.json
  → reports/report.md
  → handoff/*.md
```

## Design constraints

- No real LLM calls by default.
- No heavy web framework.
- Timestamped run directories prevent overwrites.
- All generated scientific claims must be marked as candidate/placeholder unless verified.
