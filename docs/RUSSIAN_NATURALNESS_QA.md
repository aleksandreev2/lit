# Russian Naturalness QA

`Russian Naturalness QA` is a narrow, regression-driven layer for machine-like or malformed
Russian constructions that ordinary spelling checks can miss.

It is intentionally separate from semantic editorial approval. A clean deterministic result
means only that the configured construction patterns were not found.

## Current v1 scope

The first rule family targets short broken clauses where a personal pronoun is followed by an
adverb that cannot safely carry the intended predicate by itself.

Examples that are detected:

- `Я ладно.` — `SB-RUS-001`, blocking deterministic signal.
- `Я нормально.` — `SB-RUS-002`, blocking deterministic signal in a standalone statement.
- `Я всё нормально.` — `SB-RUS-003`, blocking deterministic signal.
- `Ты рано.` — `SB-RUS-004`, medium-confidence review signal.

Contextual forms that must remain clean include:

- `Ладно.`
- `Я в порядке.`
- `У меня всё нормально.`
- `Я нормально себя чувствую.`
- `Я нормально, спасибо.`
- `Ты нормально?`
- `Ты рано пришёл.`

## Rule authority

Executable matcher metadata lives in `rules/regressions.yaml`. This is deliberate: the matcher
configuration is part of the same rule authority that is already bound into chapter freeze
inputs.

A naturalness matcher uses an exact `TOKEN_PATTERN` over normalized word tokens. The current
matcher supports:

- one or more token positions;
- an `any_of` vocabulary for each position;
- optional question skipping to avoid known colloquial false positives;
- `BLOCK` or `REVIEW` severity;
- confidence, message, and correction examples.

The detector implementation is in `scripts/russian_naturalness.py`.

## Regression corpus

`tests/fixtures/russian_naturalness_cases.yaml` is the executable good/bad corpus. Every case has
an exact set of expected rule IDs. CI runs:

```text
python scripts/russian_naturalness.py --self-test
```

A new rule is not considered production-ready until it has both positive and negative corpus
coverage. False-positive examples are as important as known bad examples.

## Chapter artifact

When `scripts/qa_artifacts.py` is run for a chapter candidate it writes
`russian_naturalness.json`. The artifact contains:

- overall naturalness status (`PASS`, `REVIEW`, or `BLOCK`);
- counts by severity;
- line and sentence for every finding;
- stable regression rule ID;
- confidence and detection type;
- reviewer message and suggested repairs.

The QA artifact manifest also stores the exact SHA-256 of the regression rule file. If the rules
change after artifact generation, `scripts/qa_artifact_check.py` rejects the old artifact package
as stale.

## What v1 does not claim

This is not yet general Russian grammar, morphology, dependency parsing, pronoun coreference, or
semantic lexical choice. LanguageTool remains useful as an independent optional reviewer, and a
later NLP tier can add morphology/syntax when it demonstrably improves recall without unacceptable
false positives.

The v1 goal is narrower: convert recurring, high-value machine-Russian defects into permanent,
testable regression locks instead of relying on memory during editing.
