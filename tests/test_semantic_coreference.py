from __future__ import annotations

from pathlib import Path

import yaml
from semantic_coreference import analyze_text, load_rules, validate_fixture_corpus

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules/semantic_coreference_regressions.yaml"
FIXTURES = ROOT / "tests/fixtures/semantic_coreference_cases.yaml"


def test_semantic_coreference_fixture_corpus_is_clean() -> None:
    assert validate_fixture_corpus(RULES, FIXTURES) == []


def test_long_distance_reference_keeps_far_candidate_evidence() -> None:
    payload = analyze_text(
        "Анна вошла.\nЗа окном гремел дождь.\nВ коридоре было темно.\nОна сняла пальто.",
        load_rules(RULES),
    )
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-CTX-001")
    assert finding["evidence"]["nearest_sentence_distance"] >= 2
    assert any(item["lemma"] == "анна" for item in finding["evidence"]["candidates"])
    assert finding["automatic_rewrite_allowed"] is False


def test_three_person_dialogue_run_is_speaker_review_not_rewrite() -> None:
    payload = analyze_text(
        "Анна, Милена и Лера остановились у двери.\n"
        "— Ты уверена?\n"
        "— Да.\n"
        "— Тогда идём.",
        load_rules(RULES),
    )
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-CTX-002")
    assert len(finding["evidence"]["participants"]) >= 3
    assert finding["severity"] == "REVIEW"
    assert payload["counts"]["BLOCK"] == 0


def test_zero_subject_with_two_feminine_candidates_is_review() -> None:
    payload = analyze_text(
        "Анна встретила Милену.\nУлыбнулась и отвернулась.",
        load_rules(RULES),
    )
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-CTX-003")
    assert finding["evidence"]["verb_gender"] == "femn"
    assert len(finding["evidence"]["candidate_subjects"]) >= 2


def test_stanza_evidence_never_turns_semantic_layer_into_pass_authority() -> None:
    stanza = {
        "status": "REVIEW",
        "coreference_chains": [
            {
                "index": 0,
                "representative_text": "Милена",
                "mentions": [
                    {
                        "sentence": 0,
                        "start_word": 2,
                        "end_word": 3,
                        "text": "Милену",
                        "is_zero": False,
                    },
                    {
                        "sentence": 1,
                        "start_word": 0,
                        "end_word": 1,
                        "text": "Она",
                        "is_zero": False,
                    },
                ],
            }
        ],
    }
    payload = analyze_text(
        "Анна встретила Милену.\nОна ушла.",
        load_rules(RULES),
        stanza_payload=stanza,
    )
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-CTX-004")
    assert finding["evidence"]["representative_text"] == "Милена"
    assert payload["status"] == "REVIEW"
    assert payload["automatic_rewrite_allowed"] is False


def test_fixture_file_contains_no_story_chapter_dependency() -> None:
    document = yaml.safe_load(FIXTURES.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert all("chapter" not in case for case in document["cases"])
