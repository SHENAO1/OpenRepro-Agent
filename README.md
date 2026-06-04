# OpenRepro-Agent

OpenRepro-Agent is a Python CLI workflow for paper reproduction projects. It initializes a reproducible workspace, ingests Markdown/txt/PDF sources, extracts candidate formulas and parameters, plans experiments, scaffolds human-gated experiment code, runs lightweight demos and parameter sweeps, validates generated artifacts, inspects project state, runs workflow-compliance benchmarks and suites, indexes benchmark evidence, classifies failures, tracks cache-aware provider usage, and produces multi-agent handoff files and evidence packages.

Current version: **v1.18.0**. This is still an alpha engineering scaffold, not a finished autonomous paper-reproduction system.

## Why this project exists

Research-paper reproduction often fails because notes, assumptions, formulas, experiment code, logs, and reports are scattered across folders or chat histories. OpenRepro-Agent focuses on making the project loop runnable, inspectable, and auditable before adding more ambitious automation.

The v1.18.0 workflow is:

```text
init → configure-provider → ingest → analyze → plan → list-templates → list-candidates → review-candidates → approve-candidates → register-data → validate-data → scaffold-experiment → set-input → validate-inputs → validate-experiment-spec → run-experiment → quality-gate → rerun-experiment → compare-experiments → run-demo → validate --all → inspect → diagnose → repair-plan → repair --dry-run → run-sweep → quality-gate → compare-runs → quality-gate --all → lineage → trace-claims → validate-claims → scorecard → gaps → todo → checkpoints → advance --dry-run → review-board → review-decision → protocol → protocol-coverage → protocol-plan → protocol-preflight → evidence-binder → validate-evidence-binder → claim-signoff → validate-claim-signoffs → claim-evidence-report → validate-claim-evidence-report → reviewer-packet → timeline → doctor → benchmark → benchmark-suite → benchmark-index → report → handoff → evidence-package → review-site → collaboration-pack → refresh → status
```

## What v0.4.0 supports

- Create a standard paper reproduction project directory.
- Ingest Markdown and text notes into `sources/`.
- Ingest PDFs, extract text and page-level provenance with `pdfplumber`, and record extraction status.
- Generate `paper_summary.md` using rule-based keyword detection and candidate extraction.
- Generate Markdown and JSON model ledgers with formula and parameter candidates marked `candidate_unverified`.
- Generate `EXPERIMENT_PLAN.md` and `experiment_plan_validation.json`.
- Configure mock or OpenAI-compatible providers while keeping real calls disabled by default.
- Scaffold human-gated experiment folders from candidate formulas and parameters.
- Run a lightweight BOC-like signal and autocorrelation demo.
- Run a noise/seed parameter sweep for the built-in demo.
- Save run artifacts: logs, figures, data, metrics, reports, config snapshots, metadata, manifest, mock API usage, and handoff notes.
- Validate run manifests, required artifacts, file sizes, and SHA-256 hashes.
- Validate every project run at once with `openrepro validate --all`.
- Inspect project state and write `workspace/inspect_summary.json`.
- Diagnose common workflow failures and suggest repairs.
- Generate advisory repair plans with `workspace/repair_plan.json` and `workspace/REPAIR_PLAN.md`.
- Compare two run directories and write run comparison artifacts.
- Run workflow-compliance benchmark tasks from `benchmarks/benchmark_schema.json`.
- Run benchmark suites from `benchmarks/sample_suite.json`.
- Generate `benchmark_index.json` and `benchmark_index.md` for benchmark runs.
- Use a deterministic mock provider interface with request-hash cache accounting.
- Generate a project-level Markdown report.
- Generate multi-agent handoff files for Claude Code, Codex, GitHub Copilot, or human maintainers.
- Run pytest tests for the minimum workflow.

## What v0.5.0 adds

- Promote human-reviewed formula and parameter candidates into `workspace/verified_candidates.json`.
- Generate `workspace/VERIFIED_CANDIDATES.md` for auditable approval notes.
- Let experiment scaffolds detect verified candidates and mark the scaffold as `verified_inputs_ready`.
- Preview controlled repair actions with `openrepro repair --dry-run`.
- Generate repair previews in `workspace/repair_dry_run.json` and `workspace/REPAIR_DRY_RUN.md`.
- Include manifest regeneration diffs in dry-run previews for manifest mismatch or missing-manifest cases.

## What v0.5.1 adds

- Surface verified candidate counts and approval status in `openrepro inspect`.
- Surface latest repair dry-run status and action counts in `openrepro inspect`.
- Include verified candidate and repair dry-run summaries in project reports.
- Include verified candidate and repair dry-run handoff files.
- Suggest `approve-candidates` from `openrepro status` when analysis and planning are complete but candidates are not approved.

## What v0.5.2 adds

- Redact likely secrets, tokens, API keys, and email addresses from provider usage previews.
- Store provider cache entries under provider/model/task namespaces.
- Add provider cache policy fields: `cache_enabled`, `cache_ttl_seconds`, and `redact_prompts`.
- Allow `configure-provider` to update cache and redaction policy without storing secrets.
- Include redacted prompt/response previews and cache namespace metadata in usage records.

## What v0.6.0 adds

- Generate run lineage artifacts with `openrepro lineage`.
- Record manifest, config, source index, and verified candidate hashes for every run.
- Add benchmark provenance fields for dataset, environment, dependencies, paper source, and runtime notes.
- Surface benchmark provenance completeness in benchmark reports, suites, and indexes.

## What v0.6.1 adds

- Apply explicitly confirmed manifest-only repairs with `openrepro repair --apply --only manifest --confirm`.
- Write `workspace/repair_apply.json` and `workspace/REPAIR_APPLY.md`.
- Keep repair application limited to manifest regeneration from files already present on disk.

## What v0.6.2 adds

- Add `openrepro doctor` for dependency, project structure, config, and provider readiness checks.
- Surface lineage status in `inspect`, `status`, and handoff files.
- Add `handoff/RUN_LINEAGE.md` to generated handoff bundles.
- Expand smoke tests to cover approval, lineage, repair dry-run/apply, and doctor commands.

## What v0.7.0 adds

- Add `openrepro run-experiment` for confirmed execution of verified experiment scaffolds.
- Require experiment status `verified_inputs_ready` and explicit `--confirm`.
- Capture runner stdout/stderr, execution metadata, report, config snapshot, runner copy, and manifest.
- Keep experiment runs as execution evidence only, not scientific reproduction claims.

