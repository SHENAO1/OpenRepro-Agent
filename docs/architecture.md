# Architecture

OpenRepro-Agent v0.1.0 uses a small modular CLI architecture.

## Modules

- `cli.py`: Typer command definitions and user-facing output.
- `project_manager.py`: project initialization and status checks.
- `document_loader.py`: source ingestion and source index management.
- `analyzer.py`: rule-based/mock analysis.
- `planner.py`: experiment plan generation.
- `demo_runner.py`: lightweight BOC-like signal demo.
- `artifact_manager.py`: run directory and artifact path utilities.
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
  → workspace/EXPERIMENT_PLAN.md
  → outputs/<timestamp>_<project>/...
  → reports/report.md
  → handoff/*.md
```

## Design constraints

- No real LLM calls by default.
- No heavy web framework.
- Timestamped run directories prevent overwrites.
- All generated scientific claims must be marked as candidate/placeholder unless verified.
