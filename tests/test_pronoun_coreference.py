from __future__ import annotations

from pathlib import Path

import yaml
from pronoun_coreference import analyze_text, load_rules, validate_fixture_corpus

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules/pronoun_regressions.yaml"
FIXTURES = ROOT / "tests/fixtures/pronoun_coreference_cases.yaml"


def test_pronoun_fixture_corpus_is_clean() -> None:
    assert validate_fixture_corpus(RULES, FIXTURES) == []


def test_ambiguous_personal_pronoun_keeps_candidate_evidence() -> None:
    payload = analyze_text(
        "Герман подошёл к Максиму. Он достал телефон.",
        load_rules(RULES),
    )
    assert payload["status"] == "REVIEW"
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-PRN-001")
    assert finding["evidence"]["pronoun"] == "Он"
    assert {item["lemma"] for item in finding["evidence"]["candidates"]} >= {
        "герман",
        "максим",
    }
    assert finding["automatic_rewrite_allowed"] is False


def test_common_noun_can_resolve_pronoun_without_false_gender_alarm() -> None:
    payload = analyze_text("Анна взяла телефон. Он зазвонил.", load_rules(RULES))
    assert payload["status"] == "PASS"
    assert payload["coverage"]["unique_candidate"] == 1


def test_possessive_owner_ambiguity_is_review_only() -> None:
    payload = analyze_text(
        "Анна посмотрела на Милену и поправила её платье.",
        load_rules(RULES),
    )
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-PRN-003")
    assert finding["severity"] == "REVIEW"
    assert len(finding["evidence"]["owner_candidates"]) == 2
    assert payload["counts"]["BLOCK"] == 0


def test_character_profile_gender_overrides_ambiguous_name_form() -> None:
    profiles = [
        {
            "id": "SB-CHAR-ALEX",
            "display_name": "Александр",
            "aliases": ["Саша"],
            "grammatical_gender": "MASC",
        }
    ]
    payload = analyze_text("Саша вошёл. Она улыбнулась.", load_rules(RULES), profiles)
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-PRN-002")
    assert finding["evidence"]["recent_candidates"][0]["character_id"] == "SB-CHAR-ALEX"
    assert finding["evidence"]["recent_candidates"][0]["gender"] == "masc"


def test_fixture_file_contains_no_story_state_dependency() -> None:
    document = yaml.safe_load(FIXTURES.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert all("chapter" not in case for case in document["cases"])
