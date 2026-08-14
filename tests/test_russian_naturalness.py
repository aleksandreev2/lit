from __future__ import annotations

from pathlib import Path

from russian_naturalness import analyze_text, load_rules, validate_fixture_corpus

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules/regressions.yaml"
FIXTURES = ROOT / "tests/fixtures/russian_naturalness_cases.yaml"


def test_naturalness_fixture_corpus_is_exact() -> None:
    assert validate_fixture_corpus(RULES, FIXTURES) == []


def test_user_examples_are_detected() -> None:
    payload = analyze_text("— Я ладно.\n— Я нормально.\n", load_rules(RULES))
    assert payload["status"] == "BLOCK"
    assert {item["rule"] for item in payload["findings"]} == {"SB-RUS-001", "SB-RUS-002"}
    assert payload["counts"] == {"BLOCK": 1, "REVIEW": 1}


def test_complete_constructions_are_not_flagged() -> None:
    text = """— Я в порядке.
— У меня всё нормально.
— Я нормально себя чувствую.
— Я нормально говорю по-русски.
— Я хорошо помню этот день.
— Я плохо спал.
— Я всё нормально сделал.
"""
    payload = analyze_text(text, load_rules(RULES))
    assert payload["status"] == "PASS"
    assert payload["findings"] == []


def test_question_and_polite_ellipsis_avoid_false_positive() -> None:
    text = """— Ты нормально?
— Ты рано?
— Я нормально, спасибо.
— Я, ладно, пойду домой.
"""
    payload = analyze_text(text, load_rules(RULES))
    assert payload["status"] == "PASS"
    assert payload["findings"] == []


def test_broken_all_state_and_bare_time_are_separate_signals() -> None:
    payload = analyze_text("— Я всё нормально.\n— Он поздно.\n", load_rules(RULES))
    by_rule = {item["rule"]: item for item in payload["findings"]}
    assert by_rule["SB-RUS-003"]["severity"] == "BLOCK"
    assert by_rule["SB-RUS-004"]["severity"] == "REVIEW"
