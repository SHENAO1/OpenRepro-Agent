# OpenRepro-Agent

OpenRepro-Agent is a Python CLI workflow for paper reproduction projects. It initializes a reproducible workspace, ingests Markdown/txt/PDF sources, extracts candidate formulas and parameters, plans experiments, runs lightweight demos and parameter sweeps, validates generated artifacts, inspects project state, runs workflow-compliance benchmarks, indexes benchmark evidence, classifies failures, tracks cache-aware mock API usage, and produces multi-agent handoff files.

Current version: **v0.3.1**. This is still an alpha engineering scaffold, not a finished autonomous paper-reproduction system.

## Why this project exists

Research-paper reproduction often fails because notes, assumptions, formulas, experiment code, logs, and reports are scattered across folders or chat histories. OpenRepro-Agent focuses on making the project loop runnable, inspectable, and auditable before adding more ambitious automation.

The v0.3.1 workflow is:

```text
init → ingest → analyze → plan → run-demo → validate --all → inspect → diagnose → run-sweep → benchmark → benchmark-index → report → handoff → status
```

## What v0.3.1 supports

- Create a standard paper reproduction project directory.
- Ingest Markdown and text notes into `sources/`.
- Ingest PDFs, extract text and page-level provenance with `pdfplumber`, and record extraction status.
- Generate `paper_summary.md` using rule-based keyword detection and candidate extraction.
- Generate Markdown and JSON model ledgers with formula and parameter candidates marked `candidate_unverified`.
- Generate `EXPERIMENT_PLAN.md` and `experiment_plan_validation.json`.
- Run a lightweight BOC-like signal and autocorrelation demo.
- Run a noise/seed parameter sweep for the built-in demo.
- Save run artifacts: logs, figures, data, metrics, reports, config snapshots, metadata, manifest, mock API usage, and handoff notes.
- Validate run manifests, required artifacts, file sizes, and SHA-256 hashes.
- Validate every project run at once with `openrepro validate --all`.
- Inspect project state and write `workspace/inspect_summary.json`.
- Diagnose common workflow failures and suggest repairs.
- Run workflow-compliance benchmark tasks from `benchmarks/benchmark_schema.json`.
- Generate `benchmark_index.json` and `benchmark_index.md` for benchmark runs.
- Use a deterministic mock provider interface with request-hash cache accounting.
- Generate a project-level Markdown report.
- Generate multi-agent handoff files for Claude Code, Codex, GitHub Copilot, or human maintainers.
- Run pytest tests for the minimum workflow.

## What v0.3.1 does not support

- It does not fully read or understand papers.
- It does not verify mathematical formulas automatically.
- It does not generate full simulation code for arbitrary papers.
- It does not automatically repair failed experiments.
- It does not implement real LLM providers; v0.3.1 ships the provider interface and mock provider only.
- It does not claim benchmark scores, user counts, token usage, or efficiency improvements.
- The BOC demo is a **lightweight BOC-like demo**, not a complete BOC acquisition/tracking implementation and not a full reproduction of any paper.

## Installation

```bash
git clone <your-fork-url> OpenRepro-Agent
cd OpenRepro-Agent

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

Python 3.10+ is required.

## Testing

Run the unit test suite:

```bash
python -m pytest -q
```

On Windows, if pytest cannot access its default temp directory, use a workspace-local base temp directory:

```powershell
New-Item -ItemType Directory -Force .codex_tmp\pytest-basetemp | Out-Null
python -m pytest -q --basetemp .codex_tmp\pytest-basetemp
```

## CLI quick start

```bash
openrepro init boc_demo
openrepro ingest boc_demo --source examples/boc_notes.md
openrepro analyze boc_demo
openrepro plan boc_demo
openrepro run-demo boc_demo
openrepro validate boc_demo
openrepro validate boc_demo --all
openrepro inspect boc_demo
openrepro diagnose boc_demo
openrepro run-sweep boc_demo --noise-std 0.0 --noise-std 0.1 --seed 42
openrepro validate boc_demo
openrepro benchmark --task benchmarks/sample_task.json --project boc_benchmark
openrepro benchmark-index
openrepro report boc_demo
openrepro handoff boc_demo
openrepro status boc_demo
```

PDF ingestion is also supported:

```bash
openrepro ingest boc_demo --source path/to/paper.pdf
```

PDF text is extracted to:

```text
workspace/extracted_sources/<paper>.txt
workspace/extracted_sources/<paper>.pages.json
```

## Command overview

### `openrepro init <project_name>`

Creates:

```text
boc_demo/
  project_config.yaml
  sources/
  workspace/
  outputs/
  handoff/
  reports/
  logs/
