# Repository instructions — Sistema Bogatstva Production Engine

These instructions apply to every agent/chat/code assistant working in this repository.

## 1. Project identity and isolation

This repository belongs only to the Russian-language novel project **«Система богатства»**.

Do not import story canon, runtime state, character facts, storage conventions, chapter numbering, or plot assumptions from other projects, including **«Система политики»** or **«Я пробудил систему геймдизайнера!»**. Foreign projects may be consulted only as clearly marked methodological references when the author explicitly wants that.

## 2. Repository role

GitHub is the **machine/execution authority** for reproducible production infrastructure:

- structured runtime/canon state;
- schemas and invariants;
- chapter QA manifests;
- regression registries;
- exact hashes and freeze evidence;
- CI workflows and logs;
- reproducible reports/artifacts;
- dependency/provenance metadata.

Google Drive remains the **human-facing editorial library** for convenient Docs, visual references, research materials, and presentation/final files unless the author explicitly changes this split.

Never create two equal current-state authorities. Machine-critical state that is represented in GitHub must have one canonical structured location and all mirrors must be marked as mirrors/snapshots.

## 3. Current repository entry points

Always inspect the live repository instead of trusting a pasted historical summary. At minimum read:

1. `README.md`
2. `AGENTS.md`
3. `canon/runtime.yaml`
4. `canon/system.yaml`
5. `canon/active_arc.yaml`
6. `rules/regressions.yaml`
7. `current/`
8. `docs/TOOLING_AND_INTEGRATIONS.md`
9. `.github/workflows/`
10. `scripts/`, `schemas/`, `tests/`, and `config/`

Then inspect the latest relevant GitHub Actions run before claiming that CI or a check passes.

## 4. Public-repository safety gate

As long as the repository is public, do **not** commit:

- full unpublished chapter prose;
- private explicit/adult scene drafts;
- sensitive visual references;
- private Drive exports;
- secrets, API keys, credentials, private URLs or personal data.

Structured production metadata already intentionally present in the repository may remain, but do not increase exposure casually. If the repository becomes private, re-evaluate this gate rather than assuming it disappeared automatically.

## 5. Source authority

For machine state, prefer explicit structured files over prose summaries. Never promote a proposal, rumor, character belief, future plan, or historical snapshot into objective canon merely because it exists in a file.

A recommended authority order for infrastructure work is:

1. current explicit author instruction;
2. current structured runtime and system state;
3. exact approved/frozen chapter evidence when present;
4. stable canon/character data;
5. active arc/router;
6. production rules and regression locks;
7. research manifests/evidence;
8. historical logs/snapshots.

If two sources conflict, stop promotion and surface the conflict; do not silently choose the more convenient value.

## 6. Deterministic vs semantic QA

Keep two distinct layers:

### Deterministic gates
Use code for things that can be proven mechanically, such as:

- schema validation;
- chapter-number consistency;
- single-current-state invariants;
- current chapter = approved chapter + 1;
- stale or mismatched hashes;
- duplicated current markers;
- foreign-project contamination;
- required manifest fields;
- missing provenance/source IDs;
- research freshness deadlines;
- dependency invalidation;
- forbidden promotion transitions;
- exact PDF/text provenance when implemented.

### Semantic REVIEW layer
Do not pretend code can definitively decide literary quality. Dialogue naturalness, POV quality, characterization, exposition convenience, erotic fidelity, scene causality, and prose rhythm remain semantic review tasks. Automated heuristics may produce `REVIEW` findings and useful artifacts, but must not silently rewrite fiction or declare literary PASS by themselves.

## 7. Freeze and invalidation model

`FINAL_TEXT_FROZEN` must be evidence-based, not a label.

A freeze should bind, at minimum, to the exact SHA-256 of:

- chapter text/revision;
- runtime parent/input state;
- applicable rules/regression manifest;
- research/source manifest when relevant;
- QA result manifest.

Any dependent change invalidates downstream PASS/freeze evidence. A changed text hash means the old textual QA no longer proves the new revision passed.

