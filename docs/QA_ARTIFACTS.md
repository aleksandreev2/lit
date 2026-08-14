# Chapter QA artifacts

Production Engine v2 can generate deterministic editor-support artifacts from an explicitly supplied chapter candidate. The generator does not write prose, decide literary quality, promote canon, or turn a heuristic hit into a BLOCK by itself.

## Command

```bash
python scripts/qa_artifacts.py path/to/candidate.txt path/to/output \
  --parent-runtime canon/runtime.yaml \
  --character-state canon/state.yaml
python scripts/qa_artifact_check.py path/to/output/artifact_manifest.json
```

No command is wired to `current/025` automatically. Chapter 25 remains `NOT_STARTED` until a real candidate is deliberately supplied later.

## Generated files

- `dialogue_only.txt` — dialogue lines only.
- `narration_only.txt` — non-empty narration lines only.
- `question_audit.json` — dialogue questions, next-turn size and exposition-question candidates.
- `dialogue_windows.json` — local dialogue windows for semantic review.
- `repeated_phrases.json` — deterministic repeated 3–5 token phrases.
- `text_signals.json` — existing short-reply/reviewer-agent rules exposed as reusable data.
- `russian_naturalness.json` — morphology-aware Russian government/calque/collocation findings.
- `pronoun_coreference.json` — fast local pronoun/coreference evidence.
- `semantic_coreference.json` — contextual long-distance, speaker-ownership and zero-subject review evidence; Stanza remains `NOT_RUN` unless explicit model output is supplied to the standalone semantic reviewer.
- `comeback_signals.json` — `поэтому / вот именно / тем более` candidates.
- `entity_mentions.json` — low-confidence capitalized entity/name candidates.
- `knowledge_claim_candidates.json` — lines containing knowledge/belief acquisition language.
- `numeric_mentions.json` — numeric, money, rate and percentage mentions.
- `research_candidates.json` — money/rate, URL and Latin-script entity candidates that may require source work.
- `continuity_audit.json` — source hashes plus known/unresolved entity mentions against optional structured state.
- `chapter_delta_candidate.json` — deliberately empty promotion proposal scaffold with `automatic_promotion_allowed: false`.
- `artifact_manifest.json` — source/rule bindings plus every generated artifact hash and byte size.

`qa_artifact_check.py` validates the manifest schema, source hash, naturalness/dialogue rules, pronoun rules, semantic-coreference rules, artifact path containment, SHA-256 and byte size. Any post-generation mutation of the source, rule registries or artifacts breaks verification.

Character state is also an explicit dependency of the generated artifact package. Changing aliases, grammatical gender or other structured character evidence invalidates pronoun/coreference output and the downstream generated-artifact evidence path.

## Detection classes

Deterministic output means the same input/revision produces the same report. It does **not** mean every candidate is a literary defect.

- `DETERMINISTIC` — mechanical extraction/counting.
- `HEURISTIC` — a reproducible review candidate that needs editor judgment.
- semantic-only rules remain outside automatic PASS/BLOCK unless a later semantic reviewer records evidence.

Entity extraction is intentionally conservative and labeled low confidence. It does not claim NER-grade truth. Pronoun/coreference findings are REVIEW candidates rather than automatic corrections; see `docs/PRONOUN_COREFERENCE_QA.md` and `docs/SEMANTIC_COREFERENCE_QA.md`.

## Russian NLP evaluation

The fast artifact layer uses two compact, local dependencies:

- Razdel for rule-based sentence/token segmentation;
- `pymorphy3` for Russian morphology and normalized lemma/case/gender/number evidence.

The Natasha/SlovNet ecosystem remains useful for an optional heavier syntax tier, but its model assets are unnecessary for the fast deterministic candidate reports. Stanza 1.14.0 is connected separately as an optional dependency/coreference semantic challenger and is deliberately excluded from the required fast CI dependency set.

## Regression locks

Machine-detectable rules are schema-backed and carry:

- stable ID and owner family;
- BLOCK/REVIEW severity;
- description;
- positive/negative examples;
- deterministic/heuristic/semantic detection type;
- fixture/test path where machine detection exists;
- affected lifecycle stages;
- introduction provenance;
- supersession link.

The main naturalness/dialogue registry lives at `rules/regressions.yaml`. Fast pronoun/coreference rules live at `rules/pronoun_regressions.yaml`. Contextual rules live at `rules/semantic_coreference_regressions.yaml`. `scripts/regression_check.py` validates all registries and rejects duplicate stable IDs across them.

Run:

```bash
python scripts/regression_check.py
python scripts/russian_naturalness.py --self-test
python scripts/pronoun_coreference.py --self-test
python scripts/semantic_coreference.py --self-test
```

Deterministic or heuristic rules without an existing fixture/test file fail the register check. The specialized corpora additionally require both bad-case coverage and explicit false-positive guards for their executable rules.
