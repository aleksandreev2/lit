#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pymorphy3
import yaml
from razdel import sentenize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "rules/regressions.yaml"
DEFAULT_FIXTURES = ROOT / "tests/fixtures/pronoun_coreference_cases.yaml"
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:-[A-Za-zА-Яа-яЁё]+)*")

PERSONAL_PRONOUNS = {
    "он": ("masc", "sing"),
    "она": ("femn", "sing"),
    "оно": ("neut", "sing"),
    "они": (None, "plur"),
}
POSSESSIVE_FORMS = {
    "его": ("masc", "sing"),
    "её": ("femn", "sing"),
    "ее": ("femn", "sing"),
    "их": (None, "plur"),
}
PROFILE_GENDER = {"MASC": "masc", "FEM": "femn", "NEUT": "neut", "UNKNOWN": None}
PERSON_GRAMMEMES = {"Name", "Surn", "Patr"}
NOUN_LIKE_POS = {"NOUN"}
POSSESSIVE_GAP_POS = {"ADJF", "PRTF", "NUMR"}


@lru_cache(maxsize=1)
def _morph_analyzer() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=8192)
def _morph_word(word: str) -> dict:
    parses = _morph_analyzer().parse(word)
    noun_parses = [parse for parse in parses if parse.tag.POS in NOUN_LIKE_POS]
    primary = noun_parses[0] if noun_parses else parses[0]
    grammemes = set(primary.tag.grammemes)
    return {
        "text": word,
        "normalized": word.casefold(),
        "lemma": primary.normal_form.casefold(),
        "pos": primary.tag.POS,
        "gender": primary.tag.gender,
        "number": primary.tag.number,
        "case": primary.tag.case,
        "cases": sorted({parse.tag.case for parse in noun_parses if parse.tag.case}),
        "genders": sorted({parse.tag.gender for parse in noun_parses if parse.tag.gender}),
        "numbers": sorted({parse.tag.number for parse in noun_parses if parse.tag.number}),
        "is_person_name": bool(grammemes & PERSON_GRAMMEMES),
        "is_animate": "anim" in grammemes,
    }


def _word_tokens(text: str) -> list[dict]:
    return [_morph_word(match.group(0)) for match in WORD_RE.finditer(text)]


def load_rules(path: Path = DEFAULT_RULES) -> dict[str, dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        rule["id"]: rule
        for rule in document.get("rules", [])
        if rule.get("owner_family") == "pronoun_coreference"
    }


def load_character_profiles(path: Path | None) -> list[dict]:
    if path is None:
        return []
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return document.get("characters", [])


def _profile_aliases(profiles: list[dict]) -> list[dict]:
    aliases: list[dict] = []
    for profile in profiles:
        names = [profile.get("display_name"), *profile.get("aliases", [])]
        for name in names:
            if not name:
                continue
            words = tuple(match.group(0).casefold() for match in WORD_RE.finditer(name))
            if not words:
                continue
            aliases.append(
                {
                    "words": words,
                    "character_id": profile.get("id"),
                    "display_name": profile.get("display_name") or name,
                    "gender": PROFILE_GENDER.get(profile.get("grammatical_gender", "UNKNOWN")),
                }
            )
    return sorted(aliases, key=lambda item: len(item["words"]), reverse=True)


def _sentence_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        for span in sentenize(line):
            sentence = span.text.strip()
            tokens = _word_tokens(sentence)
            if tokens:
                entries.append({"line": line_number, "sentence": sentence, "tokens": tokens})
    return entries


def _candidate_key(candidate: dict) -> tuple:
    if candidate.get("character_id"):
        return ("CHARACTER", candidate["character_id"])
    return (
        candidate["source"],
        candidate["lemma"],
        candidate.get("gender"),
        candidate.get("number"),
    )


def _candidate_payload(candidate: dict) -> dict:
    return {
        "text": candidate["text"],
        "lemma": candidate["lemma"],
        "source": candidate["source"],
        "character_id": candidate.get("character_id"),
        "gender": candidate.get("gender"),
        "number": candidate.get("number"),
        "sentence_index": candidate["sentence_index"],
        "token_index": candidate["token_index"],
        "subject_candidate": candidate["subject_candidate"],
    }


