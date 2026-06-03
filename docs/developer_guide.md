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

v0.8.0 candidate extraction should preserve evidence provenance: source path,
chunk index, page number when available, context windows, and evidence quality
signals. These fields help review candidates; they are not verification
results.

v1.1.0 candidate extraction should also preserve section labels, caption
anchors, and risk flags. Risk flags are triage hints for human review, not
validation results or automated rejection decisions.

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

v0.8.1 adds experiment templates. `scaffold-experiment --template basic` keeps
the guarded placeholder behavior, while `--template boc-like` and
`--template numeric-sweep` generate starter runners for verified scaffolds.
Template runners must write outputs under `OPENREPRO_RUN_DIR`, and
`run-experiment` must include `expected_artifacts.json` required paths in the
run manifest. If a completed runner omits a required template artifact,
`run-experiment` should fail instead of leaving the issue for a later
validation step.

v0.8.2 centralizes template metadata in `experiment_templates.py`.
New templates should be added there first, then exercised through
`openrepro list-templates`, scaffold generation, inspect/status summaries, and
expected-artifact diagnostics.

v0.9.0 adds `experiment_inputs.py`. Scaffold generation should map
human-verified candidates into `experiments/<id>/experiment_inputs.json`.
Template runners should read the file from `OPENREPRO_EXPERIMENT_INPUTS`, use
candidate-derived `parameter_values` when present, and fall back to documented
defaults when completeness warnings remain. `run-experiment` should snapshot
the input file under `configs/experiment_inputs_snapshot.json`.

v0.9.1 adds `environment_snapshot.py`. Experiment runs should record Python,
platform, dependency versions, random seed, runner hash, and a lightweight
same-seed repeatability check under `configs/environment_snapshot.json`.
Lineage entries for `run-experiment` should include hashes for experiment
config, experiment inputs, environment snapshot, and runner code.

v0.9.2 makes experiment inputs editable and auditable. `validate-inputs` should
refresh completeness and write workspace validation artifacts. `set-input`
should record input sources, preserve manual overrides, and keep generated
runner behavior tied to `experiment_inputs.json`.

v1.2.0 adds `experiment_spec.py`. Scaffold generation should create
`experiment_spec.json`; `run-experiment` should validate and snapshot it before
execution. Spec validation is an engineering contract check and must not be
presented as scientific correctness.

v1.2.1 makes specs freshness-aware. Spec source fingerprints should be stable
over config, input, expected artifact, and metric contracts, while ignoring
timestamps. `validate-experiment-spec --strict` should report stale specs
without refreshing them, and comparison reports should warn when two experiment
runs used different spec hashes.

v1.3.0 adds `data_registry.py`. Data registration should record local file path,
role, size, and SHA-256 under `workspace/data_index.json` without copying or
inventing datasets. `validate-data` should detect missing files and hash
mismatches. Experiment specs should include the registered data contract, and
`run-experiment` should snapshot the data index under
`configs/data_index_snapshot.json` for lineage and evidence packages.

v1.4.0 adds `quality_gate.py`. `run-experiment` should write
`reports/quality_gate.json` and `reports/quality_gate.md` after manifest
generation. Quality gate reports are intentionally excluded from run manifests
so manual re-evaluation does not stale the manifest; lineage and evidence
packages record their hashes separately. Quality gates should check execution
evidence completeness: manifest validity, runner completion, required metrics,
spec snapshots, data index snapshots, and environment snapshots. They must not
be presented as scientific reproduction success.

v1.4.1 extends quality gates into project-level summaries and diagnostics.
`quality-gate --all` should evaluate every run and write
`workspace/quality_gate_summary.json` plus `workspace/QUALITY_GATE_SUMMARY.md`.
Diagnostic issues should include failed gate check names so repair planning can
suggest the producing command or artifact class without fabricating evidence.

v1.5.0 makes repair planning quality-gate-aware. Diagnostics should emit both
an aggregate `quality_gate_failed` issue and check-specific issue codes such as
`quality_gate_metrics_missing`, `quality_gate_runner_failed`, or
`quality_gate_data_snapshot_missing`. Repair plans and dry-runs should map those
codes to explicit recovery actions, but they must not fabricate metrics,
snapshots, datasets, or scientific outputs.