## What v0.7.1 adds

- Add `openrepro list-candidates` to inspect formula and parameter candidates with review status.
- Add `openrepro review-candidates` with statuses `verified_by_human`, `rejected_by_human`, and `needs_more_evidence`.
- Write `workspace/candidate_reviews.json` and `workspace/CANDIDATE_REVIEWS.md`.
- Sync `verified_by_human` reviews into the existing verified candidate approval artifact.

## What v0.7.2 adds

- Improve `openrepro status` next-step suggestions for list/review/scaffold/run-experiment flows.
- Add candidate review and experiment-run counts to status and inspect output.
- Expand smoke scripts to cover the v0.7.x command set.
- Add release tags for recent versions.

## What v0.8.0 adds

- Write `workspace/paper_metadata.json` with title and DOI candidates.
- Add source path, chunk index, page number, context window, and evidence quality to formula candidates.
- Add numeric values, normalized units, context window, and evidence quality to parameter candidates.
- Preserve table/page provenance for PDF table-derived parameter candidates.

## What v0.8.1 adds

- Add `--template basic|boc-like|numeric-sweep` to `openrepro scaffold-experiment`.
- Generate template runners for BOC-like traces and numeric sweeps when verified inputs are available.
- Align `expected_artifacts.json` with the current `run-experiment` output layout.
- Have `run-experiment` pass `OPENREPRO_RUN_DIR` to runners and include template-required artifacts in the run manifest.

## What v0.8.2 adds

- Add `openrepro list-templates` for supported experiment templates.
- Move template metadata into a shared template registry.
- Surface scaffold template counts and expected-artifact attention counts in `inspect` and `status`.
- Diagnose legacy, missing, mismatched, or tampered `expected_artifacts.json` files for experiment scaffolds.

## What v0.9.0 adds

- Write `experiments/<id>/experiment_inputs.json` from human-verified formula and parameter candidates.
- Map parameter candidates into `parameter_values` for template runners.
- Add input completeness checks for template-required inputs such as `code_length` and `noise_std`.
- Have template runners read `OPENREPRO_EXPERIMENT_INPUTS` instead of relying only on hard-coded defaults.
- Snapshot experiment inputs into run outputs and surface the mapping in run reports and handoff files.

## What v0.9.1 adds

- Write `configs/environment_snapshot.json` for `run-experiment`.
- Record Python, platform, dependency versions, random seed, runner hash, and repeatability status.
- Add environment snapshots to required run-experiment artifacts.
- Extend lineage with experiment config, input, environment, and runner hashes.
- Add a lightweight same-seed repeatability check against prior experiment runs.

## What v0.9.2 adds

- Add `openrepro validate-inputs` for experiment input completeness checks.
- Add `openrepro set-input` for manual input calibration and overrides.
- Track input sources as `verified_candidate`, `manual_override`, or `default`.
- Surface missing required input counts in `inspect` and `status`.
- Record input validation details and warnings in experiment run evidence.

## What v0.9.3 adds

- Add `openrepro rerun-experiment` for repeat execution of an existing verified scaffold.
- Add `openrepro compare-experiments` for same-experiment metric and hash comparison.
- Write `workspace/experiment_comparison.json` and `workspace/EXPERIMENT_COMPARISON.md`.
- Add normalized input hashing so timestamp refreshes do not hide equivalent inputs.
- Extend lineage with experiment repeat groups and repeat run indexes.

## What v1.0.0 adds

- Add `openrepro evidence-package` for project-level evidence packaging.
- Write `reports/evidence_package.json` and `reports/evidence_package.md`.
- Summarize project status, inspect output, workspace artifacts, experiments, runs, lineage, benchmark indexes, reports, and handoff completeness.
- Keep evidence-package policy explicit: workflow evidence is not a scientific reproduction claim.
- Add v1.0.0 regression tests and smoke coverage for evidence package generation.

## What v1.0.1 adds

- Add evidence package source fingerprints and artifact SHA-256 hashes.
- Add freshness detection so `status` can report missing, current, or stale evidence packages.
- Add `openrepro evidence-package --zip` for compact handoff export.
- Add `handoff/EVIDENCE_PACKAGE.md`.
- Add stale-package and zip-export regression tests.

## What v1.1.0 adds

- Add section-aware evidence provenance for formula and parameter candidates.
- Add `workspace/caption_index.json` and `workspace/CAPTION_INDEX.md`.
- Add candidate risk flags and high-risk candidate counts.
- Surface candidate risk levels in `openrepro inspect`.
- Include caption evidence in evidence packages.

## What v1.2.0 adds

- Add `experiments/<id>/experiment_spec.json` as an execution contract.
- Add `openrepro validate-experiment-spec`.
- Validate experiment specs before `run-experiment`.
- Snapshot specs into run outputs and required run manifests.
- Compare and lineage experiment spec hashes across runs.

## What v1.2.1 adds

- Add source fingerprints to experiment specs so stale contracts can be detected.
- Add strict spec validation with `openrepro validate-experiment-spec --strict`.
- Surface spec status counts in `inspect`, `status`, and evidence packages.
- Warn when compared experiment runs used different experiment spec hashes.

## What v1.3.0 adds

- Add `openrepro register-data` for local data source provenance.
- Add `openrepro validate-data` for registered file presence and SHA-256 checks.
- Snapshot `workspace/data_index.json` into experiment run outputs.
- Include data registry status in specs, lineage, inspect, status, comparisons, and evidence packages.

## What v1.4.0 adds

- Add `openrepro quality-gate` for run evidence completeness checks.
- Automatically write quality gate JSON and Markdown for `run-experiment`.
- Check manifest validity, runner completion, spec/data/environment snapshots, and required metrics.
- Surface quality gate status in `inspect`, `status`, lineage, and evidence packages.

## What v1.4.1 adds

- Add `openrepro quality-gate --all` for batch quality gate evaluation.
- Write `workspace/quality_gate_summary.json` and `workspace/QUALITY_GATE_SUMMARY.md`.
- Surface failed quality gate check names in inspect and evidence packages.
- Let `diagnose` report failed quality gates as actionable issues.
- Split latest-run gate status from latest experiment-run gate status in `status`.

## What v1.5.0 adds

- Break failed quality gates into check-specific diagnosis codes.
- Add repair-plan automations for metrics, manifest, runner, and snapshot failures.
- Add repair dry-run previews for common quality gate failures without fabricating artifacts.
- Include the quality gate summary inside `workspace/repair_plan.json`.

