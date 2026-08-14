# Tooling and integrations

This project deliberately separates **deterministic machine checks** from **semantic editorial judgment**.

## Connected now

### jsonschema
Used for structured runtime/canon validation. Machine state must satisfy explicit schemas before downstream QA can pass.

### PyYAML
Used for human-readable machine state (`canon/*.yaml`).

### pytest
Runs invariant, provenance, freeze, QA-artifact, promotion, sync and release-provenance tests in CI.

### yamllint
Checks YAML quality/parse hygiene in CI. Line-length violations are blocking rather than advisory so a green deterministic job does not hide known YAML defects.

### Ruff 0.16.0
Fast deterministic Python linter from Astral, MIT licensed. CI uses an explicit conservative rule selection (`E4`, `E7`, `E9`, `F`, `I`) so upstream default-rule changes do not silently redefine the gate.

Source: `https://github.com/astral-sh/ruff`

### pip-audit 2.10.1
PyPA dependency vulnerability auditor, Apache-2.0 licensed. CI audits the Python project dependency graph against known vulnerability data. This is a dependency vulnerability gate, not a malicious-package detector or source-code security scanner.

Source: `https://github.com/pypa/pip-audit`

### zizmor 1.29.0 via zizmor-action 0.6.2
GitHub Actions security scanner, MIT licensed. The workflow uses the official action pinned to commit `3dc1ecc9bcb9e94e9b2c709687979e1298497054` and pins the scanner version to `1.29.0`. The job runs offline against workflow files with Advanced Security disabled, so it needs no write permission or SARIF upload. Checkout credentials are not persisted.

Source: `https://github.com/zizmorcore/zizmor-action`

### actions/upload-artifact 7.0.1
Official GitHub artifact action used to retain the compact `qa-report` bundle from CI. The workflow pins the action to commit `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` rather than a moving tag.

Source: `https://github.com/actions/upload-artifact`

### Razdel
Rule-based Russian tokenization/sentence segmentation. Used by deterministic dialogue/prose signal scanners so short-turn heuristics count Russian words more reliably than whitespace splitting.

### Vale 3.17.1
Official markup-aware prose linter. We use it primarily as a configurable deterministic rule engine for project-specific anti-regressions. It is **not** treated as a Russian literary editor and cannot replace dialogue/POV review. CI pins the Vale binary version rather than using `latest`.

### Google Drive connector — read/observe only for sync baselines
The connected Drive account is used to discover stable file IDs/revision IDs for explicit mappings. Production Engine records those observations in `sync/manifest.yaml` but performs no automatic Drive writes. Both current mappings are `MANUAL_ONLY` until authority/direction is deliberately changed and conflict checks are satisfied.

### LanguageTool — optional adapter
LanguageTool supports Russian proofreading and can be run locally. It is intentionally optional because a full local installation is comparatively heavy and remote public API use is not appropriate for automated CI or unpublished text. When enabled, run it locally/self-hosted and treat findings as REVIEW signals rather than automatic rewrites.

## Evaluated, not imported as runtime dependencies

### Pydantic 2.13.4
Mature MIT-licensed Python validation library using type hints. It is a good fit for application-layer typed models, but the Production Engine currently needs a serialized YAML/JSON contract shared by scripts and CI. JSON Schema is already that authority, so introducing Pydantic would duplicate validation definitions without adding a required capability.

Source: `https://github.com/pydantic/pydantic`

### prov 2.1.1
MIT-licensed implementation of the W3C PROV data model with PROV-JSON/XML/RDF support. It is useful for general data lineage, but the novel engine needs domain rules such as fact classification, character knowledge acquisition and explicit plan/proposal promotion blocking. We keep the ledger domain-specific rather than wrapping it in a larger generic provenance model.

Source: `https://github.com/trungdong/prov`

### transitions
MIT-licensed finite-state-machine library with hierarchical, async and graph extensions. It remains a candidate if chapter lifecycle behavior becomes branching or hierarchical. The present mandatory lifecycle is linear enough that explicit transition code is easier to audit and harder to configure incorrectly.

Source: `https://github.com/pytransitions/transitions`

### NetworkX 3.6.1
Mature BSD-3-Clause graph library. It was evaluated for the dependency/invalidation DAG but is not added: the current graph only needs cycle detection and reverse reachability, both implemented in a small auditable standard-library module. Re-evaluate if graph queries or provenance traversal become materially more complex.

Source: `https://github.com/networkx/networkx`

### Natasha / SlovNet
MIT-licensed Russian NLP ecosystem with NER, morphology and syntax. Useful as an optional heavier semantic-support tier, but its model assets and news-oriented compact NER are unnecessary for the fast deterministic candidate-report layer. Razdel supplies the segmentation needed there without model downloads.

Source: `https://github.com/natasha/natasha`

### NousResearch/autonovel
Useful ideas: mechanical + LLM “two immune systems”, state propagation debt, chapter comparison/revision loops. Not imported directly because it is an autonomous generation pipeline and would conflict with the author-approval/freeze workflow. We adapt architectural ideas instead.

### mrigankad/Novel-OS
Useful ideas: persistent memory, deterministic continuity checks, staged editorial agents. Not imported directly because this project already has a stronger book-specific canon/QA authority model. Concepts can be selectively ported.

### forsonny/book-os
Useful ideas: layered context and persistent writing standards. Treated as architecture reference, not source of story truth.

### Spec Kit fiction-writing preset
Useful ideas: spec/plan/tasks/checklist/continuity separation and quality gates. We already use analogous PREWRITE/scene-contract/QA gates, so direct installation would mostly duplicate authority. Selective templates may be adapted later.

## `novel_qa_toolkit`
No public GitHub repository or PyPI project with the exact name `novel_qa_toolkit` was found during the initial integration pass on 2026-08-14. Do not add an imaginary dependency. If a specific repository/package is meant, add its exact URL and evaluate license, maintenance, language support and overlap before integration.

## Integration rule

A third-party tool is admitted only when it provides one of these without becoming a competing canon authority:

1. deterministic validation;
2. reproducible proofreading/linting;
3. structured schema/state support;
4. report/artifact generation;
5. clearly isolated semantic challenger output.

No external toolkit may silently rewrite approved prose, promote proposals to canon, or bypass author approval.
