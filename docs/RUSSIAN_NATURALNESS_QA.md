# Russian Naturalness QA

`Russian Naturalness QA` is a regression-driven layer for machine-like or malformed Russian
constructions that ordinary spelling checks can miss.

It is intentionally separate from semantic editorial approval. A clean deterministic result means
only that the configured construction patterns were not found.

## v2 scope

v2 keeps the exact-token rules from v1 and adds morphology-aware checks powered by `pymorphy3`.
The checker now has three matcher families:

- `TOKEN_PATTERN` — exact normalized short-clause patterns;
- `LEMMA_WINDOW` — inflection-independent ordered lemma patterns with a bounded gap;
- `CASE_AFTER` — case-government checks after a trigger such as `согласно` or `вопреки`.

This lets one rule cover inflected variants instead of enumerating every surface form. For example,
one `оплатить + за` rule catches `оплатил за`, `оплатила за`, and other forms whose lemma is
`оплатить`.

Current examples include:

- `Я ладно.` — blocking malformed personal-state construction;
- `Я нормально.` — blocking malformed standalone personal-state construction;
- `Согласно приказа...` — blocking case-government error;
- `Вопреки приказа...` — blocking case-government error;
- `оплатить за...` — blocking government error;
- `обсудить о...`, `надеяться о...`, `интересоваться о...`, `касаться о...` — blocking government
  errors;
- `это делает смысл` — blocking English calque;
- `я имею идею`, `я имею вопрос` — review-only possession-calque signals because marked usage can
  be deliberate;
- `взять душ` — blocking collocation/calque signal;
- `спросить вопрос` — review-only nonstandard collocation signal;
- `я в порядке с этим` — blocking acceptance calque;
- `уверенность о...` — review-only suspicious government.

The distinction between `BLOCK` and `REVIEW` is intentional. High-confidence malformed forms may
block promotion; constructions that can exist as marked, regional, colloquial, or deliberate style
remain reviewer signals.

## Context evidence

Every finding now includes the previous and next detected sentence when available. The matcher does
not pretend this is full discourse understanding, but the reviewer no longer sees a suspicious
short reply in isolation. For example, a finding for `Я нормально.` can carry the preceding
`Как ты?` and the following line as evidence.

## Rule authority

Executable matcher metadata lives in `rules/regressions.yaml`. This is deliberate: matcher
configuration is part of the same rule authority already bound into chapter freeze inputs.

A matcher stores its confidence, reviewer message, repair examples, severity, and stable rule ID.
The chapter QA artifact records the exact SHA-256 of `rules/regressions.yaml`; if the rules change
after artifact generation, `scripts/qa_artifact_check.py` rejects the old package as stale.

## Regression corpus

`tests/fixtures/russian_naturalness_cases.yaml` is the executable good/bad corpus. Every case has an
exact expected rule set. v2 additionally requires every executable Russian naturalness rule to
have:

1. at least one bad fixture that exercises the rule;
2. at least one explicit false-positive guard fixture that must remain clean.

CI runs:

```text
python scripts/russian_naturalness.py --self-test
```

A new rule is not production-ready without both sides of that coverage. False-positive protection
is treated as a first-class regression requirement rather than an informal note.

## Chapter artifact

When `scripts/qa_artifacts.py` is run for a chapter candidate it writes
`russian_naturalness.json`. Findings contain:

- overall status (`PASS`, `REVIEW`, or `BLOCK`);
- stable regression rule ID;
- severity and confidence;
- source line and sentence;
- previous/next sentence context;
- matcher type;
- token/lemma/case evidence used by the matcher;
- reviewer message and suggested repairs.

## Open-source choices

v2 uses `pymorphy3==2.0.6` as the mandatory morphology layer. It is the maintained continuation of
`pymorphy2`, supports current Python releases used by the project, and does not require downloading
large neural models during CI.

The following tools were evaluated but are not mandatory in this tier:

- full Natasha/SlovNet — useful morphology and dependency syntax, but heavier model-backed analysis
  is better reserved for a later semantic/coreference tier;
- Stanza — capable Universal Dependencies parsing, but model download/runtime cost is unnecessary
  for the deterministic government and collocation rules in v2;
- Yargy — strong rule-based extraction, but its current public package stack is centered on
  `pymorphy2`; adding it would not improve the narrow v2 checks enough to justify another parser
  authority;
- LanguageTool — remains a useful independent optional reviewer, not the sole authority for fiction
  naturalness.

## What v2 still does not claim

This is not yet full Russian semantic correctness, dependency-based argument structure, pronoun
coreference, or general lexical-choice understanding. A sentence can be grammatically parseable
and still be bad fiction, contextually wrong, or semantically absurd.

The next tier should target dependency syntax and pronoun/coreference candidates, but only after a
measured corpus demonstrates useful recall without turning ordinary literary ellipsis into noise.
