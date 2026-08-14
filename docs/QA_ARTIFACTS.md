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
- `comeback_signals.json` — `поэтому / вот именно / тем более` candidates.
- `entity_mentions.json` — low-confidence capitalized entity/name candidates.
- `knowledge_claim_candidates.json` — lines containing knowledge/belief acquisition language.
- `numeric_mentions.json` — numeric, money, rate and percentage mentions.
- `research_candidates.json` — money/rate, URL and Latin-script entity candidates that may require source work.
- `continuity_audit.json` — source hashes plus known/unresolved entity mentions against optional structured state.
- `chapter_delta_candidate.json` — deliberately empty promotion proposal scaffold with `automatic_promotion_allowed: false`.
- `artifact_manifest.json` — source hash plus every generated artifact hash and byte size.

`qa_artifact_check.py` validates the manifest schema, source hash, artifact path containment, SHA-256 and byte size. Any post-generation mutation breaks verification.

## Detection classes

Deterministic output means the same input/revision produces the same report. It does **not** mean every candidate is a literary defect.

- `DETERMINISTIC` — mechanical extraction/counting.
- `HEURISTIC` — a reproducible review candidate that needs editor judgment.
- semantic-only rules remain outside automatic PASS/BLOCK unless a later semantic reviewer records evidence.

Entity extraction is intentionally conservative and labeled low confidence. It does not claim NER-grade truth.

## Russian NLP evaluation

The Natasha ecosystem was evaluated for this phase. Natasha/SlovNet provides Russian NER, morphology and syntax under MIT licensing and is production-oriented, but its published compact NER model is optimized for news and requires model assets. That is useful for an optional heavier language-analysis tier, not for the fast deterministic gate here.

Razdel remains the connected dependency because it is MIT-licensed, rule-based, compact and explicitly evaluated on Russian corpora including fiction. It already provides the token/sentence segmentation needed by these reports without model downloads.

## Regression locks

`rules/regressions.yaml` is now schema-backed and each rule records:

- stable ID and owner family;
- BLOCK/REVIEW severity;
- description;
- positive/negative examples;
- deterministic/heuristic/semantic detection type;
- fixture/test path where machine detection exists;
- affected lifecycle stages;
- introduction provenance;
- supersession link.

Run:

```bash
python scripts/regression_check.py
```

Deterministic or heuristic rules without an existing fixture/test file fail the register check. This does not pretend that a test file fully proves a semantic rule; it ensures every claimed machine-detectable lock has executable coverage somewhere in the suite.