## What v1.6.0 adds

- Add `openrepro trace-claims` for claim-to-evidence traceability.
- Write `workspace/claim_trace.json` and `workspace/CLAIM_TRACE.md`.
- Add `claim_contract` to experiment specs.
- Link candidate claims, verified claims, experiment scaffolds, registered data, and runs.
- Include claim trace summaries in `inspect`, `status`, and evidence packages.

## What v1.6.1 adds

- Add `openrepro validate-claims` for claim trace freshness and link integrity checks.
- Add `openrepro trace-claims --validate` to regenerate and immediately validate trace artifacts.
- Write `workspace/claim_trace_validation.json` and `workspace/CLAIM_TRACE_VALIDATION.md`.
- Surface claim trace validation status in `inspect`, `status`, `diagnose`, and evidence packages.

## What v1.7.0 adds

- Add `openrepro scorecard` for workflow readiness scoring.
- Write `workspace/reproduction_scorecard.json` and `workspace/REPRODUCTION_SCORECARD.md`.
- Score paper evidence, candidate review, data provenance, experiment specs, run evidence, quality gates, repeatability evidence, and claim trace health.
- Surface readiness scorecard summaries in `inspect`, `status`, handoff, and evidence packages.

## What v1.7.1 adds

- Add `openrepro gaps` and `openrepro todo` for actionable reproduction workflow gaps.
- Write `workspace/reproduction_gaps.json` and `workspace/REPRODUCTION_GAPS.md`.
- Convert missing or weak workflow evidence into severity-ranked suggested commands.
- Surface open gap counts in `inspect`, `status`, handoff, reports, and evidence packages.

## What v1.8.0 adds

- Add `openrepro checkpoints` for normalized workflow checkpoint status.
- Write `workspace/workflow_checkpoints.json` and `workspace/WORKFLOW_CHECKPOINTS.md`.
- Normalize source, analysis, planning, reviews, data, specs, runs, gates, lineage, claim trace, scorecard, and gaps into `complete`, `partial`, `blocked`, or `missing`.
- Surface checkpoint status and next checkpoint in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.8.1 adds

- Add `openrepro advance --dry-run` for guided next-step previews.
- Write `workspace/advance_plan.json` and `workspace/ADVANCE_PLAN.md`.
- Select the top next command from open gaps or the next incomplete checkpoint.
- Keep advance plans as dry-run previews only; they do not execute commands or create scientific evidence.

## What v1.9.0 adds

- Add `openrepro review-board` for a consolidated human review queue.
- Write `workspace/review_board.json` and `workspace/REVIEW_BOARD.md`.
- Summarize candidate review, data validation, experiment spec, claim trace, scorecard, gaps, and advance-plan items that need human attention.
- Surface review board status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.9.1 adds

- Add `openrepro review-decision` for recording human decisions on review board items.
- Write `workspace/review_decisions.json` and `workspace/REVIEW_DECISIONS.md`.
- Track `resolved`, `rejected`, `deferred`, and `needs_followup` decisions with reviewer notes.
- Surface review decision status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.10.0 adds

- Add `openrepro protocol` for generating a reproduction protocol.
- Write `workspace/reproduction_protocol.json` and `workspace/REPRODUCTION_PROTOCOL.md`.
- Summarize target claims, required data, required experiments, required runs, and acceptance criteria.
- Surface protocol status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.10.1 adds

- Add `openrepro protocol-coverage` for checking reproduction protocol coverage.
- Write `workspace/protocol_coverage.json` and `workspace/PROTOCOL_COVERAGE.md`.
- Check claim, data, experiment, run, and acceptance-criteria coverage.
- Surface protocol coverage status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.11.0 adds

- Add `openrepro protocol-plan` for converting protocol coverage gaps into prioritized workflow actions.
- Write `workspace/protocol_plan.json` and `workspace/PROTOCOL_PLAN.md`.
- Track critical/high action counts, top command, and human-input requirements.
- Surface protocol plan status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.11.1 adds

- Add `openrepro protocol-preflight` for checking protocol readiness before handoff or execution.
- Write `workspace/protocol_preflight.json` and `workspace/PROTOCOL_PREFLIGHT.md`.
- Check protocol readiness, coverage, plan actions, data provenance, specs, quality gates, and review decisions.
- Surface preflight status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.12.0 adds

- Add `openrepro evidence-binder` for binding each traced claim to workflow evidence.
- Write `workspace/claim_evidence_binder.json` and `workspace/CLAIM_EVIDENCE_BINDER.md`.
- Link claims to experiments, runs, registered data, quality gates, protocol coverage, and review decisions.
- Surface incomplete claim counts in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.12.1 adds

- Add `openrepro validate-evidence-binder` for checking binder freshness and internal consistency.
- Write `workspace/claim_evidence_binder_validation.json` and `workspace/CLAIM_EVIDENCE_BINDER_VALIDATION.md`.
- Detect stale binders when claims, protocol coverage, review decisions, data, specs, or runs change.
- Surface binder validation status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.13.0 adds

- Add `openrepro claim-signoff` for recording human decisions on each claim evidence binder record.
- Write `workspace/claim_signoffs.json` and `workspace/CLAIM_SIGNOFFS.md`.
- Track `accepted_workflow_evidence`, `needs_more_evidence`, `rejected`, and `deferred` signoffs.
- Surface claim signoff status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.13.1 adds

- Add `openrepro claim-evidence-report` for a reviewer-facing claim evidence matrix.
- Write `reports/claim_evidence_report.json` and `reports/claim_evidence_report.md`.
- Combine binder evidence, binder validation, and human claim signoffs per claim.
- Surface claim evidence report status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.14.0 adds

- Add `openrepro validate-claim-signoffs` for checking claim signoff coverage and freshness.
- Write `workspace/claim_signoff_validation.json` and `workspace/CLAIM_SIGNOFF_VALIDATION.md`.
- Detect stale signoff snapshots, orphan signoffs, incomplete accepted claims, and failed binder validation.
- Surface claim signoff validation status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.14.1 adds

- Add `openrepro validate-claim-evidence-report` for checking claim evidence report freshness.
- Write `reports/claim_evidence_report_validation.json` and `reports/claim_evidence_report_validation.md`.
- Detect stale reports when binder evidence, binder validation, or claim signoffs change.
- Surface claim evidence report validation status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.15.0 adds

