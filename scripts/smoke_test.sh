#!/usr/bin/env bash
set -euo pipefail

PROJECT="boc_demo_smoke"
rm -rf "$PROJECT" boc_benchmark_smoke sample_boc_suite_project smoke_suite_sample_boc_like_demo_1 benchmarks/runs

openrepro init "$PROJECT"
openrepro configure-provider "$PROJECT" --provider mock --disable-real-api
openrepro ingest "$PROJECT" --source examples/boc_notes.md
openrepro analyze "$PROJECT"
openrepro plan "$PROJECT"
openrepro scaffold-experiment "$PROJECT" --experiment-id smoke_exp
openrepro run-demo "$PROJECT"
openrepro validate "$PROJECT"
openrepro validate "$PROJECT" --all
openrepro inspect "$PROJECT"
openrepro run-sweep "$PROJECT" --noise-std 0.0 --noise-std 0.1 --seed 42
openrepro validate "$PROJECT"
openrepro validate "$PROJECT" --all
openrepro compare-runs "$PROJECT"
openrepro diagnose "$PROJECT"
openrepro repair-plan "$PROJECT"
openrepro benchmark --task benchmarks/sample_task.json --project boc_benchmark_smoke
openrepro benchmark-suite --suite benchmarks/sample_suite.json --project-prefix smoke_suite
openrepro benchmark-index
openrepro report "$PROJECT"
openrepro handoff "$PROJECT"
openrepro status "$PROJECT"

mkdir -p .codex_tmp/pytest-basetemp
python -m pytest -q --basetemp .codex_tmp/pytest-basetemp

echo "Smoke test completed."