def _extract_candidates(entry: dict, sentence_index: int, aliases: list[dict]) -> list[dict]:
    tokens = entry["tokens"]
    normalized = [token["normalized"] for token in tokens]
    candidates: list[dict] = []
    profile_covered: set[int] = set()

    for alias in aliases:
        width = len(alias["words"])
        for start in range(0, len(tokens) - width + 1):
            if tuple(normalized[start : start + width]) != alias["words"]:
                continue
            end = start + width - 1
            profile_covered.update(range(start, end + 1))
            head = tokens[end]
            candidates.append(
                {
                    "text": " ".join(token["text"] for token in tokens[start : end + 1]),
                    "lemma": alias["display_name"].casefold(),
                    "source": "CHARACTER_STATE",
                    "character_id": alias["character_id"],
                    "gender": alias["gender"] or head.get("gender"),
                    "number": head.get("number") or "sing",
                    "is_person": True,
                    "sentence_index": sentence_index,
                    "token_index": end,
                    "subject_candidate": "nomn" in head.get("cases", []),
                }
            )

    for token_index, token in enumerate(tokens):
        if token_index in profile_covered or token["pos"] != "NOUN":
            continue
        is_person = token["is_person_name"] or token["is_animate"]
        candidates.append(
            {
                "text": token["text"],
                "lemma": token["lemma"],
                "source": "MORPH_NAME" if is_person else "MORPH_NOUN",
                "character_id": None,
                "gender": token.get("gender"),
                "number": token.get("number"),
                "is_person": is_person,
                "sentence_index": sentence_index,
                "token_index": token_index,
                "subject_candidate": "nomn" in token.get("cases", []),
            }
        )
    return candidates


def _recent_candidates(
    all_candidates: list[list[dict]], sentence_index: int, token_index: int
) -> list[dict]:
    recent: list[dict] = []
    for index in range(max(0, sentence_index - 1), sentence_index + 1):
        for candidate in all_candidates[index]:
            if index == sentence_index and candidate["token_index"] >= token_index:
                continue
            recent.append(candidate)
    recent.sort(key=lambda item: (item["sentence_index"], item["token_index"]), reverse=True)

    deduped: list[dict] = []
    seen: set[tuple] = set()
    for candidate in recent:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _compatible(candidate: dict, gender: str | None, number: str) -> bool:
    candidate_number = candidate.get("number")
    if candidate_number and candidate_number != number:
        return False
    if number == "plur":
        return candidate_number == "plur"
    candidate_gender = candidate.get("gender")
    return candidate_gender is not None and candidate_gender == gender


def _preferred_compatible(recent: list[dict], gender: str | None, number: str) -> list[dict]:
    compatible = [item for item in recent if _compatible(item, gender, number)]
    person = [item for item in compatible if item["is_person"]]
    return person or compatible


def _plural_group(recent: list[dict]) -> dict | None:
    people = [item for item in recent if item["is_person"] and item.get("number") != "plur"]
    if len(people) != 2:
        return None
    return {
        "text": " + ".join(reversed([item["text"] for item in people])),
        "lemma": "group",
        "source": "SYNTHETIC_GROUP",
        "character_id": None,
        "gender": None,
        "number": "plur",
        "is_person": True,
        "sentence_index": max(item["sentence_index"] for item in people),
        "token_index": max(item["token_index"] for item in people),
        "subject_candidate": False,
    }


def _possessive_target(tokens: list[dict], index: int) -> dict | None:
    for target_index in range(index + 1, min(len(tokens), index + 4)):
        target = tokens[target_index]
        if target["pos"] == "NOUN":
            return {"token_index": target_index, "text": target["text"], "lemma": target["lemma"]}
        if target["pos"] not in POSSESSIVE_GAP_POS:
            return None
    return None


def _rule_finding(
    rule: dict,
    entry: dict,
    sentence_index: int,
    entries: list[dict],
    token_index: int,
    evidence: dict,
) -> dict:
    return {
        "rule": rule["id"],
        "name": rule["name"],
        "severity": rule["severity"],
        "confidence": evidence.pop("confidence"),
        "detection": rule["detection_type"],
        "line": entry["line"],
        "sentence": entry["sentence"],
        "previous_sentence": entries[sentence_index - 1]["sentence"] if sentence_index else None,
        "next_sentence": (
            entries[sentence_index + 1]["sentence"] if sentence_index + 1 < len(entries) else None
        ),
        "token_index": token_index,
        "evidence": evidence,
        "message": rule["description"],
        "automatic_rewrite_allowed": False,
    }


