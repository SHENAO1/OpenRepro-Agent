# OpenRepro-Agent

[English](README.md) | [简体中文](README.zh-CN.md)

OpenRepro-Agent is a Python CLI for building auditable paper-reproduction workspaces. It helps you ingest sources, extract candidate evidence, scaffold guarded experiments, run toy or verified workflows, validate artifacts, and package results for human or agent handoff.

Current version: **v1.56.0**. This is an alpha engineering scaffold, not an autonomous paper-reproduction system.

## Why

Paper reproduction often fails because notes, formulas, assumptions, datasets, code, logs, and review decisions are scattered across folders and chat histories. OpenRepro-Agent keeps those materials in one reproducible project layout and marks what is verified, missing, stale, or still human-reviewed.

## Highlights

- Reproducible project layout for paper notes, configs, data, experiments, outputs, reports, and handoff files.
- Markdown, text, and PDF ingestion with source provenance.
- Rule-based formula and parameter candidate extraction.
- Human-gated candidate review before experiment scaffolding.
- Experiment specs, input validation, run manifests, quality gates, and run comparisons.
- Dataset cards, lightweight data quality gates, lineage, claim traceability, readiness reviews, and evidence packages.
- Static review surfaces including dashboard, evidence explorer, and reproduction cockpit.
- Mock provider by default, with explicit opt-in OpenAI-compatible API support.
- Built-in starter workflow and OpenRepro-Bench Lite for repeatable workflow checks.

## Install

```bash
git clone https://github.com/SHENAO1/OpenRepro-Agent.git
cd OpenRepro-Agent

python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.10+ is required.

## Quick Start

Run the packaged random-search toy paper workflow:

```bash
openrepro start random_search_demo
```

This creates a project, ingests packaged notes, analyzes candidate formulas and parameters, scaffolds a guarded experiment, runs it, evaluates the quality gate, and writes report/handoff artifacts.

Useful next commands:

```bash
openrepro status random_search_demo
openrepro cockpit build random_search_demo --zip
openrepro evidence-package random_search_demo --zip
openrepro bench-lite
```

The output is workflow evidence and toy execution evidence only. It is not a claim that a paper has been reproduced.

## API Configuration

OpenRepro uses a deterministic mock provider by default. Real API calls are disabled unless you explicitly enable them and provide a key through an environment variable.

Mock mode:

```bash
openrepro configure-provider random_search_demo --provider mock --disable-real-api
```

OpenAI-compatible API:

```bash
openrepro configure-provider random_search_demo \
  --provider openai \
  --model gpt-4.1-mini \
  --enable-real-api \
  --api-key-env OPENAI_API_KEY \
  --endpoint https://api.openai.com/v1/chat/completions
```

Set the key before running commands that make real provider calls:

```bash
export OPENAI_API_KEY="<your-api-key>"
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
```

For a third-party OpenAI-compatible Base URL, pass the full chat completions endpoint. If the provider gives `https://example.com/v1`, configure `https://example.com/v1/chat/completions`.

Token Plan example:

```powershell
$env:OPENREPRO_API_KEY = "<your-token-plan-api-key>"
openrepro configure-provider random_search_demo `
  --provider openai `
  --model mimo-v2.5 `
  --enable-real-api `
  --api-key-env OPENREPRO_API_KEY `
  --endpoint https://token-plan-cn.xiaomimimo.com/v1/chat/completions
```

OpenRepro stores the provider name, model name, endpoint, cache policy, redaction policy, and API-key environment variable name in `project_config.yaml`. It does **not** store API key values.

## Core Workflow

For a manual project, the usual path is:

```bash
openrepro init my_repro
openrepro ingest my_repro --source path/to/paper_or_notes.pdf
openrepro analyze my_repro
openrepro plan my_repro
openrepro list-candidates my_repro
openrepro approve-candidates my_repro --all --reviewer human
openrepro scaffold-experiment my_repro --experiment-id baseline --template basic
openrepro validate-experiment-spec my_repro --experiment-id baseline
openrepro run-experiment my_repro --experiment-id baseline --confirm
openrepro quality-gate my_repro --all
openrepro evidence-package my_repro --zip
```

Use `openrepro --help` and `openrepro <command> --help` for the full command reference.

## Important Outputs

- `workspace/`: analysis, candidate review, data quality, lineage, readiness, and workflow status artifacts.
- `experiments/`: guarded experiment scaffolds and experiment specs.
- `outputs/`: timestamped run outputs, metrics, logs, manifests, and quality gates.
- `reports/`: report, dashboard, evidence package, review site, and cockpit artifacts.
- `handoff/`: files for human maintainers and coding agents.
- `benchmarks/`: workflow-compliance benchmark tasks and indexes.

## Documentation

- [Roadmap](ROADMAP.md)
- [Architecture](docs/architecture.md)
- [Developer guide](docs/developer_guide.md)
- [API usage policy](API_USAGE.md)
- [Contributing](CONTRIBUTING.md)

## Current Limits

OpenRepro-Agent does not fully read or understand papers, verify mathematical formulas automatically, verify dataset semantics automatically, generate complete simulation code for arbitrary papers, or claim scientific reproduction success. Human review is required for formulas, parameters, data semantics, implementation choices, and final reproduction claims.

## No Fabricated Results Policy

The project must not fabricate benchmark results, user counts, token usage, cost estimates, accuracy improvements, efficiency improvements, or claims that a lightweight demo is a complete paper reproduction.

## License

MIT