- Add `openrepro reviewer-packet` for human reviewer handoff.
- Write `reports/reviewer_packet.json`, `reports/reviewer_packet.md`, and optional `reports/reviewer_packet.zip`.
- Summarize claim evidence, signoffs, validations, open actions, review order, and source artifact hashes.
- Surface reviewer packet status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.16.0 adds

- Add `openrepro review-site` for a static human review site.
- Write `reports/review_site/index.html`, `reports/review_site_manifest.json`, and optional `reports/review_site.zip`.
- Summarize project readiness, claim evidence matrix, reviewer packet status, evidence package freshness, quality gates, open actions, blockers, and key artifact links.
- Surface review site status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.16.1 adds

- Add `openrepro timeline` for a unified project timeline and decision log.
- Write `workspace/project_timeline.json` and `workspace/PROJECT_TIMELINE.md`.
- Consolidate source ingestion, candidate reviews, verified candidates, claim signoffs, review decisions, runs, quality gates, and major evidence artifacts into chronological events.
- Surface timeline status in `inspect`, `status`, reports, handoff, evidence packages, and review sites.

## What v1.17.0 adds

- Add `openrepro collaboration-pack` for role-based project handoff.
- Write `handoff/collaboration_pack.json`, `handoff/COLLABORATION_PACK.md`, and optional `handoff/collaboration_pack.zip`.
- Split next work into maintainer, reviewer, experimenter, and next-agent checklists.
- Summarize unresolved decisions, next safe commands, readiness state, and files to inspect first.
- Surface collaboration pack status in `inspect`, `status`, reports, handoff, and evidence packages.

## What v1.18.0 adds

- Add `openrepro refresh` for a safe derived-artifact refresh pipeline.
- Write `workspace/refresh_run.json`, `workspace/REFRESH_RUN.md`, and optional `workspace/refresh_run.zip`.
- Refresh quality gates, lineage, traceability, scorecards, gaps, protocols, binders, reviewer packets, timelines, reports, handoff files, evidence packages, review sites, and collaboration packs.
- Keep refresh guarded: it does not run experiments, add human signoffs, resolve review decisions, or fabricate missing scientific artifacts.
- Surface refresh run status in `inspect`, `status`, reports, handoff, and evidence packages.

## Current limitations

- It does not fully read or understand papers.
- It does not verify mathematical formulas automatically.
- It does not verify dataset semantics, labels, provenance claims, or scientific data quality automatically.
- It does not generate full simulation code for arbitrary papers.
- It does not automatically repair failed experiments.
- It does not apply repair previews automatically; dry-run output is for review.
- It does not enable real LLM providers by default; OpenAI-compatible calls require explicit opt-in and environment-backed secrets.
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
openrepro configure-provider boc_demo --provider mock --disable-real-api
openrepro ingest boc_demo --source examples/boc_notes.md
openrepro analyze boc_demo
openrepro plan boc_demo
openrepro list-templates
openrepro list-candidates boc_demo
openrepro review-candidates boc_demo --candidate-id F001 --status needs_more_evidence --reviewer human
openrepro approve-candidates boc_demo --all --reviewer human
# Optional: register local data files before scaffolding so specs capture data provenance.
openrepro register-data boc_demo --path path/to/dataset.csv --role dataset
openrepro validate-data boc_demo
openrepro scaffold-experiment boc_demo --experiment-id boc_candidate_exp --template boc-like
openrepro set-input boc_demo --experiment-id boc_candidate_exp --name noise_std --value 0.05
openrepro set-input boc_demo --experiment-id boc_candidate_exp --name code_length --value 128
openrepro validate-inputs boc_demo --experiment-id boc_candidate_exp
openrepro validate-experiment-spec boc_demo --experiment-id boc_candidate_exp
openrepro run-experiment boc_demo --experiment-id boc_candidate_exp --confirm
openrepro quality-gate boc_demo
openrepro rerun-experiment boc_demo --experiment-id boc_candidate_exp --confirm
openrepro compare-experiments boc_demo --experiment-id boc_candidate_exp
openrepro run-demo boc_demo
openrepro validate boc_demo
openrepro validate boc_demo --all
openrepro inspect boc_demo
openrepro diagnose boc_demo
openrepro repair-plan boc_demo
openrepro repair boc_demo --dry-run
openrepro run-sweep boc_demo --noise-std 0.0 --noise-std 0.1 --seed 42
openrepro quality-gate boc_demo
openrepro validate boc_demo
openrepro compare-runs boc_demo
openrepro quality-gate boc_demo --all
openrepro lineage boc_demo
openrepro trace-claims boc_demo --validate
openrepro validate-claims boc_demo
openrepro scorecard boc_demo
openrepro gaps boc_demo
openrepro todo boc_demo
openrepro checkpoints boc_demo
openrepro advance boc_demo --dry-run
openrepro review-board boc_demo
# Optional when review-board reports open items:
openrepro review-decision boc_demo --item-id candidate_verification_missing --decision needs_followup --reviewer human
openrepro protocol boc_demo
openrepro protocol-coverage boc_demo
openrepro protocol-plan boc_demo
openrepro protocol-preflight boc_demo
openrepro evidence-binder boc_demo
openrepro validate-evidence-binder boc_demo
openrepro claim-signoff boc_demo --claim-id formula:F001 --decision accepted_workflow_evidence --reviewer human
openrepro validate-claim-signoffs boc_demo
openrepro claim-evidence-report boc_demo
openrepro validate-claim-evidence-report boc_demo
openrepro reviewer-packet boc_demo --zip
openrepro timeline boc_demo
openrepro doctor boc_demo
openrepro benchmark --task benchmarks/sample_task.json --project boc_benchmark
openrepro benchmark-suite --suite benchmarks/sample_suite.json --project-prefix boc_suite
openrepro benchmark-index
openrepro report boc_demo
openrepro handoff boc_demo
openrepro evidence-package boc_demo --zip
openrepro review-site boc_demo --zip
openrepro collaboration-pack boc_demo --zip
openrepro refresh boc_demo --zip
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
  data/
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