def analyze_lines(
    lines: list[str],
    rules: dict[str, dict] | None = None,
    character_profiles: list[dict] | None = None,
) -> dict:
    rules = rules if rules is not None else load_rules()
    profiles = character_profiles or []
    aliases = _profile_aliases(profiles)
    entries = _sentence_entries(lines)
    candidates_by_sentence = [
        _extract_candidates(entry, index, aliases) for index, entry in enumerate(entries)
    ]
    findings: list[dict] = []
    ambiguous_personal_positions: set[tuple[int, int]] = set()
    coverage = Counter()

    for sentence_index, entry in enumerate(entries):
        tokens = entry["tokens"]
        for token_index, token in enumerate(tokens):
            surface = token["normalized"]
            if surface in PERSONAL_PRONOUNS:
                coverage["personal_pronouns"] += 1
                gender, number = PERSONAL_PRONOUNS[surface]
                recent = _recent_candidates(candidates_by_sentence, sentence_index, token_index)
                compatible = _preferred_compatible(recent, gender, number)
                if number == "plur" and not compatible:
                    group = _plural_group(recent)
                    if group:
                        compatible = [group]

                if len(compatible) >= 2 and "SB-PRN-001" in rules:
                    coverage["ambiguous"] += 1
                    ambiguous_personal_positions.add((sentence_index, token_index))
                    findings.append(
                        _rule_finding(
                            rules["SB-PRN-001"],
                            entry,
                            sentence_index,
                            entries,
                            token_index,
                            {
                                "confidence": "MEDIUM",
                                "pronoun": token["text"],
                                "expected_gender": gender,
                                "expected_number": number,
                                "candidates": [_candidate_payload(item) for item in compatible],
                            },
                        )
                    )
                elif len(compatible) == 1:
                    coverage["unique_candidate"] += 1
                elif recent:
                    known_recent = [
                        item
                        for item in recent
                        if item.get("gender") is not None or item.get("number") is not None
                    ]
                    if known_recent and "SB-PRN-002" in rules:
                        coverage["gender_or_number_conflict"] += 1
                        findings.append(
                            _rule_finding(
                                rules["SB-PRN-002"],
                                entry,
                                sentence_index,
                                entries,
                                token_index,
                                {
                                    "confidence": "LOW",
                                    "pronoun": token["text"],
                                    "expected_gender": gender,
                                    "expected_number": number,
                                    "recent_candidates": [
                                        _candidate_payload(item) for item in known_recent
                                    ],
                                },
                            )
                        )
                    else:
                        coverage["unresolved"] += 1
                else:
                    coverage["unresolved"] += 1

            if surface in POSSESSIVE_FORMS:
                target = _possessive_target(tokens, token_index)
                if target is None:
                    continue
                coverage["possessive_markers"] += 1
                gender, number = POSSESSIVE_FORMS[surface]
                recent = _recent_candidates(candidates_by_sentence, sentence_index, token_index)
                owners = [
                    item
                    for item in _preferred_compatible(recent, gender, number)
                    if item["is_person"]
                ]
                if number == "plur" and not owners:
                    group = _plural_group(recent)
                    if group:
                        owners = [group]

                if len(owners) >= 2 and "SB-PRN-003" in rules:
                    findings.append(
                        _rule_finding(
                            rules["SB-PRN-003"],
                            entry,
                            sentence_index,
                            entries,
                            token_index,
                            {
                                "confidence": "MEDIUM",
                                "possessive": token["text"],
                                "possessed_noun": target,
                                "owner_candidates": [_candidate_payload(item) for item in owners],
                            },
                        )
                    )
                elif len(owners) == 1 and "SB-PRN-004" in rules:
                    same_sentence_subjects = [
                        item
                        for item in recent
                        if item["sentence_index"] == sentence_index
                        and item["is_person"]
                        and item["subject_candidate"]
                    ]
                    subject = same_sentence_subjects[0] if same_sentence_subjects else None
                    if subject and _candidate_key(subject) == _candidate_key(owners[0]):
                        findings.append(
                            _rule_finding(
                                rules["SB-PRN-004"],
                                entry,
                                sentence_index,
                                entries,
                                token_index,
                                {
                                    "confidence": "MEDIUM",
                                    "possessive": token["text"],
                                    "possessed_noun": target,
                                    "subject_candidate": _candidate_payload(subject),
                                    "owner_candidate": _candidate_payload(owners[0]),
                                },
                            )
                        )

            if token["lemma"] == "свой":
                coverage["reflexive_possessives"] += 1
                ambiguous = [
                    position
                    for position in ambiguous_personal_positions
                    if position[0] == sentence_index and position[1] < token_index
                ]
                if ambiguous and "SB-PRN-005" in rules:
                    findings.append(
                        _rule_finding(
                            rules["SB-PRN-005"],
                            entry,
                            sentence_index,
                            entries,
                            token_index,
                            {
                                "confidence": "MEDIUM",
                                "reflexive": token["text"],
                                "ambiguous_subject_pronoun_positions": [
                                    {"sentence_index": sent, "token_index": tok}
                                    for sent, tok in sorted(ambiguous)
                                ],
                            },
                        )
                    )

    counts = Counter(item["severity"] for item in findings)
    return {
        "status": "REVIEW" if findings else "PASS",
        "count": len(findings),
        "counts": {"BLOCK": counts["BLOCK"], "REVIEW": counts["REVIEW"]},
        "coverage": {
            key: coverage[key]
            for key in (
                "personal_pronouns",
                "possessive_markers",
                "reflexive_possessives",
                "unique_candidate",
                "ambiguous",
                "gender_or_number_conflict",
                "unresolved",
            )
        },
        "findings": findings,
        "automatic_rewrite_allowed": False,
        "note": (
            "Fast morphology/recency candidate audit only. A REVIEW finding is not a proven "
            "coreference error; full literary coreference remains semantic review."
        ),
    }