```

It also creates initial handoff files:

```text
handoff/PROJECT_CONTEXT.md
handoff/AGENT_HANDOFF.md
handoff/NEXT_STEPS.md
```

### `openrepro ingest <project_name> --source <path>`

Copies Markdown/txt/PDF sources into `sources/` and updates:

```text
workspace/source_index.json
```

For PDFs, v0.3.1 records:

- `extraction_status`
- `extracted_text_path`
- `pages_path`
- `page_count`
- `char_count`
- `table_count`

Extraction failures do not remove the copied source. They are recorded as `extraction_failed` so the rest of the workflow can continue.

### `openrepro analyze <project_name>`

Generates:

```text
workspace/paper_summary.md
workspace/MODEL_LEDGER.md
workspace/analysis_result.json
workspace/formula_candidates.json
workspace/parameter_candidates.json
workspace/model_ledger.json
```

The analyzer is rule-based. Formula, parameter, and model records are candidates and require human verification.

### `openrepro plan <project_name>`

Generates:

```text
workspace/EXPERIMENT_PLAN.md
workspace/experiment_plan_validation.json
```

The validation file checks whether sources exist, PDF extraction needs review, candidate formulas/parameters were detected, and demo configuration values are valid.

### `openrepro run-demo <project_name>`

Creates a timestamped output directory, for example:

```text
outputs/2026-xx-xx_20-30-15_boc_demo/
  logs/run.log
  figures/correlation.png
  data/demo_signal.npy
  data/correlation.npy
  data/demo_metrics.json
  reports/demo_report.md
  configs/project_config_snapshot.yaml
  code/README.md
  api_usage/api_usage.jsonl
  api_usage/api_usage_summary.json
  handoff/AGENT_HANDOFF.md
  metadata.json
  manifest.json
```

The demo generates a pseudo-random spreading code, a square-wave subcarrier, a lightweight BOC-like signal, a noisy observation, and a normalized autocorrelation function.

### `openrepro validate <project_name> [--run-dir PATH]`

Validates the latest run directory by default, or a specific run directory when `--run-dir` is provided.

It checks:

- `manifest.json` exists and is readable
- required artifacts exist
- manifest entries match current file size
- manifest entries match current SHA-256 hashes

The command exits with code `0` when valid and code `1` when validation fails.

Use `--all` to validate every run under `outputs/` in one pass:

```bash
openrepro validate boc_demo --all
```

The all-runs mode prints a table and includes diagnosis suggestions for any failed run.

### `openrepro inspect <project_name>`

Prints a compact project health table covering sources, PDF extraction status, formula and parameter candidate counts, run counts, the latest manifest status, benchmark run count, diagnosis health, and the next suggested command.

It also writes:

```text
workspace/inspect_summary.json
```

The JSON summary is intended for agents and automation that need the same state snapshot without parsing terminal output.

### `openrepro diagnose <project_name> [--run-dir PATH]`

Classifies project or run failures and suggests repairs. It covers missing artifacts, manifest mismatches, missing source files, PDF extraction failures, invalid demo config, provider-disabled errors, and unknown runtime errors.

### `openrepro run-sweep <project_name> [--noise-std FLOAT]... [--seed INT]...`

Runs the built-in BOC-like demo across a noise/seed grid. Defaults:

```text
noise_std = [0.0, 0.05, 0.1, 0.2]
seed = project_config.yaml demo.seed
```

Outputs include:

```text
data/sweep_results.json
data/sweep_metrics.csv
figures/sweep_correlation_peak.png
reports/sweep_report.md
metadata.json
manifest.json
```

### `openrepro benchmark --task <task.json> [--project <project_name>]`

Runs a workflow-compliance benchmark task. If `--project` is omitted, the task id becomes the project name. If the project does not exist, it is initialized automatically.

Outputs are written under:

```text
benchmarks/runs/<timestamp>_<task_id>/
  benchmark_result.json
  benchmark_report.md
  api_usage/api_usage.jsonl
  api_usage/api_usage_summary.json
  manifest.json