For PDFs, v0.4.0 records:

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
workspace/paper_metadata.json
workspace/caption_index.json
workspace/CAPTION_INDEX.md
```

The analyzer is rule-based. Formula, parameter, and model records are candidates and require human verification.
Formula and parameter candidates include section labels, context windows,
evidence quality, and risk flags such as missing page anchors or thin context.

### `openrepro plan <project_name>`

Generates:

```text
workspace/EXPERIMENT_PLAN.md
workspace/experiment_plan_validation.json
```

The validation file checks whether sources exist, PDF extraction needs review, candidate formulas/parameters were detected, and demo configuration values are valid.

### `openrepro configure-provider <project_name>`

Updates provider settings in `project_config.yaml` without storing secrets. Mock mode remains the default:

```bash
openrepro configure-provider boc_demo --provider mock --disable-real-api
```

OpenAI-compatible calls require explicit opt-in and an environment variable:

```bash
openrepro configure-provider boc_demo --provider openai --model gpt-4.1-mini --enable-real-api --api-key-env OPENAI_API_KEY
```

The command reports whether the configured provider is ready for real calls; it never prints or stores API key values.

Provider cache and redaction policy can also be configured:

```bash
openrepro configure-provider boc_demo --provider mock --cache-enabled --cache-ttl-seconds 86400 --redact-prompts
```

### `openrepro scaffold-experiment <project_name>`

Creates a human-gated experiment scaffold under:

```text
experiments/<experiment_id>/
  README.md
  APPROVAL_REQUIRED.md
  experiment_config.json
  experiment_spec.json
  expected_artifacts.json
  experiment_inputs.json
  runner.py
  runner_stub.py