def analyze_text(
    text: str,
    rules: dict[str, dict] | None = None,
    character_profiles: list[dict] | None = None,
) -> dict:
    return analyze_lines(text.splitlines(), rules, character_profiles)


def validate_fixture_corpus(
    rules_path: Path = DEFAULT_RULES,
    fixtures_path: Path = DEFAULT_FIXTURES,
) -> list[str]:
    rules = load_rules(rules_path)
    rule_ids = set(rules)
    fixture_doc = yaml.safe_load(fixtures_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    seen_ids: set[str] = set()
    exercised_rules: set[str] = set()
    guarded_rules: set[str] = set()

    for case in fixture_doc.get("cases", []):
        case_id = case["id"]
        if case_id in seen_ids:
            errors.append(f"PRONOUN_FIXTURE duplicate case id {case_id}")
            continue
        seen_ids.add(case_id)
        expected = set(case.get("expected_rules", []))
        guards = set(case.get("guards_rules", []))
        if expected - rule_ids:
            errors.append(f"PRONOUN_FIXTURE {case_id}: unknown expected rules {sorted(expected - rule_ids)}")
        if guards - rule_ids:
            errors.append(f"PRONOUN_FIXTURE {case_id}: unknown guarded rules {sorted(guards - rule_ids)}")

        payload = analyze_text(case["text"], rules, case.get("characters", []))
        actual = {item["rule"] for item in payload["findings"]}
        if actual != expected:
            errors.append(
                f"PRONOUN_FIXTURE {case_id}: expected={sorted(expected)} "
                f"actual={sorted(actual)} text={case['text']!r}"
            )
        expected_status = case.get("expected_status")
        if expected_status is not None and payload["status"] != expected_status:
            errors.append(
                f"PRONOUN_FIXTURE {case_id}: expected status={expected_status} "
                f"actual={payload['status']}"
            )
        exercised_rules.update(expected)
        guarded_rules.update(guards)

    missing_exercise = sorted(rule_ids - exercised_rules)
    missing_guards = sorted(rule_ids - guarded_rules)
    if missing_exercise:
        errors.append(f"PRONOUN_FIXTURE rules without bad coverage: {missing_exercise}")
    if missing_guards:
        errors.append(f"PRONOUN_FIXTURE rules without false-positive guards: {missing_guards}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast Russian pronoun/coreference candidate audit.")
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--character-state", type=Path)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", dest="json_output", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        errors = validate_fixture_corpus(args.rules, args.fixtures)
        if errors:
            print("PRONOUN_COREFERENCE_CORPUS: FAIL")
            for error in errors:
                print(f"- {error}")
            return 1
        fixture_doc = yaml.safe_load(args.fixtures.read_text(encoding="utf-8"))
        print(
            "PRONOUN_COREFERENCE_CORPUS: PASS "
            f"cases={len(fixture_doc['cases'])} rules={len(load_rules(args.rules))}"
        )
        return 0

    if args.path is None:
        parser.error("path is required unless --self-test is used")
    profiles = load_character_profiles(args.character_state)
    payload = analyze_text(
        args.path.read_text(encoding="utf-8"),
        load_rules(args.rules),
        profiles,
    )
    payload["file"] = str(args.path)
    payload["character_state"] = str(args.character_state) if args.character_state else None
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"PRONOUN_COREFERENCE: {payload['status']} count={payload['count']}")
        for item in payload["findings"]:
            print(
                f"- {item['rule']} {item['severity']} line {item['line']}: "
                f"{item['message']} :: {item['sentence']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
