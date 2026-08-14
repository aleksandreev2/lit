# Russian pronoun and coreference QA

Production Engine separates a fast reproducible pronoun audit from a heavier semantic coreference challenger. Neither layer is allowed to rewrite prose, decide canon, or replace an editor.

## Fast required tier

Run the synthetic regression corpus:

```bash
python scripts/pronoun_coreference.py --self-test
```

Run the audit on an explicitly supplied chapter candidate:

```bash
python scripts/pronoun_coreference.py path/to/candidate.txt \
  --character-state canon/state.yaml \
  --json
```

The same fast audit is generated automatically as `pronoun_coreference.json` when `scripts/qa_artifacts.py` is run on a supplied candidate.

The implementation uses the already pinned `pymorphy3` morphology plus Razdel sentence segmentation. It considers noun/name candidates in the current sentence before a pronoun and in the preceding sentence. Character-state metadata, when explicitly present, can supply aliases and grammatical gender. The current project state does not gain any character facts merely because the schema can represent them.

### Stable review rules

`rules/pronoun_regressions.yaml` contains five schema-backed REVIEW rules:

- `SB-PRN-001` — multiple compatible antecedents for `он / она / оно / они`;
- `SB-PRN-002` — no compatible recent antecedent while recent candidates with known gender/number exist;
- `SB-PRN-003` — multiple compatible owners for possessive `его / её / их` before a noun;
- `SB-PRN-004` — a non-reflexive possessive appears to point back to the nominative subject and `свой` may have been intended;
- `SB-PRN-005` — `свой` inherits ambiguity from an already ambiguous personal subject pronoun in the same sentence.

Every rule is REVIEW rather than BLOCK. A detected ambiguity can be intentional, an omitted/off-page antecedent may be valid, and literary Russian regularly uses context that a short deterministic window cannot fully resolve.

### Evidence retained

Findings retain:

- current, previous and next sentence;
- pronoun/possessive token and location;
- expected gender/number where relevant;
- recent candidate antecedents or owners;
- candidate source (`CHARACTER_STATE`, morphology name, morphology noun or synthetic group);
- character ID when the candidate comes from structured state;
- explicit `automatic_rewrite_allowed: false`.

The corpus contains only synthetic prose. It includes both target defects/ambiguities and false-positive guards. The corpus gate fails if a rule lacks a bad example or lacks a guard.

## Optional Stanza semantic challenger

Stanza 1.14.0 is available as an optional dependency:

```bash
python -m pip install '.[coref]'
```

Install Russian models deliberately outside the adapter, then run:

```bash
python scripts/stanza_coreference_review.py path/to/candidate.txt --json
```

The adapter requests `tokenize,pos,lemma,depparse,coref` and uses `download_method=None`. It therefore does not download or refresh models implicitly while reviewing a chapter. Missing Stanza or missing local models produces `NOT_AVAILABLE` rather than a fake PASS.

The output exposes dependency evidence and Stanza `Document.coref` chains. It is always semantic REVIEW evidence. Stanza's Russian CorefUD model is transformer-based and is intentionally not installed in the fast required CI job.

## Why not automatic corrections

Coreference is not equivalent to morphology. Examples such as these require discourse and scene understanding:

```text
Герман подошёл к Максиму. Он достал телефон.
Анна посмотрела на Милену и поправила её платье.
Анна сказала Милене, что она забрала свою сумку.
```

A machine can identify competing candidates, but deciding the intended referent can require character goals, focus, world state, paragraph structure and authorial intent. Therefore the system narrows review targets and preserves evidence rather than rewriting the sentence.

## Character metadata contract

`schemas/structured_state.schema.json` now permits two optional fields on a character:

```yaml
aliases: ["Саша"]
grammatical_gender: MASC
```

Allowed grammatical genders are `MASC`, `FEM`, `NEUT` and `UNKNOWN`. These fields become authoritative only when real project state is deliberately populated through the normal canon/provenance workflow. The QA layer never infers a missing canon field and writes it back automatically.

## Invalidation and freeze

The dependency graph contains `pronoun_coreference_qa`, depending on:

- chapter text;
- structured character state;
- regression rules.

`qa_manifest` depends on this node. A relevant dependency change therefore makes downstream QA/freeze evidence stale through the normal graph rather than leaving an old pronoun review silently valid.

## Limits

The fast tier is intentionally conservative:

- its deterministic context window is local rather than chapter-wide;
- morphology is not a dependency parse;
- quotation/speaker ownership is not fully solved;
- zero pronoun findings does not prove semantic correctness;
- Stanza output can also be wrong and remains reviewer evidence;
- no result is a substitute for the final semantic reread.
