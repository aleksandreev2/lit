# Sistema Bogatstva — Production Engine

Machine-executable production infrastructure for the novel project **«Система богатства»**.

GitHub is the execution/state layer: schemas, runtime, invariants, QA manifests, hashes and CI. Google Drive remains the human-facing editorial library for convenient Docs, references and final presentation files.

> Important: this repository is currently **public**. Do not commit private story material, unpublished full chapters, secrets, API keys, or sensitive reference files unless the repository visibility is intentionally changed.

## Current machine state

- Canon/HAPPENED through chapter 24.
- Current chapter: 25, not started.
- Runtime: `canon/runtime.yaml`.
- System mechanics/history: `canon/system.yaml`.
- Active arc router: `canon/active_arc.yaml`.
- Regression registry: `rules/regressions.yaml`.

## Local checks

```bash
python -m pip install '.[qa]'
python scripts/project_preflight.py
pytest -q
yamllint canon config
```

Optional Russian grammar/style review:

```bash
python -m pip install '.[grammar]'
python scripts/languagetool_check.py path/to/text.txt --json
```

LanguageTool output is a REVIEW source, not automatic fiction rewriting.

## Freeze model

A final chapter revision should carry a manifest whose SHA-256 values match the exact chapter/runtime/rule inputs used by QA. `scripts/freeze_check.py` rejects stale evidence after any dependent file changes.

## Third-party tooling

See `docs/TOOLING_AND_INTEGRATIONS.md`. The project currently integrates `jsonschema`, `pytest`, `yamllint`, Vale, and an optional LanguageTool adapter. Novel-specific frameworks are evaluated selectively rather than imported as competing canon authorities.