```

The scaffold is generated from candidate formulas and parameters and is marked `approval_required` unless verified candidates exist or `--acknowledge-candidates` is provided. It is a coding starting point, not a reproduction claim.

Use `--template basic`, `--template boc-like`, or `--template numeric-sweep` to choose the starter runner. Template runners are created only for runnable scaffolds, and they write declared outputs under `OPENREPRO_RUN_DIR` during `run-experiment`.

Verified candidates are also mapped into `experiment_inputs.json`. The file
contains formula evidence, parameter records, `parameter_values`, and input
completeness status. Template runners read it through
`OPENREPRO_EXPERIMENT_INPUTS`.

Use `openrepro set-input` to add or override individual values. Manual values
are marked as `manual_override` and validation artifacts are written under
`workspace/experiment_input_validation.json` and
`workspace/EXPERIMENT_INPUT_VALIDATION.md`.

### `openrepro validate-inputs <project_name> --experiment-id ID`

Checks whether the scaffold has all inputs required by its template. The command
exits non-zero when required inputs are missing.

### `openrepro validate-experiment-spec <project_name> --experiment-id ID`

Validates the experiment contract and writes:

```text
workspace/experiment_spec_validation.json
workspace/EXPERIMENT_SPEC_VALIDATION.md
```

The contract records template, input, runner, artifact, and metric expectations.
Validation checks engineering consistency only; it does not verify scientific
correctness. Use `--strict` to fail on stale specs or warnings without
refreshing the saved contract.

### `openrepro set-input <project_name> --experiment-id ID --name NAME --value VALUE`

Sets an input value in `experiment_inputs.json` and refreshes input validation.
Values may be JSON scalars or comma-separated lists.

### `openrepro list-templates`

Lists supported experiment scaffold templates, their purpose, required
artifacts, and input hints. The current templates are `basic`, `boc-like`, and
`numeric-sweep`.

### `openrepro approve-candidates <project_name>`

Writes human approval artifacts for selected candidate formulas and parameters:

```text
workspace/verified_candidates.json
workspace/VERIFIED_CANDIDATES.md
```

Approve all currently detected candidates:

```bash
openrepro approve-candidates boc_demo --all --reviewer human --note "Checked against paper notes."
```

Or approve specific candidate IDs:

```bash
openrepro approve-candidates boc_demo --formula-id F001 --parameter-id P001
```

Verified candidates are implementation inputs only. They do not prove that the paper has been reproduced.

### `openrepro register-data <project_name> --path PATH --role ROLE`

Registers a local data file in:

```text
workspace/data_index.json
workspace/DATA_INDEX.md
```

The registry stores role, path, size, SHA-256, source label, and notes. Register
data before scaffolding an experiment when the experiment spec should capture
that data contract.

### `openrepro validate-data <project_name>`

Checks registered data files still exist and match their recorded SHA-256 hashes.
The command writes:

```text
workspace/data_validation.json
workspace/DATA_VALIDATION.md
```

The validation is a file provenance check only; it does not verify the scientific
meaning, labels, quality, or completeness of the dataset.

### `openrepro list-candidates <project_name>`

Lists formula and parameter candidates with their latest review status. By
default, unreviewed records keep `candidate_unverified`.

### `openrepro review-candidates <project_name>`

Records a human review status for one or more candidates:

```bash
openrepro review-candidates boc_demo --candidate-id F001 --status needs_more_evidence --reviewer human --note "Need page-level context."
openrepro review-candidates boc_demo --candidate-id P001 --status rejected_by_human --reviewer human
openrepro review-candidates boc_demo --candidate-id F002 --status verified_by_human --reviewer human
```

Review artifacts are written to:

```text
workspace/candidate_reviews.json
workspace/CANDIDATE_REVIEWS.md
```

When a review uses `verified_by_human`, OpenRepro-Agent also updates
`workspace/verified_candidates.json` for compatibility with experiment
scaffolding and `run-experiment`.

### `openrepro run-experiment <project_name> --experiment-id ID --confirm`

Runs a verified experiment scaffold and records execution evidence in a
timestamped output directory. The command refuses to run unless:

- `--confirm` is provided.
- `experiments/<id>/experiment_config.json` has `status: verified_inputs_ready`.
- the experiment config marks the scaffold as runnable.

Outputs include:

```text
logs/run.log
data/execution_result.json
reports/experiment_report.md
configs/experiment_config_snapshot.json
configs/experiment_inputs_snapshot.json
configs/experiment_spec_snapshot.json
configs/data_index_snapshot.json
configs/environment_snapshot.json
reports/quality_gate.json
reports/quality_gate.md
code/runner.py
metadata.json
manifest.json
```

The command executes the scaffold runner and records evidence only. It does not
claim paper reproduction success.

For v0.8.1 scaffolds, `run-experiment` reads
`experiments/<id>/expected_artifacts.json` and includes those required paths in
the run manifest, so template-specific outputs are validated with the rest of
the run evidence. If a runner exits successfully but omits required template
artifacts, the command fails with an artifact-validation error.

### `openrepro quality-gate <project_name> [--run-dir RUN_DIR] [--all]`

Evaluates a run directory and writes:

```text
reports/quality_gate.json
reports/quality_gate.md
```

For `run-experiment`, the gate checks manifest validity, runner completion,
spec/data/environment snapshots, and required template metrics. For other run
commands, it applies a manifest-level evidence check. The gate is evidence
completeness only; it is not a scientific reproduction claim.

Use `--all` to evaluate every run directory and write:

```text
workspace/quality_gate_summary.json
workspace/QUALITY_GATE_SUMMARY.md
```

### `openrepro trace-claims <project_name>`

Builds claim-to-evidence traceability and writes:

```text
workspace/claim_trace.json
workspace/CLAIM_TRACE.md
```

Formula and parameter candidates are treated as traceable claims. The trace
links them to experiment specs, registered data, and run evidence. It is an
audit map only; it does not prove that any paper claim has been scientifically
reproduced.

Pass `--validate` to immediately run claim trace validation after regenerating
the trace.

### `openrepro validate-claims <project_name>`

Validates existing claim trace freshness and link integrity, then writes:

```text
workspace/claim_trace_validation.json
workspace/CLAIM_TRACE_VALIDATION.md
```

Validation checks whether the trace is stale, whether experiment claims resolve
to known candidates, whether verified links are backed by human-approved
candidates, whether experiment data links still exist in the data registry, and
whether experiment runs point back to known scaffolds. Validation is workflow
evidence only; it is not mathematical or scientific verification.

### `openrepro scorecard <project_name>`

Generates a workflow readiness scorecard and writes:

```text
workspace/reproduction_scorecard.json
workspace/REPRODUCTION_SCORECARD.md
```

The scorecard summarizes engineering evidence completeness across paper
evidence, candidate review, data provenance, experiment specs, run evidence,
quality gates, repeatability evidence, and claim trace health. It is not a
scientific reproduction score and must not be used to claim a paper was
reproduced.

### `openrepro gaps <project_name>`

Generates actionable reproduction workflow gaps and writes:

```text
workspace/reproduction_gaps.json
workspace/REPRODUCTION_GAPS.md
```

Gaps are severity-ranked to-dos derived from workflow evidence, scorecard
dimensions, diagnostics, quality gates, and claim trace validation. Each gap
includes a suggested next command. `openrepro todo <project_name>` is an alias
that writes the same artifacts.

### `openrepro checkpoints <project_name>`

Generates normalized workflow checkpoints and writes:

```text
workspace/workflow_checkpoints.json
workspace/WORKFLOW_CHECKPOINTS.md
```

Checkpoints map the major reproduction workflow stages to `complete`,
`partial`, `blocked`, or `missing`, then expose the next checkpoint and suggested
command. They are workflow progress markers only, not proof of scientific
reproduction.

### `openrepro advance <project_name> --dry-run`

Generates a guided advance plan and writes:

```text
workspace/advance_plan.json
workspace/ADVANCE_PLAN.md
```

The plan previews the next command selected from open gaps or the next
incomplete checkpoint. It never executes the command; commands with placeholders
such as `<id>` still require human input.

### `openrepro review-board <project_name>`

Generates a human review board and writes:

```text
workspace/review_board.json
workspace/REVIEW_BOARD.md
```

The board consolidates candidate-review, data, spec, claim-trace, scorecard,
gap, and advance-plan items that still require human attention. A clear board is
an engineering workflow signal only, not proof of scientific reproduction.

### `openrepro review-decision <project_name> --item-id ID --decision STATUS --reviewer NAME`

Records a human decision for a review board item and writes:

```text
workspace/review_decisions.json
workspace/REVIEW_DECISIONS.md
```

Supported decision statuses are `resolved`, `rejected`, `deferred`, and
`needs_followup`. Closing a review item records workflow handling only; it does
not validate formulas, data, code, or scientific outputs.

### `openrepro protocol <project_name>`

Generates a reproduction protocol and writes:

```text
workspace/reproduction_protocol.json
workspace/REPRODUCTION_PROTOCOL.md
```

The protocol summarizes target claims, required data, required experiments,
required runs, and acceptance criteria. It defines workflow acceptance criteria
only; it does not claim the paper has been reproduced.

### `openrepro protocol-coverage <project_name>`

Generates protocol coverage checks and writes:

```text
workspace/protocol_coverage.json
workspace/PROTOCOL_COVERAGE.md
```

Coverage checks whether protocol claims, data, experiments, runs, and
acceptance criteria are linked to current workflow evidence. The coverage score
is an engineering completeness signal, not a scientific reproduction score.

### `openrepro protocol-plan <project_name>`

Generates prioritized workflow actions from protocol coverage gaps and writes:

```text
workspace/protocol_plan.json
workspace/PROTOCOL_PLAN.md
```

The action plan previews suggested commands, priority, source dimension, and
whether placeholder input still needs a human. It does not execute commands or
prove scientific reproduction.

### `openrepro protocol-preflight <project_name>`

Runs protocol readiness preflight checks and writes:

```text
workspace/protocol_preflight.json
workspace/PROTOCOL_PREFLIGHT.md
```

Preflight checks whether the protocol, coverage, action plan, data provenance,
experiment specs, quality gates, and review decisions are ready. Evidence
package freshness is advisory only so preflight can run before packaging.

### `openrepro evidence-binder <project_name>`

Binds traced claims to workflow evidence and writes:

```text
workspace/claim_evidence_binder.json
workspace/CLAIM_EVIDENCE_BINDER.md
```

The binder groups each claim with linked experiments, runs, registered data,
quality gate status, protocol coverage, and related review decisions. Missing
evidence is reported as workflow gaps, not as scientific failure or success.

### `openrepro validate-evidence-binder <project_name>`

Validates binder freshness and consistency, then writes:

```text
workspace/claim_evidence_binder_validation.json
workspace/CLAIM_EVIDENCE_BINDER_VALIDATION.md
```

Validation checks whether the stored binder still matches current claims,
coverage, review decisions, data, specs, and runs. It also checks claim counts
and missing-evidence consistency. It does not verify scientific correctness.

### `openrepro claim-signoff <project_name>`

Records or summarizes human signoffs for claim evidence binder records and writes:

```text
workspace/claim_signoffs.json
workspace/CLAIM_SIGNOFFS.md
```

Use `--claim-id`, `--decision`, and `--reviewer` together to record a decision.
Allowed decisions are `accepted_workflow_evidence`, `needs_more_evidence`,
`rejected`, and `deferred`. A signoff is a human workflow decision about the
evidence record; it does not prove scientific reproduction.

### `openrepro validate-claim-signoffs <project_name>`

Validates claim signoff coverage and freshness, then writes:

```text
workspace/claim_signoff_validation.json
workspace/CLAIM_SIGNOFF_VALIDATION.md
```

Validation checks whether every current binder claim has a current terminal
signoff, whether accepted claims still have complete evidence, whether signoff
snapshots match the current binder, and whether stale or orphan signoffs exist.
It does not verify scientific correctness.

### `openrepro claim-evidence-report <project_name>`

Generates a reviewer-facing claim evidence matrix and writes:

```text
reports/claim_evidence_report.json
reports/claim_evidence_report.md
```

The report combines the current claim evidence binder, binder validation, and
latest claim signoffs. It highlights open actions per claim and keeps policy
language explicit that workflow evidence is not scientific proof.

### `openrepro validate-claim-evidence-report <project_name>`

Validates claim evidence report freshness and consistency, then writes:

```text
reports/claim_evidence_report_validation.json
reports/claim_evidence_report_validation.md
```

Validation checks whether the stored report still matches the current binder,
binder validation, and claim signoffs. It also checks claim row counts, open
action counts, and whether a `ready` report is internally consistent.

### `openrepro reviewer-packet <project_name> [--zip]`

Generates a human reviewer handoff packet and writes:

```text
reports/reviewer_packet.json
reports/reviewer_packet.md
reports/reviewer_packet.zip
```

The packet summarizes claim evidence, signoffs, validations, open actions,
review order, and source artifact hashes. It is an organized workflow review
packet, not a scientific proof package.

### `openrepro review-site <project_name> [--zip]`

Generates a static human review site and writes:

```text
reports/review_site/index.html
reports/review_site_manifest.json
reports/review_site.zip
```

The site summarizes the reviewer packet, claim evidence matrix, evidence
package freshness, protocol preflight, quality gates, open actions, blockers,
and key artifact links. It is a static HTML handoff view; no Node or web server
is required.

### `openrepro timeline <project_name>`

Generates a unified project timeline and writes:

```text
workspace/project_timeline.json
workspace/PROJECT_TIMELINE.md
```

The timeline consolidates source ingestion, candidate reviews, verified
candidates, claim signoffs, review decisions, run manifests, quality gates, and
major evidence artifacts into chronological events for audit and collaboration.

### `openrepro collaboration-pack <project_name> [--zip]`

Generates a role-based collaboration handoff pack and writes:

```text
handoff/collaboration_pack.json
handoff/COLLABORATION_PACK.md
handoff/collaboration_pack.zip
```

The pack splits review work into maintainer, reviewer, experimenter, and
next-agent checklists. It also lists unresolved decisions, next safe commands,
readiness state, and files to inspect first.

### `openrepro refresh <project_name> [--zip]`

Refreshes derived workflow and handoff artifacts without running experiments or
closing human decisions. It writes:

```text
workspace/refresh_run.json
workspace/REFRESH_RUN.md
workspace/refresh_run.zip
```

Refresh records each step, failed step count, top failed step, and guardrails.
It can refresh downstream zip artifacts when `--zip` is passed.

### `openrepro rerun-experiment <project_name> --experiment-id ID --confirm`

Runs the same verified experiment scaffold again and records another normal
`run-experiment` output directory. It uses the same guardrails as
`run-experiment`: the scaffold must be runnable, inputs are refreshed, and the
command needs explicit `--confirm`.

### `openrepro compare-experiments <project_name> --experiment-id ID [--left-run PATH] [--right-run PATH]`

Compares two `run-experiment` outputs for the same experiment, defaulting to
the latest two runs for that experiment id, and writes:

```text
workspace/experiment_comparison.json
workspace/EXPERIMENT_COMPARISON.md
```

The comparison reports metric equality, metric deltas, runner hashes, raw input
hashes, normalized input hashes, spec hashes, and environment hashes. It is
repeatability evidence only; it does not claim paper reproduction success.

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

### `openrepro repair-plan <project_name> [--run-dir PATH]`

Writes advisory repair artifacts:

```text
workspace/repair_plan.json
workspace/REPAIR_PLAN.md
```

v0.4.0 repair plans do not edit files automatically. They convert diagnosis output into ordered manual repair suggestions.

### `openrepro repair <project_name> --dry-run [--run-dir PATH]`

Writes a controlled repair preview without mutating project or run files:

```text
workspace/repair_dry_run.json
workspace/REPAIR_DRY_RUN.md
```

For manifest mismatch and missing-manifest issues, the dry-run preview includes a unified diff showing how `manifest.json` would change if regenerated from files currently present on disk. Missing scientific artifacts are never fabricated.

To apply the manifest-only repair after reviewing the dry-run:

```bash
openrepro repair boc_demo --apply --only manifest --confirm
```

v0.6.1 apply mode does not generate missing scientific artifacts, edit
experiment code, change configuration values, or infer parameters.

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

### `openrepro compare-runs <project_name> [--left-run PATH] [--right-run PATH]`

Compares two run directories, defaulting to the latest two runs, and writes:

```text
workspace/run_comparison.json
workspace/RUN_COMPARISON.md
```

The comparison reports observed manifest status and metric differences only.

### `openrepro lineage <project_name>`

Writes project run lineage artifacts:

```text
workspace/run_lineage.json
workspace/RUN_LINEAGE.md
```

Each run entry records the parent command and SHA-256 hashes for the run
manifest, config snapshot, project source index, and verified candidates when
available. Experiment runs also include repeat group ids and repeat indexes so
same-experiment reruns can be audited. The lineage report is provenance
evidence only; it does not claim scientific reproduction success.

### `openrepro doctor <project_name>`

Checks local dependencies, project structure, project config, and provider readiness. It writes:

```text
workspace/doctor.json
workspace/DOCTOR.md
```

Doctor checks workflow readiness only; it does not claim scientific reproduction success.

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

Benchmark task files may use either the v0.3.0 fields (`expected_artifacts`, `evaluation_metrics`) or the v0.4.0 fields:

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

### `openrepro benchmark-suite --suite <suite.json> [--project-prefix PREFIX]`

Runs a collection of benchmark tasks and writes suite-level evidence under:

```text
benchmarks/runs/<timestamp>_<suite_id>_suite/
  benchmark_suite_result.json
  benchmark_suite_report.md
  manifest.json
