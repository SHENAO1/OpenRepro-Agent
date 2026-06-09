# OpenRepro-Agent

[English](README.md) | [简体中文](README.zh-CN.md)

OpenRepro-Agent is a Python CLI for building auditable paper-reproduction workspaces. It keeps notes, evidence, experiments, outputs, reports, and handoff files in one project layout so humans and supervised agents can continue work without losing provenance.

Current version: **v1.58.0**. This is an alpha engineering scaffold, not an autonomous paper-reproduction system.

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

Run the packaged demo workflow:

```bash
openrepro start random_search_demo
openrepro status random_search_demo
openrepro cockpit build random_search_demo --zip
```

Useful review and handoff commands:

```bash
openrepro evidence-graph random_search_demo
openrepro agent-task-spec random_search_demo
openrepro evidence-package random_search_demo --zip
openrepro bench-lite
```

The demo produces workflow evidence and toy execution evidence. It does not prove that a paper has been reproduced.

## Manual Workflow

```bash
openrepro init my_repro
openrepro ingest my_repro --source path/to/paper_or_notes.pdf
openrepro analyze my_repro
openrepro plan my_repro
openrepro approve-candidates my_repro --all --reviewer human
openrepro scaffold-experiment my_repro --experiment-id baseline --template basic
openrepro run-experiment my_repro --experiment-id baseline --confirm
openrepro quality-gate my_repro --all
openrepro evidence-package my_repro --zip
```

Use `openrepro --help` and `openrepro <command> --help` for the full command list.

## Notes

- Real model API calls are disabled by default. OpenRepro uses a deterministic mock provider unless a real provider is explicitly configured.
- API keys are read from environment variables and are not stored in project files.
- Human review is still required for formulas, parameters, dataset meaning, implementation choices, and final reproduction claims.
- Do not fabricate benchmark results, usage numbers, cost estimates, accuracy gains, or reproduction success claims.

## Documentation

- [Roadmap](ROADMAP.md)
- [Architecture](docs/architecture.md)
- [Developer guide](docs/developer_guide.md)
- [API usage policy](API_USAGE.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT
