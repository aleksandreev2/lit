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
    assert payload["counts"] == {"BLOCK": 2, "REVIEW": 0}


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


def test_morphology_catches_inflected_government_and_calques() -> None:
    text = """Она оплатила за билет.
Мы обсудили о проблеме.
Она надеялась об успехе.
Он интересовался об этой компании.
Это не делает никакого смысла.
"""
    payload = analyze_text(text, load_rules(RULES))
    assert payload["status"] == "BLOCK"
    assert {item["rule"] for item in payload["findings"]} == {
        "SB-RUS-007",
        "SB-RUS-008",
        "SB-RUS-009",
        "SB-RUS-010",
        "SB-RUS-012",
    }
    assert all(item["matcher_type"] == "LEMMA_WINDOW" for item in payload["findings"])


def test_case_government_flags_genitive_and_allows_dative() -> None:
    bad = analyze_text(
        "Согласно приказа директора, офис закрыли. Вопреки приказа он остался.",
        load_rules(RULES),
    )
    assert {item["rule"] for item in bad["findings"]} == {"SB-RUS-005", "SB-RUS-006"}
    assert all(item["evidence"]["observed_case"] == "gent" for item in bad["findings"])

    good = analyze_text(
        "Согласно его приказу, офис закрыли. Вопреки приказу он остался.",
        load_rules(RULES),
    )
    assert good["status"] == "PASS"
    assert good["findings"] == []


def test_lexical_collocation_and_full_sentence_calques_are_scoped() -> None:
    bad = analyze_text(
        "Я взял душ. Он спросил вопрос. Я в порядке с этим.",
        load_rules(RULES),
    )
    by_rule = {item["rule"]: item for item in bad["findings"]}
    assert by_rule["SB-RUS-015"]["severity"] == "BLOCK"
    assert by_rule["SB-RUS-016"]["severity"] == "REVIEW"
    assert by_rule["SB-RUS-017"]["severity"] == "BLOCK"

    good = analyze_text(
        "Я принял душ. Он задал вопрос. Я имею представление о рисках.",
        load_rules(RULES),
    )
    assert good["status"] == "PASS"


def test_shower_calque_does_not_capture_genitive_plural_souls() -> None:
    payload = analyze_text("Он взял пять душ под опеку.", load_rules(RULES))
    assert payload["status"] == "PASS"
    assert payload["findings"] == []


def test_review_only_possession_calques_remain_review() -> None:
    payload = analyze_text("Я имею идею. Я имею вопрос.", load_rules(RULES))
    assert payload["status"] == "REVIEW"
    assert payload["counts"] == {"BLOCK": 0, "REVIEW": 2}
    assert {item["rule"] for item in payload["findings"]} == {"SB-RUS-013", "SB-RUS-014"}


def test_finding_includes_neighboring_sentence_context() -> None:
    payload = analyze_text(
        "— Как ты?\n— Я нормально.\n— Тогда поехали.\n",
        load_rules(RULES),
    )
    finding = next(item for item in payload["findings"] if item["rule"] == "SB-RUS-002")
    assert finding["previous_sentence"] == "— Как ты?"
    assert finding["next_sentence"] == "— Тогда поехали."
