$ErrorActionPreference = "Stop"
$Project = "boc_demo_smoke"
$GeneratedProjects = @($Project, "boc_benchmark_smoke", "sample_boc_suite_project", "smoke_suite_sample_boc_like_demo_1")

foreach ($Item in $GeneratedProjects) {
  if (Test-Path $Item) {
    Remove-Item -Recurse -Force $Item
  }
}
if (Test-Path benchmarks\runs) {
  Remove-Item -Recurse -Force benchmarks\runs
}

openrepro init $Project
openrepro configure-provider $Project --provider mock --disable-real-api
openrepro ingest $Project --source examples/boc_notes.md
openrepro analyze $Project
openrepro plan $Project
openrepro scaffold-experiment $Project --experiment-id smoke_exp
openrepro run-demo $Project
openrepro validate $Project
openrepro validate $Project --all
openrepro inspect $Project
openrepro run-sweep $Project --noise-std 0.0 --noise-std 0.1 --seed 42
openrepro validate $Project
openrepro validate $Project --all
openrepro compare-runs $Project
openrepro diagnose $Project
openrepro repair-plan $Project
openrepro benchmark --task benchmarks/sample_task.json --project boc_benchmark_smoke
openrepro benchmark-suite --suite benchmarks/sample_suite.json --project-prefix smoke_suite
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
