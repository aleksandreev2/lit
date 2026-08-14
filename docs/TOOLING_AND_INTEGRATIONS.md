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
Checks YAML quality/parse hygiene in CI. Line-length violations are blocking rather than advisory so a green deterministic job does not hide known YAML defects.

### Ruff 0.16.0
Fast deterministic Python linter from Astral, MIT licensed. The repository already carried Ruff configuration but did not install or execute Ruff in CI; v2 hardening activates it with an explicit conservative rule selection (`E4`, `E7`, `E9`, `F`, `I`) so upstream default-rule changes do not silently redefine the gate.

Source: `https://github.com/astral-sh/ruff`

### pip-audit 2.10.1
PyPA dependency vulnerability auditor, Apache-2.0 licensed. CI audits the Python project dependency graph against known vulnerability data. This is a dependency vulnerability gate, not a malicious-package detector or source-code security scanner.

Source: `https://github.com/pypa/pip-audit`

### Razdel
Rule-based Russian tokenization/sentence segmentation. Used by deterministic dialogue/prose signal scanners so short-turn heuristics count Russian words more reliably than whitespace splitting.

### Vale
Official markup-aware prose linter. We use it primarily as a configurable deterministic rule engine for project-specific anti-regressions (for example foreign-book contamination). It is **not** treated as a Russian literary editor and cannot replace dialogue/POV review. CI pins the Vale binary version rather than using `latest`.

### LanguageTool — optional adapter
LanguageTool supports Russian proofreading and can be run locally. It is intentionally optional because a full local installation is comparatively heavy and remote public API use is not appropriate for automated CI or unpublished text. When enabled, run it locally/self-hosted and treat findings as REVIEW signals rather than automatic rewrites.

## Evaluated, not imported as runtime dependencies

### zizmor 1.29.0
Actively maintained MIT-licensed static analysis for GitHub Actions and related CI configuration. It is a strong candidate for the next security-hardening slice because it can detect unpinned actions, risky permissions and credential persistence. It is deliberately not mixed into the first lifecycle/schema hardening change so any new CI-security findings can be reviewed and fixed as their own focused gate.

Source: `https://github.com/zizmorcore/zizmor`

### NetworkX 3.6.1
Mature BSD-3-Clause graph library. It was evaluated for the future dependency/invalidation DAG, but is not added yet: the current graph requirements are small enough to model with standard-library data structures, so adding a broad graph package now would increase dependency surface without providing a needed capability. Re-evaluate if graph queries, cycle analysis or larger provenance traversal become non-trivial.

Source: `https://github.com/networkx/networkx`

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
