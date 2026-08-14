from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _validator() -> Draft202012Validator:
    schema = json.loads(
        (ROOT / "schemas/structured_state.schema.json").read_text(encoding="utf-8")
    )
    return Draft202012Validator(schema)


def _state(character: dict) -> dict:
    return {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "as_of_chapter": 24,
        "characters": [character],
        "relationships": [],
        "locations": [],
        "assets_money": [],
        "active_threads": [],
        "future_locks": [],
        "proposals": [],
    }


def test_character_aliases_and_grammatical_gender_are_optional_valid_metadata() -> None:
    character = {
        "id": "SB-CHAR-ALEX",
        "display_name": "Александр",
        "aliases": ["Саша", "Алекс"],
        "grammatical_gender": "MASC",
        "status": "ACTIVE",
        "state_revision": 1,
        "fact_ids": [],
    }
    assert list(_validator().iter_errors(_state(character))) == []


def test_invalid_grammatical_gender_is_rejected() -> None:
    character = {
        "id": "SB-CHAR-ALEX",
        "display_name": "Александр",
        "grammatical_gender": "MALE",
        "status": "ACTIVE",
        "state_revision": 1,
        "fact_ids": [],
    }
    errors = list(_validator().iter_errors(_state(character)))
    assert errors
    assert any("grammatical_gender" in ".".join(map(str, error.path)) for error in errors)


def test_existing_character_shape_without_pronoun_metadata_remains_valid() -> None:
    character = {
        "id": "SB-CHAR-ALEX",
        "display_name": "Александр",
        "status": "ACTIVE",
        "state_revision": 1,
        "fact_ids": [],
    }
    assert list(_validator().iter_errors(_state(character))) == []
