#!/usr/bin/env bash
set -euo pipefail

PROJECT="boc_demo_smoke"
rm -rf "$PROJECT"

openrepro init "$PROJECT"
openrepro ingest "$PROJECT" --source examples/boc_notes.md
openrepro analyze "$PROJECT"
openrepro plan "$PROJECT"
openrepro run-demo "$PROJECT"
openrepro validate "$PROJECT"
openrepro run-sweep "$PROJECT" --noise-std 0.0 --noise-std 0.1 --seed 42
openrepro validate "$PROJECT"
openrepro report "$PROJECT"
openrepro handoff "$PROJECT"
openrepro status "$PROJECT"

mkdir -p .codex_tmp/pytest-basetemp
python -m pytest -q --basetemp .codex_tmp/pytest-basetemp

echo "Smoke test completed."
