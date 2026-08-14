# Semantic/coreference QA v2

The Production Engine has three deliberately separate Russian reference-analysis tiers. None of them may silently rewrite fiction or declare literary quality by itself.

## Tier 1 — fast pronoun audit

`scripts/pronoun_coreference.py` uses Razdel plus pinned `pymorphy3` morphology and a short local window. It finds mechanical review candidates such as ambiguous `он/она`, gender/number mismatch, possessive-owner ambiguity, and `свой` chains.

This tier is compact enough for required CI.

## Tier 2 — contextual semantic/coreference review

`scripts/semantic_coreference.py` extends the review window without pretending to solve general coreference. Its registry is `rules/semantic_coreference_regressions.yaml`.

Current stable REVIEW rules:

- `SB-CTX-001` — a personal antecedent exists only two to four sentences back;
- `SB-CTX-002` — a run of three or more dialogue turns has at least three plausible participants but insufficient explicit speaker attribution;
- `SB-CTX-003` — an omitted subject is compatible with multiple recent people;
- `SB-CTX-004` — supplied Stanza evidence picks a chain where the fast layer reports ambiguity;
- `SB-CTX-005` — supplied Stanza evidence contains a long-distance chain spanning at least three sentence positions;
- `SB-CTX-006` — supplied Stanza evidence contains an explicit empty/zero mention.

Every rule is `REVIEW`, not `BLOCK`. Russian pro-drop, dialogue alternation, and long-distance reference can all be intentional. The engine surfaces evidence and context for an editor; it does not make the literary decision.

Run the reproducible synthetic corpus with:

```bash
python scripts/semantic_coreference.py --self-test
```

Run it against an explicitly supplied text with:

```bash
python scripts/semantic_coreference.py path/to/text.txt \
  --character-state path/to/state.yaml \
  --json
```

The fixture corpus is synthetic and contains no chapter-25 prose or story-state dependency.

## Tier 3 — optional Stanza challenger

`stanza==1.14.0` remains an optional heavy dependency rather than part of `.[qa]`. The adapter requests Russian tokenization, POS, lemma, dependency parsing and CorefUD coreference and records model evidence in JSON.

The adapter sets `download_method=None`. It never downloads or refreshes model assets while reviewing a chapter. Model installation is an explicit separate operation.

Stanza coreference output can include empty/zero mentions; when present, `stanza_coreference_review.py` preserves them with `is_zero: true`. The Production Engine does not assume every Russian input will produce zero mentions.

A Stanza chain is a challenger result, not canon authority. In particular, `SB-CTX-004` intentionally reports disagreement/extra specificity instead of accepting the model assignment as truth.

Upstream references:

- Stanza coreference: `https://stanfordnlp.github.io/stanza/coref.html`
- Stanza releases: `https://github.com/stanfordnlp/stanza/releases`

## Speaker attribution boundary

The contextual tier does not claim to infer the true speaker of raw literary dialogue. `SB-CTX-002` only detects a risky structural condition: more than two plausible participants plus an under-attributed consecutive dialogue run.

Stanza 1.14 also supports speaker metadata for transcript-style processing. That is useful when speaker labels already exist; it is not a replacement for literary speaker inference from raw prose.

BookNLP was evaluated because it includes quote attribution and literary coreference, but its public installation/model path is English-oriented, including English spaCy assets and LitBank-based resources. It is therefore not imported into the Russian production path.

Source: `https://github.com/booknlp/booknlp`

## Artifact and invalidation contract

`qa_artifacts.py` emits `semantic_coreference.json` alongside `pronoun_coreference.json`. `artifact_manifest.json` binds the exact SHA-256 of `rules/semantic_coreference_regressions.yaml`.

The dependency graph also makes `semantic_coreference_qa` depend on chapter text, character state and rules. `generated_artifact_manifest` now depends on character state as well. A changed character alias/gender/state therefore invalidates both coreference QA and the generated evidence package before freeze/release.
