from __future__ import annotations

from copy import deepcopy

from scripts.chapter_lifecycle import STAGES, transition_allowed, validate_manifest_lifecycle


def base_manifest() -> dict:
    return {
        "stage": "NOT_STARTED",
        "freeze": {
            "chapter_sha256": None,
            "final_text_frozen": False,
            "author_approved": False,
            "author_approval_evidence_id": None,
        },
    }


def test_lifecycle_allows_only_same_or_next_gate() -> None:
    for index, stage in enumerate(STAGES):
        assert transition_allowed(stage, stage)
        if index + 1 < len(STAGES):
            assert transition_allowed(stage, STAGES[index + 1])
        if index + 2 < len(STAGES):
            assert not transition_allowed(stage, STAGES[index + 2])


def test_prefreeze_stage_rejects_freeze_evidence() -> None:
    manifest = base_manifest()
    manifest["stage"] = "FINAL_CANDIDATE"
    manifest["freeze"]["chapter_sha256"] = "a" * 64
    assert validate_manifest_lifecycle(manifest) == [
        "FINAL_CANDIDATE cannot carry a frozen chapter hash"
    ]


def test_final_text_frozen_requires_hash_but_not_author_approval() -> None:
    manifest = base_manifest()
    manifest["stage"] = "FINAL_TEXT_FROZEN"
    errors = validate_manifest_lifecycle(manifest)
    assert "FINAL_TEXT_FROZEN requires a lowercase SHA-256 chapter hash" in errors
    assert "FINAL_TEXT_FROZEN requires final_text_frozen=true" in errors

    manifest["freeze"].update(
        chapter_sha256="a" * 64,
        final_text_frozen=True,
    )
    assert validate_manifest_lifecycle(manifest) == []


def test_author_approved_requires_explicit_evidence() -> None:
    manifest = base_manifest()
    manifest["stage"] = "AUTHOR_APPROVED"
    manifest["freeze"].update(
        chapter_sha256="b" * 64,
        final_text_frozen=True,
        author_approved=True,
    )
    assert validate_manifest_lifecycle(manifest) == [
        "AUTHOR_APPROVED requires explicit author_approval_evidence_id"
    ]

    approved = deepcopy(manifest)
    approved["freeze"]["author_approval_evidence_id"] = "AUTHOR-APPROVAL-025-001"
    assert validate_manifest_lifecycle(approved) == []


def test_happened_cannot_exist_without_frozen_author_approved_state() -> None:
    manifest = base_manifest()
    manifest["stage"] = "HAPPENED"
    errors = validate_manifest_lifecycle(manifest)
    assert len(errors) == 4
    assert any("chapter hash" in error for error in errors)
    assert any("author_approved=true" in error for error in errors)
    assert any("author_approval_evidence_id" in error for error in errors)
