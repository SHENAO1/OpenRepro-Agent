#!/usr/bin/env bash
set -euo pipefail

PROJECT="boc_demo_smoke"
rm -rf "$PROJECT"

openrepro init "$PROJECT"
openrepro ingest "$PROJECT" --source examples/boc_notes.md
openrepro analyze "$PROJECT"
openrepro plan "$PROJECT"
openrepro run-demo "$PROJECT"
openrepro report "$PROJECT"
openrepro handoff "$PROJECT"
openrepro status "$PROJECT"

pytest

echo "Smoke test completed."
