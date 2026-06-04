#!/usr/bin/env bash
set -euo pipefail

PROJECT="boc_demo_smoke"
export PYTHONPATH="${PYTHONPATH:-}:src"
rm -rf "$PROJECT" boc_benchmark_smoke sample_boc_suite_project smoke_suite_sample_boc_like_demo_1 benchmarks/runs

python -m openrepro.cli init "$PROJECT"
python -m openrepro.cli configure-provider "$PROJECT" --provider mock --disable-real-api
python -m openrepro.cli ingest "$PROJECT" --source examples/boc_notes.md
python -m openrepro.cli analyze "$PROJECT"
python -m openrepro.cli plan "$PROJECT"
python -m openrepro.cli list-templates
python -m openrepro.cli list-candidates "$PROJECT"
python -m openrepro.cli review-candidates "$PROJECT" --candidate-id F001 --status needs_more_evidence --reviewer smoke
python -m openrepro.cli approve-candidates "$PROJECT" --all --reviewer smoke
mkdir -p "$PROJECT/data"
printf '{"samples":[1,2,3]}\n' > "$PROJECT/data/smoke_dataset.json"
python -m openrepro.cli register-data "$PROJECT" --path "$PROJECT/data/smoke_dataset.json" --role dataset --note smoke
python -m openrepro.cli validate-data "$PROJECT"
python -m openrepro.cli scaffold-experiment "$PROJECT" --experiment-id smoke_exp --template boc-like
python -m openrepro.cli set-input "$PROJECT" --experiment-id smoke_exp --name noise_std --value 0.05 --note smoke
python -m openrepro.cli set-input "$PROJECT" --experiment-id smoke_exp --name code_length --value 128 --note smoke
python -m openrepro.cli validate-inputs "$PROJECT" --experiment-id smoke_exp
python -m openrepro.cli validate-experiment-spec "$PROJECT" --experiment-id smoke_exp
python -m openrepro.cli run-experiment "$PROJECT" --experiment-id smoke_exp --confirm
python -m openrepro.cli quality-gate "$PROJECT"
python -m openrepro.cli rerun-experiment "$PROJECT" --experiment-id smoke_exp --confirm
python -m openrepro.cli compare-experiments "$PROJECT" --experiment-id smoke_exp
python -m openrepro.cli run-demo "$PROJECT"
python -m openrepro.cli validate "$PROJECT"
python -m openrepro.cli validate "$PROJECT" --all
python -m openrepro.cli inspect "$PROJECT"
python -m openrepro.cli run-sweep "$PROJECT" --noise-std 0.0 --noise-std 0.1 --seed 42
python -m openrepro.cli quality-gate "$PROJECT"
python -m openrepro.cli validate "$PROJECT"
python -m openrepro.cli validate "$PROJECT" --all
python -m openrepro.cli compare-runs "$PROJECT"
python -m openrepro.cli quality-gate "$PROJECT" --all
python -m openrepro.cli lineage "$PROJECT"
python -m openrepro.cli trace-claims "$PROJECT" --validate
python -m openrepro.cli validate-claims "$PROJECT"
python -m openrepro.cli scorecard "$PROJECT"
python -m openrepro.cli diagnose "$PROJECT"
python -m openrepro.cli repair-plan "$PROJECT"
python -m openrepro.cli repair "$PROJECT" --dry-run
python -m openrepro.cli repair "$PROJECT" --apply --only manifest --confirm
python -m openrepro.cli doctor "$PROJECT"
python -m openrepro.cli benchmark --task benchmarks/sample_task.json --project boc_benchmark_smoke
python -m openrepro.cli benchmark-suite --suite benchmarks/sample_suite.json --project-prefix smoke_suite
python -m openrepro.cli benchmark-index
python -m openrepro.cli gaps "$PROJECT"
python -m openrepro.cli todo "$PROJECT"
python -m openrepro.cli checkpoints "$PROJECT"
python -m openrepro.cli advance "$PROJECT" --dry-run
python -m openrepro.cli review-board "$PROJECT"
python -m openrepro.cli protocol "$PROJECT"
python -m openrepro.cli protocol-coverage "$PROJECT"
python -m openrepro.cli protocol-plan "$PROJECT"
python -m openrepro.cli protocol-preflight "$PROJECT"
python -m openrepro.cli evidence-binder "$PROJECT"
python -m openrepro.cli validate-evidence-binder "$PROJECT"
python -m openrepro.cli claim-signoff "$PROJECT" --claim-id formula:F001 --decision accepted_workflow_evidence --reviewer smoke
python -m openrepro.cli claim-signoff "$PROJECT" --claim-id formula:F002 --decision accepted_workflow_evidence --reviewer smoke
python -m openrepro.cli validate-claim-signoffs "$PROJECT"
python -m openrepro.cli claim-evidence-report "$PROJECT"
python -m openrepro.cli validate-claim-evidence-report "$PROJECT"
python -m openrepro.cli reviewer-packet "$PROJECT" --zip
python -m openrepro.cli timeline "$PROJECT"
python -m openrepro.cli report "$PROJECT"
python -m openrepro.cli handoff "$PROJECT"
python -m openrepro.cli evidence-package "$PROJECT" --zip
python -m openrepro.cli review-site "$PROJECT" --zip
python -m openrepro.cli collaboration-pack "$PROJECT" --zip
python -m openrepro.cli refresh "$PROJECT" --zip
python -m openrepro.cli status "$PROJECT"

mkdir -p .codex_tmp/pytest-basetemp
python -m pytest -q --basetemp .codex_tmp/pytest-basetemp

echo "Smoke test completed."
