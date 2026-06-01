# Session State

Updated: 2026-06-01

## Current Goal

Release OpenRepro-Agent v0.4.0 with opt-in provider readiness, human-gated experiment scaffolds, benchmark suites, repair plans, run comparison, and release documentation.

## Current State

- The repository has the v0.4.0 Python CLI workflow in place.
- The local working directory started without a Git repository.
- No project-specific `AGENTS.md` or prior baton files were present.
- v0.4.0 keeps real APIs disabled by default and supports an explicit OpenAI-compatible provider path with environment-backed secrets.
- PDF ingestion extracts text and page provenance with `pdfplumber`.
- Demo, sweep, benchmark, and benchmark-suite runs write `manifest.json`; demo/sweep outputs can be checked with `openrepro validate` or `openrepro validate --all`.
- Benchmark runs and suites record workflow-compliance evidence only and update `benchmarks/runs/benchmark_index.*`.
- Project inspection writes `workspace/inspect_summary.json`.
- Experiment scaffolds write guarded files under `experiments/<id>/`.
- Repair plans and run comparisons write machine-readable workspace artifacts.

## Latest Evidence

- Unit tests pass when pytest uses a workspace-local base temp directory:

```powershell
python -m pytest -q --basetemp E:\Code\OpenRepro-Agent\.codex_tmp\pytest-basetemp
```

- Default pytest temp discovery can fail on this Windows machine with `PermissionError` for `C:\Users\87139\AppData\Local\Temp\pytest-of-87139`.
- Editable install into `.codex_tmp\venv` completed successfully.
- Full CLI smoke flow passed from `.codex_tmp\smoke_workspace` after changing the CLI success prefix from a Unicode checkmark to ASCII `OK`.
- The generated `figures/correlation.png` was opened and visually confirmed as non-empty.
- Git repository was initialized on `main`, the v0.1.0 baseline was committed, and the `v0.1.0` tag was created.
- Public GitHub repository was created and pushed: `https://github.com/SHENAO1/OpenRepro-Agent`.
- Remote `origin` uses SSH: `git@github.com:SHENAO1/OpenRepro-Agent.git`.
- Remote default branch is `main`; tag `v0.1.0` is present on GitHub.

## Exact Next Step

Run full v0.4.0 verification, then commit, tag, push, update GitHub About, and create the v0.4.0 release.

## Completed v0.4.0 Work

- Opt-in provider configuration and OpenAI-compatible provider guardrails.
- Human-gated experiment scaffolding.
- Benchmark-suite execution and evidence manifests.
- Advisory repair plans.
- Run comparison artifacts.
