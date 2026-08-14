from __future__ import annotations

import json
from pathlib import Path

import yaml
from qa_artifact_check import validate_manifest
from qa_artifacts import generate_artifacts
from regression_check import validate_regressions

ROOT = Path(__file__).resolve().parents[1]

SYNTHETIC_TEXT = """Ирина открыла дверь и проверила официальный источник.
— Почему курс BTC изменился?
— Я не знаю точную причину, но мне сказали проверить новости, рынок и официальный источник перед любым выводом.
— Да.
— Нет.
— Ладно.
— Логично.
— Я нормально.
Цена в примере — 100 000 USD.
Ирина ещё раз проверила официальный источник перед разговором.
"""


def _make_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source = tmp_path / "synthetic-candidate.txt"
    source.write_text(SYNTHETIC_TEXT, encoding="utf-8")

    runtime = tmp_path / "runtime.yaml"
    runtime.write_text("through_chapter: 24\n", encoding="utf-8")

    state = tmp_path / "state.yaml"
    state.write_text(
        yaml.safe_dump(
            {
                "characters": [
                    {
                        "id": "SB-CHAR-IRINA",
                        "display_name": "Ирина",
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "artifacts"
    return source, runtime, state, output


def test_generate_editor_artifacts_and_verify_hashes(tmp_path: Path) -> None:
    source, runtime, state, output = _make_inputs(tmp_path)
    manifest = generate_artifacts(
        source,
        output,
        parent_runtime=runtime,
        character_state=state,
    )

    assert len(manifest["artifacts"]) == 14
    assert not Path(manifest["source"]["path"]).is_absolute()
    assert not Path(manifest["regression_rules"]["path"]).is_absolute()
    assert validate_manifest(output / "artifact_manifest.json") == []

    dialogue = (output / "dialogue_only.txt").read_text(encoding="utf-8")
    narration = (output / "narration_only.txt").read_text(encoding="utf-8")
    assert "Почему курс BTC" in dialogue
    assert "Ирина открыла дверь" in narration
    assert "Почему курс BTC" not in narration


def test_question_knowledge_money_and_text_signals_are_review_candidates(tmp_path: Path) -> None:
    source, runtime, state, output = _make_inputs(tmp_path)
    generate_artifacts(source, output, parent_runtime=runtime, character_state=state)

    questions = json.loads((output / "question_audit.json").read_text(encoding="utf-8"))
    assert questions["questions"][0]["convenient_exposition_candidate"] is True

    knowledge = json.loads(
        (output / "knowledge_claim_candidates.json").read_text(encoding="utf-8")
    )
    assert any("мне сказали" in item["text"] for item in knowledge["candidates"])

    research = json.loads((output / "research_candidates.json").read_text(encoding="utf-8"))
    assert research["automatic_research_pass"] is False
    assert any(item["text"] == "100 000 USD" for item in research["candidates"])

    signals = json.loads((output / "text_signals.json").read_text(encoding="utf-8"))
    rules = {item["rule"] for item in signals["findings"]}
    assert "SB-DIA-001" in rules
    assert "SB-DIA-003" in rules

    naturalness = json.loads((output / "russian_naturalness.json").read_text(encoding="utf-8"))
    assert naturalness["status"] == "REVIEW"
    assert {item["rule"] for item in naturalness["findings"]} == {"SB-RUS-002"}


def test_continuity_and_delta_reports_cannot_promote_canon(tmp_path: Path) -> None:
    source, runtime, state, output = _make_inputs(tmp_path)
    generate_artifacts(source, output, parent_runtime=runtime, character_state=state)

    continuity = json.loads((output / "continuity_audit.json").read_text(encoding="utf-8"))
    assert "Ирина" in continuity["known_character_mentions"]
    assert continuity["automatic_canon_delta"] is False

    delta = json.loads((output / "chapter_delta_candidate.json").read_text(encoding="utf-8"))
    assert delta["status"] == "REVIEW"
    assert delta["automatic_promotion_allowed"] is False
    assert delta["fact_changes"] == []


def test_artifact_tamper_breaks_manifest_verification(tmp_path: Path) -> None:
    source, runtime, state, output = _make_inputs(tmp_path)
    generate_artifacts(source, output, parent_runtime=runtime, character_state=state)
    (output / "dialogue_only.txt").write_text("tampered\n", encoding="utf-8")

    errors = validate_manifest(output / "artifact_manifest.json")
    assert any("hash mismatch dialogue_only.txt" in error for error in errors)


def test_rule_change_invalidates_generated_artifacts(tmp_path: Path) -> None:
    source, runtime, state, output = _make_inputs(tmp_path)
    rules_copy = tmp_path / "regressions.yaml"
    rules_copy.write_text(
        (ROOT / "rules/regressions.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    generate_artifacts(
        source,
        output,
        parent_runtime=runtime,
        character_state=state,
        regression_rules=rules_copy,
    )
    rules_copy.write_text(rules_copy.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")

    errors = validate_manifest(output / "artifact_manifest.json")
    assert any("QA_ARTIFACT_RULES hash mismatch" in error for error in errors)


def test_regression_register_has_fixture_coverage() -> None:
    assert validate_regressions(ROOT / "rules/regressions.yaml") == []


def test_machine_regression_without_fixture_is_rejected(tmp_path: Path) -> None:
    document = yaml.safe_load((ROOT / "rules/regressions.yaml").read_text(encoding="utf-8"))
    document["rules"][0]["fixture_test_path"] = "tests/does_not_exist.py"
    path = tmp_path / "regressions.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")

    errors = validate_regressions(path)
    assert any(error.startswith("REGRESSION_FIXTURE SB-DIA-001") for error in errors)
