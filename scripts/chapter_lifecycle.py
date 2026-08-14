#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

STAGES = (
    "NOT_STARTED",
    "PREWRITE",
    "DRAFT_READY_FOR_EDITOR",
    "QA_IN_PROGRESS",
    "FINAL_CANDIDATE",
    "FINAL_TEXT_FROZEN",
    "AUTHOR_APPROVED",
    "HAPPENED",
)

NEXT_STAGE = {current: target for current, target in zip(STAGES, STAGES[1:])}
SHA256_LENGTH = 64


def transition_allowed(current: str, target: str) -> bool:
    """Return true only for an idempotent check or the single next lifecycle gate."""
    return target == current or NEXT_STAGE.get(current) == target


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != SHA256_LENGTH:
        return False
    return all(char in "0123456789abcdef" for char in value)


def validate_manifest_lifecycle(manifest: dict) -> list[str]:
    """Validate lifecycle evidence that is stricter than shape-only JSON Schema checks."""
    errors: list[str] = []
    stage = manifest.get("stage")
    freeze = manifest.get("freeze", {})

    if stage not in STAGES:
        return [f"unknown lifecycle stage: {stage!r}"]

    chapter_sha = freeze.get("chapter_sha256")
    final_text_frozen = freeze.get("final_text_frozen")
    author_approved = freeze.get("author_approved")
    approval_evidence = freeze.get("author_approval_evidence_id")

    prefreeze_stages = {
        "NOT_STARTED",
        "PREWRITE",
        "DRAFT_READY_FOR_EDITOR",
        "QA_IN_PROGRESS",
        "FINAL_CANDIDATE",
    }

    if stage in prefreeze_stages:
        if chapter_sha is not None:
            errors.append(f"{stage} cannot carry a frozen chapter hash")
        if final_text_frozen is not False:
            errors.append(f"{stage} requires final_text_frozen=false")
        if author_approved is not False:
            errors.append(f"{stage} requires author_approved=false")
        if approval_evidence is not None:
            errors.append(f"{stage} cannot carry author approval evidence")

    if stage == "FINAL_TEXT_FROZEN":
        if not _is_sha256(chapter_sha):
            errors.append("FINAL_TEXT_FROZEN requires a lowercase SHA-256 chapter hash")
        if final_text_frozen is not True:
            errors.append("FINAL_TEXT_FROZEN requires final_text_frozen=true")
        if author_approved is not False:
            errors.append("FINAL_TEXT_FROZEN cannot synthesize author approval")
        if approval_evidence is not None:
            errors.append("FINAL_TEXT_FROZEN cannot carry author approval evidence")

    if stage in {"AUTHOR_APPROVED", "HAPPENED"}:
        if not _is_sha256(chapter_sha):
            errors.append(f"{stage} requires a lowercase SHA-256 chapter hash")
        if final_text_frozen is not True:
            errors.append(f"{stage} requires final_text_frozen=true")
        if author_approved is not True:
            errors.append(f"{stage} requires author_approved=true")
        if not isinstance(approval_evidence, str) or not approval_evidence.strip():
            errors.append(f"{stage} requires explicit author_approval_evidence_id")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate chapter lifecycle state and freeze/approval evidence.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--transition-from", choices=STAGES)
    args = parser.parse_args()

    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    errors = validate_manifest_lifecycle(manifest)

    if args.transition_from and not transition_allowed(args.transition_from, manifest.get("stage")):
        errors.append(
            f"illegal transition {args.transition_from} -> {manifest.get('stage')}; "
            "mandatory lifecycle gates cannot be skipped"
        )

    if errors:
        print("CHAPTER_LIFECYCLE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"CHAPTER_LIFECYCLE: PASS stage={manifest['stage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
