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

v0.5.2 adds provider cache policy and preview redaction. New provider code should
write redacted `prompt_preview` and `response_preview` fields to usage records,
store cache files under provider/model/task namespaces, and respect
`cache_enabled`, `cache_ttl_seconds`, and `redact_prompts`.

## Benchmark runner

Benchmark tasks must report workflow-compliance evidence only. They can check
sources, artifacts, manifests, and metric availability, but they must not claim
paper reproduction success or scientific benchmark scores.

v0.4.0 benchmark tasks may use either legacy `expected_artifacts` and
`evaluation_metrics` fields or the newer `artifacts.required`,
`artifacts.optional`, `metrics.required`, and `metrics.optional` fields.
Optional checks should be reported without failing the benchmark status.

v0.6.0 benchmark tasks may include dataset, environment, dependencies,
paper_source, and expected_runtime_notes fields. These fields are provenance
evidence only. They must be surfaced in benchmark outputs and indexes without
turning them into scientific scores.

## Project inspection

`openrepro inspect <project_name>` should print a concise human-facing table and
write `workspace/inspect_summary.json`. The JSON summary is the stable interface
for other agents; update tests whenever the summary schema changes.

## Experiment scaffolds

`openrepro scaffold-experiment` creates files under `experiments/<id>/` from
candidate evidence. Generated scaffolds must stay human-gated: mark candidates
as unverified, write `APPROVAL_REQUIRED.md`, and avoid runnable scientific claims
until a human has reviewed formulas, parameters, and assumptions.

v0.5.0 adds `openrepro approve-candidates`, which writes
`workspace/verified_candidates.json` and `workspace/VERIFIED_CANDIDATES.md`.
Experiment scaffolds may use that artifact to mark inputs as
`verified_inputs_ready`, but this still does not claim paper reproduction
success.

v0.7.1 adds `openrepro list-candidates` and `openrepro review-candidates`.
Review status values are `verified_by_human`, `rejected_by_human`, and
`needs_more_evidence`; unreviewed candidates remain `candidate_unverified`.
Reviews should be written to `workspace/candidate_reviews.json` and
`workspace/CANDIDATE_REVIEWS.md`. A `verified_by_human` review should also
update the verified candidate artifact so existing experiment guardrails keep
working.

`openrepro run-experiment` may execute only verified experiment scaffolds. It
must require `--confirm`, require `status: verified_inputs_ready`, capture
execution evidence under a normal output run directory, and write a manifest.
It must not reinterpret a successful runner exit as scientific reproduction
success.

## Run lineage

`openrepro lineage <project_name>` writes `workspace/run_lineage.json` and
`workspace/RUN_LINEAGE.md`. Entries should include parent command, manifest
hash, config hash, source index hash, and verified candidate hash when present.
Lineage artifacts are provenance evidence only.

`openrepro inspect`, `openrepro status`, and handoff files should surface whether
lineage has been generated so agents can avoid guessing project provenance
state.

## Doctor checks

`openrepro doctor <project_name>` writes `workspace/doctor.json` and
`workspace/DOCTOR.md`. Doctor checks should stay focused on environment and
workflow readiness: dependency availability, project structure, config presence,
and provider readiness. They must not infer scientific validity.

## Repair and run comparison

`openrepro repair-plan` is advisory only in v0.4.0 and must not mutate project
code or artifacts. `openrepro compare-runs` should report observed manifest and
metric differences without interpreting them as scientific superiority.

v0.5.0 adds `openrepro repair --dry-run`, which writes
`workspace/repair_dry_run.json` and `workspace/REPAIR_DRY_RUN.md` without
mutating run artifacts. Manifest repair previews should be generated as diffs
against the current on-disk files; missing scientific artifacts must never be
fabricated.

v0.6.1 adds `openrepro repair --apply --only manifest --confirm`. Apply mode
must remain manifest-only: regenerate `manifest.json` from files already present
on disk, write `workspace/repair_apply.json` and `workspace/REPAIR_APPLY.md`,
and do not generate scientific artifacts, edit experiment code, or infer
parameters.
