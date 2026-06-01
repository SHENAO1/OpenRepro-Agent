$ErrorActionPreference = "Stop"
$Project = "boc_demo_smoke"

if (Test-Path $Project) {
  Remove-Item -Recurse -Force $Project
}

openrepro init $Project
openrepro ingest $Project --source examples/boc_notes.md
openrepro analyze $Project
openrepro plan $Project
openrepro run-demo $Project
openrepro validate $Project
openrepro validate $Project --all
openrepro inspect $Project
openrepro run-sweep $Project --noise-std 0.0 --noise-std 0.1 --seed 42
openrepro validate $Project
openrepro validate $Project --all
openrepro diagnose $Project
openrepro benchmark --task benchmarks/sample_task.json --project boc_benchmark_smoke
openrepro benchmark-index
openrepro report $Project
openrepro handoff $Project
openrepro status $Project

New-Item -ItemType Directory -Force .codex_tmp\pytest-basetemp | Out-Null
python -m pytest -q --basetemp .codex_tmp\pytest-basetemp
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Write-Host "Smoke test completed."
