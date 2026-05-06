# Contributing

Thanks for considering contributing to OpenRepro-Agent.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Contribution guidelines

- Keep v0.1.x lightweight and CLI-first.
- Do not add large frameworks unless there is a strong reason.
- Do not claim benchmark results without committed code and artifacts that reproduce them.
- Do not report token usage unless it comes from actual provider calls.
- Clearly distinguish confirmed facts, assumptions, placeholders, and future work.
- Add pytest tests for new commands and artifact schemas.

## Pull request checklist

- [ ] `pytest` passes.
- [ ] README or docs updated when behavior changes.
- [ ] New artifacts do not overwrite previous runs.
- [ ] API usage accounting remains honest and auditable.