```

Benchmark results only report observed workflow evidence: source ingestion, generated artifacts, manifest validity, and metric availability. They do not claim paper reproduction success or scientific benchmark scores.

Benchmark task files may use either the v0.3.0 fields (`expected_artifacts`, `evaluation_metrics`) or the v0.3.1 fields:

```json
{
  "artifacts": {
    "required": ["workspace/paper_summary.md"],
    "optional": ["outputs/<timestamp>_<project>/reports/demo_report.md"]
  },
  "metrics": {
    "required": ["signal_length"],
    "optional": ["side_lobe_level"]
  },
  "workflow": {
    "run_demo": true,
    "run_sweep": false
  },
  "pass_criteria": {
    "require_manifest_valid": true
  }
}
```

Optional artifacts and metrics are reported but do not make the benchmark status fail.

### `openrepro benchmark-index [--runs-dir PATH]`

Rebuilds benchmark indexes for existing benchmark runs:

```text
benchmarks/runs/benchmark_index.json
benchmarks/runs/benchmark_index.md
```

The index includes task id, status, creation time, benchmark directory, project directory, latest run directory, artifact pass count, metric pass count, manifest validity, and diagnosis count. It is regenerated automatically after every benchmark run.

### `openrepro report <project_name>`

Generates:

```text
reports/report.md
```

### `openrepro handoff <project_name>`

Generates or updates:

```text
handoff/PROJECT_CONTEXT.md
handoff/PAPER_SUMMARY.md
handoff/MODEL_LEDGER.md
handoff/EXPERIMENT_PLAN.md
handoff/CODE_STATUS.md
handoff/RUN_LOG_SUMMARY.md
handoff/ERROR_NOTES.md
handoff/NEXT_STEPS.md
handoff/AGENT_HANDOFF.md
```

### `openrepro status <project_name>`

Prints whether the project exists, whether each workflow stage has completed, the most recent run directory, report status, handoff completeness, and the next suggested command.

## Artifact manifest design

Each demo, sweep, or benchmark run writes:

```text
manifest.json
```

The manifest records:

- schema version
- OpenRepro-Agent version
- run id
- command type
- created timestamp
- required artifacts
- relative artifact paths
- artifact category
- existence flag
- file size
- SHA-256 digest

This lets later agents, humans, and CI checks verify that reports and metrics are backed by actual files.

## Provider and API Usage design

v0.3.1 does **not** implement real API providers. It ships a provider interface, a deterministic `MockProvider`, request-hash caching, and mock usage files to preserve the accounting schema:

```text
api_usage/api_usage.jsonl
api_usage/api_usage_summary.json
```

Mock and cached events use zero prompt tokens, zero completion tokens, zero total tokens, and zero estimated cost. The summary keeps `total_calls` at zero for mocked and cached events so the project does not invent real API usage.

Future versions can add real providers while tracking:

- provider and model
- task type
- prompt/completion/total tokens
- estimated cost
- cache hit status
- call status
- request hash

## Multi-Agent Handoff

The `handoff/` directory is designed for both humans and coding agents. It separates project context, paper summary, model ledger, experiment plan, code status, run logs, error notes, next steps, and the final handoff memo.

Important rule: handoff files must distinguish between confirmed facts, assumptions, placeholders, candidates, and future work.

## Benchmark policy

The `benchmarks/` directory contains a task schema, a sample task, generated benchmark run outputs, and a rebuildable benchmark index. v0.3.1 reports workflow-compliance evidence only. It does not report scientific benchmark scores or claim a paper has been reproduced.

## Roadmap snapshot

- v0.1.0: runnable CLI workflow and lightweight BOC-like demo.
- v0.2.0: PDF text extraction, artifact manifests, formula/parameter candidates, experiment plan validation, demo parameter sweeps.
- v0.3.0: provider interface, cache-aware API usage, benchmark runner, failure diagnosis and repair suggestions.
- v0.3.1: project inspection, `validate --all`, benchmark indexing, and compatible benchmark schema hardening.
- v0.4.0: opt-in real provider implementations and richer paper-to-code workflows.

See `ROADMAP.md` for details.

## Disclaimer

OpenRepro-Agent v0.3.1 is an engineering scaffold for reproducibility workflows. It should not be used to claim that a paper has been reproduced unless the user has independently verified formulas, parameters, code, data, and outputs.

## No fabricated results policy

This project must not fabricate:

- benchmark results
- user counts
- token usage
- cost estimates
- accuracy or efficiency improvements
- claims that a lightweight demo is a complete paper reproduction

Only actual generated artifacts should be reported.
