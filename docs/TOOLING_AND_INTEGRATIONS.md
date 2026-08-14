# Tooling and integrations

This project deliberately separates **deterministic machine checks** from **semantic editorial judgment**.

## Connected now

### jsonschema
Used for structured runtime/canon validation. Machine state must satisfy explicit schemas before downstream QA can pass.

### PyYAML
Used for human-readable machine state (`canon/*.yaml`).

### pytest
Runs invariant tests in CI.

### yamllint
Checks YAML quality/parse hygiene in CI.

### Razdel
Rule-based Russian tokenization/sentence segmentation. Used by deterministic dialogue/prose signal scanners so short-turn heuristics count Russian words more reliably than whitespace splitting.

### Vale
Official markup-aware prose linter. We use it primarily as a configurable deterministic rule engine for project-specific anti-regressions (for example foreign-book contamination). It is **not** treated as a Russian literary editor and cannot replace dialogue/POV review.

### LanguageTool — optional adapter
LanguageTool supports Russian proofreading and can be run locally. It is intentionally optional because a full local installation is comparatively heavy and remote public API use is not appropriate for automated CI or unpublished text. When enabled, run it locally/self-hosted and treat findings as REVIEW signals rather than automatic rewrites.

## Evaluated, not imported as runtime dependencies

### NousResearch/autonovel
Useful ideas: mechanical + LLM “two immune systems”, state propagation debt, chapter comparison/revision loops. Not imported directly because it is an autonomous generation pipeline and would conflict with the author-approval/freeze workflow. We adapt the architectural ideas instead.

### mrigankad/Novel-OS
Useful ideas: persistent memory, deterministic continuity checks, staged editorial agents. Not imported directly because this project already has a stronger book-specific canon/QA authority model. Concepts can be selectively ported.

### forsonny/book-os
Useful ideas: layered context and persistent writing standards. Treated as architecture reference, not source of story truth.

### Spec Kit fiction-writing preset
Useful ideas: spec/plan/tasks/checklist/continuity separation and quality gates. We already use analogous PREWRITE/scene-contract/QA gates, so direct installation would mostly duplicate authority. Selective templates may be adapted later.

## `novel_qa_toolkit`
No public GitHub repository or PyPI project with the exact name `novel_qa_toolkit` was found during the initial integration pass on 2026-08-14. Do not add an imaginary dependency. If the author meant a specific repository/package, add its exact URL here and evaluate license, maintenance, language support and overlap before integration.

## Integration rule

A third-party tool is admitted only when it provides one of these without becoming a competing canon authority:

1. deterministic validation;
2. reproducible proofreading/linting;
3. structured schema/state support;
4. report/artifact generation;
5. clearly isolated semantic challenger output.

No external toolkit may silently rewrite approved prose, promote proposals to canon, or bypass author approval.