v1.6.0 adds `claim_trace.py`. Claim traces should treat formula and parameter
candidates as traceable claims, then link them to experiment specs, registered
data, and run evidence. `trace-claims` should write JSON and Markdown under
`workspace/`. The trace is an audit map only and must not imply that a claim was
scientifically reproduced.

v1.6.1 adds claim trace validation. `validate-claims` should check trace
freshness and link integrity without rewriting `claim_trace.json`. Validation
may flag stale traces, unresolved experiment claims, unregistered experiment
data, and experiment runs that no longer point to known scaffolds. These checks
are engineering audit checks only; they must not verify formulas, datasets, or
scientific correctness.

v1.7.0 adds `scorecard.py`. Readiness scorecards should aggregate workflow
evidence completeness across paper evidence, candidate review, data provenance,
experiment specs, run evidence, quality gates, repeatability evidence, and claim
trace health. Scores are for triage and handoff only. They must not be described
as scientific reproduction scores or proof that a paper result was reproduced.

v1.7.1 adds `gaps.py`. Reproduction gaps should convert upstream workflow
evidence issues into severity-ranked to-dos with suggested commands. Gaps may
use scorecard dimensions, diagnostics, quality gates, and claim trace validation,
but should avoid evaluating generated evidence packages directly to prevent
self-referential freshness loops. Closing gaps is workflow housekeeping, not a
scientific reproduction claim.

v1.8.0 adds `checkpoints.py`. Workflow checkpoints should normalize major
project stages into `complete`, `partial`, `blocked`, or `missing`, and should
point to a single next checkpoint plus command. Checkpoints are allowed to read
existing summaries, but they should not generate scientific evidence, run
experiments, or imply that checkpoint completion equals paper reproduction.

v1.8.1 adds `advance.py`. Advance plans should be dry-run previews only. They
may select a command from open gaps or the next incomplete checkpoint, but they
must not execute commands, fill placeholder values, run experiments, repair
artifacts, or generate scientific results. The CLI should require
`advance --dry-run` until an explicitly reviewed apply mode exists.

v1.9.0 adds `review_board.py`. Review boards should aggregate existing human
review prompts into a single queue. They may point to candidate review, data,
experiment spec, claim trace, scorecard, gap, or advance-plan commands, but they
must not mark formulas, data, code, or scientific outputs as validated. A clear
board means no open workflow prompts were detected, not that the paper was
reproduced.

v1.9.1 adds `review_decisions.py`. Review decisions should record human
handling of review board items with reviewer notes and explicit status. A
closed item means the review prompt was handled or rejected; it must not be
treated as formula validation, data validation, code correctness, or scientific
reproduction evidence.

v1.10.0 adds `reproduction_protocol.py`. Protocols should synthesize target
claims, required data, required experiments, required runs, and acceptance
criteria from existing artifacts. They may say whether workflow criteria are
blocked or ready, but they must not claim that the protocol has been executed
successfully or that the paper has been scientifically reproduced.

v1.10.1 adds `protocol_coverage.py`. Coverage should check whether protocol
claims, data, experiments, runs, and acceptance criteria are linked to current
workflow evidence. Coverage scores are engineering completeness signals only;
they must not be framed as scientific reproduction scores.

v0.9.3 adds `experiment_compare.py`. `rerun-experiment` should reuse the same
execution guardrails as `run-experiment`, while `compare-experiments` should
compare only runs that belong to the requested experiment id. Comparison reports
must stay evidence-oriented: metric deltas, runner hashes, raw input hashes,
normalized input hashes, and environment hashes are acceptable; scientific
reproduction claims are not.

v1.0.0 adds `evidence_package.py`. Evidence packages should reuse existing
inspect, lineage, manifest validation, experiment, benchmark, report, and
handoff artifacts rather than recomputing incompatible state. They should write
both JSON and Markdown under `reports/` and keep policy language explicit that
workflow evidence is not a scientific reproduction claim.

v1.0.1 adds `evidence_fingerprint.py`. Evidence package freshness should be
based on source fingerprints that exclude generated evidence package files.
`evidence-package --zip` should export the package plus referenced workspace
and handoff artifacts without changing scientific evidence.

## Run lineage

`openrepro lineage <project_name>` writes `workspace/run_lineage.json` and
`workspace/RUN_LINEAGE.md`. Entries should include parent command, manifest
hash, config hash, source index hash, and verified candidate hash when present.
Experiment reruns should be grouped with repeat ids and repeat run indexes.
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
