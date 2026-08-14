# Structured state and provenance contract

Production Engine v2 keeps canon state split by responsibility instead of treating one YAML file as a universal database.

## Authorities

- `canon/runtime.yaml` — chapter pointer and runtime/system summary.
- `canon/system.yaml` — System rules and happened System history.
- `canon/state.yaml` — typed registries for characters, relationships, locations, assets/money, active threads, future locks and proposals.
- `canon/facts.yaml` — stable fact IDs, classification, provenance and supersession.
- `canon/knowledge.yaml` — which character knows/believes/suspects which fact and how that knowledge was acquired.
- `research/ledger.yaml` — source provenance, historical lock, geography/scope and freshness metadata for real-world claims.
- `rules/author_instructions.yaml` — explicit author decisions as machine-readable instructions rather than chat-only memory.

The new registries intentionally start empty. A public infrastructure repository must not invent canon or expose unpublished prose merely to populate a schema.

## Stable ID families

- facts: `SB-F-*`
- characters: `SB-CHAR-*`
- relationships: `SB-REL-*`
- locations: `SB-LOC-*`
- assets/money: `SB-ASSET-*`
- active threads: `SB-THREAD-*`
- future locks: `SB-LOCK-*`
- proposals: `SB-PROP-*`
- knowledge entries: `SB-KNW-*`
- research records: `SB-RES-*`
- author instructions: `SB-AUTH-*`

IDs are identity, not presentation text. Renaming a display name or summary must not silently mint a new entity.

## Fact classes

A fact ledger entry must explicitly identify one of:

- `OBJECTIVE_FACT`
- `BELIEF`
- `RUMOR`
- `PLAN`
- `PROPOSAL`

`PLAN` and `PROPOSAL` cannot declare a `happened_chapter`. An `OBJECTIVE_FACT` must have at least one direct authoritative provenance source (`HAPPENED_CHAPTER`, `RUNTIME`, `SYSTEM`, `AUTHOR_INSTRUCTION`, or `RESEARCH`). A chain containing only `FACT` references is not sufficient to promote a plan, proposal, rumor or belief into objective canon.

Supersession is bidirectional: if new fact B supersedes A, B must list A and A must point back to B. This prevents stale facts from remaining apparently active through a one-sided edit.

## Character knowledge

Knowledge is a separate relation; a fact existing in canon does not imply that every character knows it.

Supported acquisition methods are:

- `WITNESSED`
- `TOLD_BY`
- `PUBLIC_KNOWLEDGE`
- `DOCUMENT_MESSAGE`
- `LEGITIMATE_INFERENCE`
- `PRE_STORY_KNOWLEDGE`

Every knowledge entry references a real character and fact. `TOLD_BY` requires a source character and cannot use the recipient as that source. This blocks convenient off-page knowledge from being silently invented just to make a dialogue line work.

## Research freshness

Research records bind a claim fact to a source URL/stable source ID, access date, historical date lock, geography, product/provider scope, confidence, freshness class and dependent facts/chapters.

`VOLATILE` and `EVENT_DRIVEN` records require a `recheck_after` date or an event trigger. Once `recheck_after` is in the past, `scripts/provenance_check.py` reports `RESEARCH_STALE` instead of preserving an old PASS indefinitely.

## Deterministic validation

Run:

```bash
python scripts/provenance_check.py
```

The checker first validates each authority against JSON Schema, then enforces cross-file invariants. CI exposes this as the dedicated `structured state and provenance` job.

Schema validation and cross-reference validation are both required: JSON Schema catches malformed records, while the cross-checker catches valid-looking records that refer to nonexistent facts/characters/sources or violate promotion/provenance rules.

## Third-party design decision

Pydantic, W3C PROV (`prov`) and `transitions` were evaluated before this slice. They are not runtime dependencies here:

- JSON Schema already provides the serialized contract shared by YAML authorities and CI, so adding Pydantic now would duplicate the validation source of truth.
- W3C PROV is a capable general-purpose provenance model, but the Production Engine needs domain-specific rules such as `PLAN -> OBJECTIVE_FACT` blocking and character knowledge acquisition semantics.
- `transitions` remains a reasonable candidate if lifecycle behavior becomes branching/hierarchical; the current mandatory linear chapter lifecycle is simpler and safer as explicit code.

Re-evaluate these choices if the state model grows beyond what the current deterministic layer can express cleanly.
