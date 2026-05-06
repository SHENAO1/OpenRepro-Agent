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

## API provider extensions

Real providers should be opt-in. They must write actual usage records and must not fabricate tokens or costs.
