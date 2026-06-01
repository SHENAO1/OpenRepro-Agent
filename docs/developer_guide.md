# Developer Guide

## Run tests

```bash
pip install -e ".[dev]"
python -m pytest -q
```

On Windows, if pytest cannot access the default temp directory, use a workspace-local base temp directory:

```powershell
New-Item -ItemType Directory -Force .codex_tmp\pytest-basetemp | Out-Null
python -m pytest -q --basetemp .codex_tmp\pytest-basetemp
```

## Run smoke test

```bash
bash scripts/smoke_test.sh
```

PowerShell:

```powershell
.\scripts\smoke_test.ps1
```

## Adding a new CLI command

1. Add implementation in a focused module under `src/openrepro/`.
2. Add a Typer command in `cli.py`.
3. Add tests under `tests/`.
4. Update README and docs.
5. Ensure generated artifacts are timestamped or safely overwritten only when appropriate.

## Artifact manifests

Demo and sweep runs must write `manifest.json` after all run artifacts are complete.
When adding a new run command, define its required artifacts in `artifact_manager.py`,
write the manifest at the end of the command, and add validation tests.

## PDF and candidate extraction

PDF ingestion uses `pdfplumber`. Extracted text and page provenance should stay under
`workspace/extracted_sources/`, and all generated formulas or parameters must remain
marked as candidates until a human verifies them.

## API provider extensions

Real providers should be opt-in. They must write actual usage records and must not fabricate tokens or costs.

v0.4.0 ships `MockProvider` plus a minimal OpenAI-compatible provider path.
Real calls must require explicit configuration, environment-backed secrets, and
request-hash cache accounting. Do not store API keys in project files.

## Benchmark runner

Benchmark tasks must report workflow-compliance evidence only. They can check
sources, artifacts, manifests, and metric availability, but they must not claim
paper reproduction success or scientific benchmark scores.

v0.4.0 benchmark tasks may use either legacy `expected_artifacts` and
`evaluation_metrics` fields or the newer `artifacts.required`,
`artifacts.optional`, `metrics.required`, and `metrics.optional` fields.
Optional checks should be reported without failing the benchmark status.

## Project inspection

`openrepro inspect <project_name>` should print a concise human-facing table and
write `workspace/inspect_summary.json`. The JSON summary is the stable interface
for other agents; update tests whenever the summary schema changes.

## Experiment scaffolds

`openrepro scaffold-experiment` creates files under `experiments/<id>/` from
candidate evidence. Generated scaffolds must stay human-gated: mark candidates
as unverified, write `APPROVAL_REQUIRED.md`, and avoid runnable scientific claims
until a human has reviewed formulas, parameters, and assumptions.

## Repair and run comparison

`openrepro repair-plan` is advisory only in v0.4.0 and must not mutate project
code or artifacts. `openrepro compare-runs` should report observed manifest and
metric differences without interpreting them as scientific superiority.
