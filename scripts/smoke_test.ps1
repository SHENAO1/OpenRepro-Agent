$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src;$env:PYTHONPATH"
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

python -m openrepro.cli init $Project
python -m openrepro.cli configure-provider $Project --provider mock --disable-real-api
python -m openrepro.cli ingest $Project --source examples/boc_notes.md
python -m openrepro.cli analyze $Project
python -m openrepro.cli plan $Project
python -m openrepro.cli list-templates
python -m openrepro.cli list-candidates $Project
python -m openrepro.cli review-candidates $Project --candidate-id F001 --status needs_more_evidence --reviewer smoke
python -m openrepro.cli approve-candidates $Project --all --reviewer smoke
New-Item -ItemType Directory -Force "$Project\data" | Out-Null
Set-Content -Encoding UTF8 "$Project\data\smoke_dataset.json" '{"samples":[1,2,3]}'
python -m openrepro.cli register-data $Project --path "$Project\data\smoke_dataset.json" --role dataset --note smoke
python -m openrepro.cli validate-data $Project
python -m openrepro.cli scaffold-experiment $Project --experiment-id smoke_exp --template boc-like
python -m openrepro.cli set-input $Project --experiment-id smoke_exp --name noise_std --value 0.05 --note smoke
python -m openrepro.cli set-input $Project --experiment-id smoke_exp --name code_length --value 128 --note smoke
python -m openrepro.cli validate-inputs $Project --experiment-id smoke_exp
python -m openrepro.cli validate-experiment-spec $Project --experiment-id smoke_exp
python -m openrepro.cli run-experiment $Project --experiment-id smoke_exp --confirm
python -m openrepro.cli quality-gate $Project
python -m openrepro.cli rerun-experiment $Project --experiment-id smoke_exp --confirm
python -m openrepro.cli compare-experiments $Project --experiment-id smoke_exp
python -m openrepro.cli run-demo $Project
python -m openrepro.cli validate $Project
python -m openrepro.cli validate $Project --all
python -m openrepro.cli inspect $Project
python -m openrepro.cli run-sweep $Project --noise-std 0.0 --noise-std 0.1 --seed 42
python -m openrepro.cli quality-gate $Project
python -m openrepro.cli validate $Project
python -m openrepro.cli validate $Project --all
python -m openrepro.cli compare-runs $Project
python -m openrepro.cli quality-gate $Project --all
python -m openrepro.cli lineage $Project
python -m openrepro.cli trace-claims $Project
python -m openrepro.cli diagnose $Project
python -m openrepro.cli repair-plan $Project
python -m openrepro.cli repair $Project --dry-run
python -m openrepro.cli repair $Project --apply --only manifest --confirm
python -m openrepro.cli doctor $Project
python -m openrepro.cli benchmark --task benchmarks/sample_task.json --project boc_benchmark_smoke
python -m openrepro.cli benchmark-suite --suite benchmarks/sample_suite.json --project-prefix smoke_suite
python -m openrepro.cli benchmark-index
python -m openrepro.cli report $Project
python -m openrepro.cli handoff $Project
python -m openrepro.cli evidence-package $Project --zip
python -m openrepro.cli status $Project

New-Item -ItemType Directory -Force .codex_tmp\pytest-basetemp | Out-Null
python -m pytest -q --basetemp .codex_tmp\pytest-basetemp
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Write-Host "Smoke test completed."
