# Dependency invalidation and cryptographic freeze

Production Engine v2 treats every PASS as evidence bound to exact inputs, not as a permanent badge.

## Dependency DAG

`config/dependency_graph.yaml` declares the direction of authority and invalidation:

`rules/runtime/research/character_state/chapter_text -> QA -> qa_manifest -> freeze -> release artifacts -> PDF/release`

The graph is validated for duplicate nodes, unknown dependencies, self-dependencies and cycles. `scripts/dependency_graph.py` can also calculate transitive stale nodes from one or more changed inputs.

Example:

```bash
python scripts/dependency_graph.py config/dependency_graph.yaml --changed runtime
```

A runtime change invalidates continuity QA, the QA manifest, freeze and downstream release artifacts; it does not invalidate dialogue-only QA unless chapter text also changed.

## Pre-freeze vs post-freeze artifacts

There are intentionally two artifact concepts:

- `generated_artifact_manifest` is pre-freeze evidence produced from the chapter candidate and is itself bound into the freeze;
- `release_artifact_manifest` is downstream of the freeze and represents release/PDF outputs.

Using one node for both would create a logical cycle (freeze depends on artifact manifest while artifact manifest depends on freeze), so the graph forbids that architecture.

## Freeze manifest

A valid freeze binds SHA-256 hashes for exactly these roles:

- `CHAPTER_TEXT`
- `PARENT_RUNTIME`
- `CHARACTER_STATE`
- `REGRESSION_RULES`
- `RESEARCH_MANIFEST`
- `QA_MANIFEST`
- `GENERATED_ARTIFACT_MANIFEST`

Role-to-graph-node mappings are fixed in code. A manifest cannot claim that a runtime file is `chapter_text` merely by changing a label.

All QA gates recorded in a freeze must be `PASS`. `REVIEW`, `BLOCK` or `STALE` makes the freeze invalid.

## Building and verifying

The builder accepts a JSON spec containing chapter number, graph path, the seven input roles/paths and QA gate results:

```bash
python scripts/freeze_manifest.py build freeze-spec.json freeze.json
python scripts/freeze_manifest.py verify freeze.json
```

The compatibility entrypoint remains:

```bash
python scripts/freeze_check.py freeze.json
```

Verification re-hashes every bound file. A mismatch marks its graph node changed and propagates stale status to all dependents. The command fails rather than silently preserving an obsolete freeze.

## No Ch25 freeze yet

Chapter 25 has no chapter text candidate and therefore no real freeze manifest is created. Tests use synthetic temporary files to prove build/verify/invalidation behavior without adding or fabricating chapter prose.

## Why no graph dependency

NetworkX was evaluated earlier and remains useful if graph analysis becomes substantially more complex. The current DAG needs only cycle detection and reverse reachability, both implemented in a small auditable standard-library module. Adding NetworkX at this stage would increase dependency and vulnerability surface without improving the required behavior.
