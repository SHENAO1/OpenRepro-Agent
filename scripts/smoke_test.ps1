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
openrepro report $Project
openrepro handoff $Project
openrepro status $Project

pytest

Write-Host "Smoke test completed."
