# Session State

Updated: 2026-05-06

## Current Goal

Solidify OpenRepro-Agent v0.1.0 as a trustworthy baseline before adding v0.2.0 features.

## Current State

- The repository has the v0.1.0 Python CLI scaffold in place.
- The local working directory started without a Git repository.
- No project-specific `AGENTS.md` or prior baton files were present.
- v0.1.0 keeps mock API usage, mock/rule-based analysis, PDF placeholder ingestion, and a lightweight BOC-like demo by design.

## Latest Evidence

- Unit tests pass when pytest uses a workspace-local base temp directory:

```powershell
python -m pytest -q --basetemp E:\Code\OpenRepro-Agent\.codex_tmp\pytest-basetemp
```

- Default pytest temp discovery can fail on this Windows machine with `PermissionError` for `C:\Users\87139\AppData\Local\Temp\pytest-of-87139`.
- Editable install into `.codex_tmp\venv` completed successfully.
- Full CLI smoke flow passed from `.codex_tmp\smoke_workspace` after changing the CLI success prefix from a Unicode checkmark to ASCII `OK`.
- The generated `figures/correlation.png` was opened and visually confirmed as non-empty.
- Git repository was initialized on `main`, the v0.1.0 baseline was committed, and the `v0.1.0` tag was created.
- Public GitHub repository was created and pushed: `https://github.com/SHENAO1/OpenRepro-Agent`.
- Remote `origin` uses SSH: `git@github.com:SHENAO1/OpenRepro-Agent.git`.
- Remote default branch is `main`; tag `v0.1.0` is present on GitHub.

## Exact Next Step

Start v0.2.0 with artifact manifest design, or create GitHub issues for the deferred roadmap items.

## Deferred v0.2.0 Work

- Artifact manifest and run-evidence validation.
- PDF text extraction with provenance.
- Formula candidate detection.
- Parameter table extraction.
- Parameter sweeps for demo runs.