```

Suite output is still workflow-compliance evidence only; it does not aggregate scientific reproduction scores.

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

### `openrepro evidence-package <project_name> [--zip]`

Generates a project-level evidence bundle:

```text
reports/evidence_package.json
reports/evidence_package.md
reports/evidence_package.zip
```

The package summarizes inspect output, workspace artifacts, experiment
scaffolds, run manifests, lineage, benchmark indexes, project reports, and
handoff completeness. It includes source fingerprints and artifact hashes so
`openrepro status` can report whether the package is current or stale. It is
intended as an auditable handover artifact, not as a scientific reproduction
claim.

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

v0.4.0 keeps `MockProvider` as the default and adds an explicit opt-in OpenAI-compatible provider path. Real calls require:

- `api.enable_real_api: true`
- a non-mock provider such as `openai`
- an environment variable such as `OPENAI_API_KEY`

Provider usage is recorded in:

```text
api_usage/api_usage.jsonl
api_usage/api_usage_summary.json
```

Mock and cached events use zero prompt tokens, zero completion tokens, zero total tokens, and zero estimated cost. The summary keeps `total_calls` at zero for mocked and cached events so the project does not invent real API usage. Real provider events are counted only from provider-returned usage data, and costs stay zero unless an auditable provider estimate is available.

Tracked fields include:

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

The `benchmarks/` directory contains a task schema, a sample task, a sample suite, generated benchmark run outputs, and a rebuildable benchmark index. Benchmarks report workflow-compliance evidence and provenance only. They do not report scientific benchmark scores or claim a paper has been reproduced.

## Roadmap snapshot

- v0.1.0: runnable CLI workflow and lightweight BOC-like demo.
- v0.2.0: PDF text extraction, artifact manifests, formula/parameter candidates, experiment plan validation, demo parameter sweeps.
- v0.3.0: provider interface, cache-aware API usage, benchmark runner, failure diagnosis and repair suggestions.
- v0.3.1: project inspection, `validate --all`, benchmark indexing, and compatible benchmark schema hardening.
- v0.4.0: opt-in OpenAI-compatible provider path, human-gated experiment scaffolds, benchmark suites, repair plans, and run comparison.
- v0.5.0: candidate approval artifacts, verified-input scaffolds, and controlled repair dry-run previews.
- v0.5.1: verified candidate and repair dry-run status surfaced through inspect, report, handoff, and status.
- v0.5.2: provider prompt/response preview redaction, cache namespace, and cache policy controls.
- v0.6.0: benchmark provenance fields and project run lineage artifacts.
- v0.6.1: confirmed manifest-only repair apply.
- v0.6.2: doctor checks, lineage status visibility, and expanded smoke coverage.
- v0.7.0: confirmed execution of verified experiment scaffolds.
- v0.7.1: candidate listing and review lifecycle.
- v0.7.2: status/inspect stabilization, smoke coverage, and release tag cleanup.
- v0.8.0: paper metadata, DOI candidates, and candidate evidence provenance.
- v0.8.1: experiment templates and template-specific run artifact validation.
- v0.8.2: template registry, `list-templates`, and scaffold expected-artifact diagnostics.
- v0.9.0: verified candidate to experiment input mapping, input snapshots, and input-aware template runners.
- v0.9.1: environment snapshots, runner/input/environment lineage hashes, and same-seed repeatability checks.
- v0.9.2: input validation, manual input overrides, and missing-input visibility.
- v0.9.3: repeat experiment execution, same-experiment comparison artifacts, and lineage repeat indexes.
- v1.0.0: project-level evidence packages for auditable handover.
- v1.0.1: evidence package freshness, artifact hashes, zip export, and handoff integration.
- v1.1.0: section-aware candidate provenance, caption indexes, and high-risk candidate visibility.
- v1.2.0: experiment specs, spec validation, run spec snapshots, and spec hashes.
- v1.2.1: spec source fingerprints, freshness inspection, strict validation, and comparison warnings.
- v1.3.0: data registry, data validation, run data snapshots, and data provenance in evidence outputs.
- v1.4.0: run quality gates, quality gate reports, and gate status in evidence outputs.
- v1.4.1: batch quality gates, failed-check summaries, and quality-gate diagnostics.
- v1.5.0: quality-gate-aware repair plans and repair dry-run previews.
- v1.6.0: claim traceability across candidates, experiments, data, and runs.
- v1.6.1: claim trace validation for freshness and link integrity.
- v1.7.0: workflow readiness scorecards across reproduction evidence dimensions.
- v1.7.1: actionable reproduction gaps and todo artifacts.
- v1.8.0: workflow checkpoint engine for normalized stage status.
- v1.8.1: guided advance dry-run plans.
- v1.9.0: human review board for outstanding review items.
- v1.9.1: human review decision records for review board items.
- v1.10.0: reproduction protocol with claim/data/experiment/run acceptance criteria.
- v1.10.1: protocol coverage checks for workflow evidence completeness.
- v1.11.0: protocol action plans from coverage gaps.
- v1.11.1: protocol readiness preflight checks.
- v1.12.0: claim evidence binders across trace, runs, data, and protocol coverage.
- v1.12.1: claim evidence binder freshness and consistency validation.
- v1.13.0: human claim signoffs for evidence binder records.
- v1.13.1: reviewer-facing claim evidence report across binder, validation, and signoffs.
- v1.14.0: claim signoff freshness and coverage validation.
- v1.14.1: claim evidence report freshness and consistency validation.
- v1.15.0: reviewer packet for human claim evidence review.
- v1.16.0: static review site for human-facing evidence handoff.
- v1.16.1: project timeline and decision log for audit handoff.
- v1.17.0: collaboration pack with role-based handoff checklists.
- v1.18.0: safe refresh pipeline for derived workflow and handoff artifacts.

See `ROADMAP.md` for details.

## Disclaimer

OpenRepro-Agent v1.18.0 is an engineering scaffold for reproducibility workflows. It should not be used to claim that a paper has been reproduced unless the user has independently verified formulas, parameters, code, data, and outputs.

## No fabricated results policy

This project must not fabricate:

- benchmark results
- user counts
- token usage
- cost estimates
- accuracy or efficiency improvements
- claims that a lightweight demo is a complete paper reproduction

Only actual generated artifacts should be reported.