## 8. Chapter lifecycle

Model chapter production as an explicit state machine. Recommended states:

`NOT_STARTED -> PREWRITE -> DRAFT_READY_FOR_EDITOR -> QA_IN_PROGRESS -> FINAL_CANDIDATE -> FINAL_TEXT_FROZEN -> AUTHOR_APPROVED -> HAPPENED`

Do not skip gates. `AUTHOR_APPROVED` is an author decision and must never be synthesized from CI success. Promotion to `HAPPENED` should update runtime/character/system/arc state transactionally or fail.

## 9. Research-first rule

Exact real-world claims that may change or depend on date/provider/location/model must have provenance before they are treated as reliable production inputs. Examples: prices, laws, bank settlement behavior, crypto rules, product availability, routes, historical prices, vehicle specs, businesses, import/registration rules.

A useful research record should contain:

- claim/subject;
- source URL or stable source identifier;
- source title/domain;
- accessed/verified date;
- historical date lock if applicable;
- geographic/provider/model scope;
- confidence/status;
- freshness class / recheck trigger;
- chapter(s) or facts depending on it.

Do not backcast a current value as an exact historical value.

## 10. Third-party tooling policy

Use mature existing tools when they improve reproducibility, but do not install packages just because their names sound relevant.

Before adding a third-party dependency or framework, verify:

- exact repository/package identity;
- current maintenance state;
- license;
- security/reputation;
- Russian-language support where relevant;
- deterministic vs LLM behavior;
- overlap with existing architecture;
- whether it creates a competing canon/workflow authority.

Prefer narrow libraries/actions over importing an entire autonomous novel-generation framework. Adapt useful architecture from larger projects when direct integration would create conflicts.

Currently integrated/evaluated tooling is documented in `docs/TOOLING_AND_INTEGRATIONS.md`. The exact-name `novel_qa_toolkit` was not found as a verified public dependency during the initial pass; never invent it. If the author provides a specific URL/package, evaluate that exact target.

## 11. CI discipline

For non-trivial infrastructure changes:

1. inspect current `main` and latest CI;
2. create a focused branch;
3. implement with tests;
4. run/trigger CI;
5. inspect failed job logs rather than guessing;
6. fix until required checks are green;
7. summarize evidence accurately;
8. merge only when the requested scope is complete and no blocking failure remains.

Never claim a script/check/workflow was executed if it was only written.

## 12. Desired v2+ direction

When extending the system, prefer these capabilities:

- stronger JSON Schema / typed state models;
- per-fact provenance and knowledge ownership;
- character knowledge graph and source-of-knowledge checks;
- research freshness engine;
- dependency graph and automatic impact invalidation;
- structured author-instruction register;
- chapter QA artifact generation (`dialogue-only`, `narration-only`, question audit, repetition/signals, continuity diff);
- regression-rule ownership and test fixtures;
- chapter lifecycle/promotion command with transactional updates;
- reproducible freeze manifest;
- PDF provenance and preflight once full text can safely live in the repo;
- Drive↔GitHub sync **manifest** with conflict detection, not blind bidirectional overwrite;
- machine-readable CI summary/artifacts for future chats.

## 13. Modification principles

- Preserve author intent over generic writing norms.
- Do not silently rewrite approved prose.
- Do not turn REVIEW heuristics into automatic replacements.
- Do not make the world a reward system for the protagonist.
- Do not let infrastructure rules import story content from another book.
- Prefer explicit failure over hidden fallback when canon/state is ambiguous.
- Keep volatile current state out of stable README-style documentation whenever possible; route readers to structured current-state files.
- Every important automation should have a test or a reproducible evidence path.

## 14. New-chat behavior

If a user opens a new chat to continue work on this repository, the agent should first inspect this repository and its latest CI instead of asking the user to restate all existing infrastructure. The user may paste `docs/NEW_CHAT_BOOTSTRAP_PROMPT.md` as the task brief.
