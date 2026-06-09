# OpenRepro-Agent

OpenRepro-Agent is a Python CLI for building auditable paper-reproduction workspaces. It helps you keep paper notes, candidate formulas, experiment scaffolds, run evidence, validation outputs, and handoff files in one reproducible project layout.

Current version on `main`: **v1.26.0**. This is an alpha engineering scaffold, not an autonomous paper-reproduction system.

## Why

Paper reproduction often fails because notes, assumptions, formulas, datasets, code, logs, and review decisions are scattered across folders or chat histories. OpenRepro-Agent focuses on making the reproduction workflow runnable, inspectable, and explicit about what is verified, missing, stale, or still waiting for human review.

## Highlights

- Project layout for sources, configs, data, experiments, outputs, reports, and handoff files.
- Markdown, text, and PDF ingestion with source provenance.
- Rule-based formula and parameter candidate extraction.
- Human-gated candidate approval before experiment scaffolding.
- Experiment specs, input validation, run manifests, quality gates, and run comparisons.
- Data registration, run lineage, claim traceability, readiness scorecards, and evidence packages.
- Static review artifacts such as review site, dashboard, reviewer packet, and collaboration pack.
- Mock provider by default, with explicit opt-in OpenAI-compatible API support.
- Workflow-compliance benchmark runner and benchmark-suite support.

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

Run a small local workflow with the bundled BOC-style notes:

```bash
openrepro init boc_demo
openrepro configure-provider boc_demo --provider mock --disable-real-api
openrepro ingest boc_demo --source examples/boc_notes.md
openrepro analyze boc_demo
openrepro plan boc_demo
openrepro list-candidates boc_demo
openrepro approve-candidates boc_demo --all --reviewer human
openrepro scaffold-experiment boc_demo --experiment-id boc_candidate_exp --template boc-like
openrepro validate-inputs boc_demo --experiment-id boc_candidate_exp
openrepro validate-experiment-spec boc_demo --experiment-id boc_candidate_exp
openrepro run-experiment boc_demo --experiment-id boc_candidate_exp --confirm
openrepro quality-gate boc_demo --all
openrepro evidence-package boc_demo --zip
openrepro status boc_demo
```

The output is workflow evidence and toy execution evidence only. It is not a claim that a paper has been reproduced.

## API Configuration

OpenRepro uses a deterministic mock provider by default. Real API calls are disabled unless you explicitly enable them and provide a key through an environment variable.

Mock mode:

```bash
openrepro configure-provider boc_demo --provider mock --disable-real-api
```

OpenAI-compatible API:

```bash
openrepro configure-provider boc_demo \
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
openrepro configure-provider boc_demo `
  --provider openai `
  --model mimo-v2.5 `
  --enable-real-api `
  --api-key-env OPENREPRO_API_KEY `
  --endpoint https://token-plan-cn.xiaomimimo.com/v1/chat/completions
```

OpenRepro stores the provider name, model name, endpoint, cache policy, redaction policy, and API-key environment variable name in `project_config.yaml`. It does **not** store API key values.

## Important Outputs

- `workspace/`: analysis, candidate review, validation, lineage, readiness, and workflow status artifacts.
- `experiments/`: guarded experiment scaffolds and experiment specs.
- `outputs/`: timestamped run outputs, metrics, logs, manifests, and quality gates.
- `reports/`: reports, evidence packages, dashboards, and review artifacts.
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
