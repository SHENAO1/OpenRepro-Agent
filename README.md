# OpenRepro-Agent

OpenRepro-Agent is a minimal Python CLI workflow for paper reproduction projects: it initializes a reproducible workspace, ingests paper notes, creates a rule-based summary and model ledger, generates an experiment plan, runs a lightweight demo, saves artifacts, writes reports, tracks mock API usage, and produces multi-agent handoff files.

Current version: **v0.1.0**. This is an alpha engineering scaffold, not a finished autonomous paper-reproduction system.

## Why this project exists

Research-paper reproduction often fails because notes, assumptions, formulas, experiment code, logs, and reports are scattered across folders or chat histories. OpenRepro-Agent v0.1.0 focuses on one practical goal: make the end-to-end project loop runnable and inspectable before adding more ambitious automation.

The v0.1.0 workflow is:

```text
init → ingest → analyze → plan → run-demo → report → handoff → status
```

## What v0.1.0 supports

- Create a standard paper reproduction project directory.
- Ingest Markdown and text notes into `sources/`.
- Copy PDF files as placeholders with an explicit limitation message.
- Generate `paper_summary.md` using rule-based keyword detection and mock analysis.
- Generate `MODEL_LEDGER.md` with model candidates, variables, equation placeholders, and verification status.
- Generate `EXPERIMENT_PLAN.md`.
- Run a lightweight BOC-like signal and autocorrelation demo.
- Save run artifacts: logs, figures, NumPy data, metrics, reports, config snapshot, metadata, mock API usage, and handoff notes.
- Generate a project-level Markdown report.
- Generate multi-agent handoff files for Claude Code, Codex, GitHub Copilot, or human maintainers.
- Run pytest tests for the minimum workflow.

## What v0.1.0 does not support

- It does not fully read or understand papers.
- It does not extract text from PDFs.
- It does not automatically extract verified mathematical formulas.
- It does not generate full simulation code for arbitrary papers.
- It does not automatically repair failed experiments.
- It does not call real LLM APIs by default.
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
openrepro report boc_demo
openrepro handoff boc_demo
openrepro status boc_demo
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

Existing project directories are not overwritten.

### `openrepro ingest <project_name> --source <path>`

Copies Markdown/txt sources into `sources/` and updates:

```text
workspace/source_index.json
```

PDF files are copied as placeholders. v0.1.0 does not extract PDF text.

### `openrepro analyze <project_name>`

Generates:

```text
workspace/paper_summary.md
workspace/MODEL_LEDGER.md
workspace/analysis_result.json
```

The analyzer is rule-based and mock-only. It is meant to create a reviewable scaffold, not verified scientific conclusions.

### `openrepro plan <project_name>`

Generates:

```text
workspace/EXPERIMENT_PLAN.md
```

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
```

The demo generates a pseudo-random spreading code, a square-wave subcarrier, a lightweight BOC-like signal, a noisy observation, and a normalized autocorrelation function.

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

Prints whether the project exists, whether each workflow stage has completed, the most recent demo run directory, report status, handoff completeness, and the next suggested command.

## Output directory design

Project-level files live under `workspace/`, `reports/`, and `handoff/`. Each demo run is isolated under `outputs/<timestamp>_<project>/` so that repeated experiments do not overwrite one another.

This design allows future versions to add parameter sweeps, benchmark runs, and regression comparisons without losing prior artifacts.

## API Usage design

v0.1.0 does **not** call real APIs by default. It writes mock usage files to preserve the accounting schema:

```text
api_usage/api_usage.jsonl
api_usage/api_usage_summary.json
```

Mock events use zero prompt tokens, zero completion tokens, zero total tokens, and zero estimated cost. The summary keeps `total_calls` at zero for mocked events so the project does not invent real API usage.

Future versions can add real providers while tracking:

- provider and model
- task type
- prompt/completion/total tokens
- estimated cost
- cache hit status
- call status

## Multi-Agent Handoff

The `handoff/` directory is designed for both humans and coding agents. It separates project context, paper summary, model ledger, experiment plan, code status, run logs, error notes, next steps, and the final handoff memo.

Important rule: handoff files must distinguish between confirmed facts, assumptions, placeholders, and future work.

## Benchmark plan

The `benchmarks/` directory currently contains only a schema and a sample task. v0.1.0 does not report benchmark results. Future versions may add a benchmark runner that executes defined reproduction tasks and records actual metrics from actual runs.

## Roadmap snapshot

- v0.1.0: runnable CLI workflow and lightweight BOC-like demo.
- v0.2.0: PDF text extraction, formula candidates, parameter extraction, richer experiment plans.
- v0.3.0: real LLM provider interfaces, cache-aware API usage, benchmark runner, experiment repair loop.

See `ROADMAP.md` for details.

## Disclaimer

OpenRepro-Agent v0.1.0 is an engineering scaffold for reproducibility workflows. It should not be used to claim that a paper has been reproduced unless the user has independently verified formulas, parameters, code, data, and outputs.

## No fabricated results policy

This project must not fabricate:

- benchmark results
- user counts
- token usage
- cost estimates
- accuracy or efficiency improvements
- claims that a lightweight demo is a complete paper reproduction

Only actual generated artifacts should be reported.
