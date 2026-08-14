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
DEFAULT_FIXTURES = ROOT / "tests/fixtures/russian_naturalness_cases.yaml"
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:-[A-Za-zА-Яа-яЁё]+)*")


@lru_cache(maxsize=1)
def _morph_analyzer() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=8192)
def _morph_word(word: str) -> dict:
    parse = _morph_analyzer().parse(word)[0]
    return {
        "text": word,
        "normalized": word.casefold(),
        "lemma": parse.normal_form.casefold(),
        "pos": parse.tag.POS,
        "case": parse.tag.case,
    }


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in WORD_RE.finditer(text)]


def _morph_tokens(text: str) -> list[dict]:
    return [_morph_word(match.group(0)) for match in WORD_RE.finditer(text)]


def load_rules(path: Path = DEFAULT_RULES) -> list[dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        rule
        for rule in document.get("rules", [])
        if rule.get("owner_family") == "russian_naturalness" and rule.get("matcher")
    ]


def _token_pattern_evidence(tokens: list[str], matcher: dict) -> dict | None:
    pattern = matcher["tokens"]
    if len(tokens) != len(pattern):
        return None
    if not all(
        token in {item.casefold() for item in spec["any_of"]}
        for token, spec in zip(tokens, pattern)
    ):
        return None
    return {"matched_tokens": tokens}


def _lemma_matches(token: dict, spec: dict) -> bool:
    allowed = {item.casefold() for item in spec["any_of"]}
    return token["lemma"] in allowed


def _lemma_window_evidence(tokens: list[dict], matcher: dict) -> dict | None:
    pattern = matcher["lemmas"]
    max_gap = matcher["max_gap"]
    require_full_sentence = matcher["require_full_sentence"]
    if len(tokens) < len(pattern):
        return None

    first_positions = [
        index
        for index, token in enumerate(tokens)
        if _lemma_matches(token, pattern[0])
        and (not require_full_sentence or index == 0)
    ]
    paths: list[list[int]] = [[index] for index in first_positions]

    for spec in pattern[1:]:
        next_paths: list[list[int]] = []
        for path in paths:
            previous = path[-1]
            stop = min(len(tokens), previous + max_gap + 2)
            for index in range(previous + 1, stop):
                if _lemma_matches(tokens[index], spec):
                    next_paths.append([*path, index])
        paths = next_paths
        if not paths:
            return None

    for path in paths:
        if require_full_sentence and path[-1] != len(tokens) - 1:
            continue
        return {
            "matched_tokens": [tokens[index]["text"] for index in path],
            "matched_lemmas": [tokens[index]["lemma"] for index in path],
            "positions": path,
        }
    return None


def _case_after_evidence(tokens: list[dict], matcher: dict) -> dict | None:
    trigger_lemmas = {item.casefold() for item in matcher["trigger_lemmas"]}
    target_pos = set(matcher["target_pos"])
    allowed_cases = set(matcher["allowed_cases"])
    max_scan = matcher["max_scan"]

    for trigger_index, token in enumerate(tokens):
        if token["lemma"] not in trigger_lemmas:
            continue
        stop = min(len(tokens), trigger_index + max_scan + 1)
        for target_index in range(trigger_index + 1, stop):
            target = tokens[target_index]
            if target["pos"] not in target_pos:
                continue
            if target["case"] is None:
                break
            if target["case"] in allowed_cases:
                break
            return {
                "trigger": token["text"],
                "trigger_lemma": token["lemma"],
                "target": target["text"],
                "target_lemma": target["lemma"],
                "observed_case": target["case"],
                "allowed_cases": sorted(allowed_cases),
            }
    return None


def _match_evidence(sentence: str, matcher: dict) -> dict | None:
    if matcher.get("skip_if_question", False) and "?" in sentence:
        return None
    matcher_type = matcher["type"]
    if matcher_type == "TOKEN_PATTERN":
        return _token_pattern_evidence(_tokens(sentence), matcher)
    morph_tokens = _morph_tokens(sentence)
    if matcher_type == "LEMMA_WINDOW":
        return _lemma_window_evidence(morph_tokens, matcher)
    if matcher_type == "CASE_AFTER":
        return _case_after_evidence(morph_tokens, matcher)
    raise ValueError(f"unsupported naturalness matcher type: {matcher_type}")


def _sentence_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        for span in sentenize(line):
            sentence = span.text.strip()
            if sentence and _tokens(sentence):
                entries.append({"line": line_number, "sentence": sentence})
    return entries


def analyze_lines(lines: list[str], rules: list[dict] | None = None) -> dict:
    rules = rules if rules is not None else load_rules()
    entries = _sentence_entries(lines)
    findings: list[dict] = []
    for sentence_index, entry in enumerate(entries):
        sentence = entry["sentence"]
        for rule in rules:
            matcher = rule["matcher"]
            evidence = _match_evidence(sentence, matcher)
            if evidence is None:
                continue
            findings.append(
                {
                    "rule": rule["id"],
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "confidence": matcher["confidence"],
                    "detection": rule["detection_type"],
                    "matcher_type": matcher["type"],
                    "line": entry["line"],
                    "sentence": sentence,
                    "previous_sentence": (
                        entries[sentence_index - 1]["sentence"] if sentence_index else None
                    ),
                    "next_sentence": (
                        entries[sentence_index + 1]["sentence"]
                        if sentence_index + 1 < len(entries)
                        else None
                    ),
                    "evidence": evidence,
                    "message": matcher["message"],
                    "suggestions": matcher["suggestions"],
                }
            )

    counts = Counter(item["severity"] for item in findings)
    status = "BLOCK" if counts["BLOCK"] else ("REVIEW" if counts["REVIEW"] else "PASS")
    return {
        "status": status,
        "count": len(findings),
        "counts": {"BLOCK": counts["BLOCK"], "REVIEW": counts["REVIEW"]},
        "findings": findings,
        "note": (
            "Deterministic/heuristic naturalness signals only; semantic editorial review "
            "remains required."
        ),
    }


def analyze_text(text: str, rules: list[dict] | None = None) -> dict:
    return analyze_lines(text.splitlines(), rules)


def validate_fixture_corpus(
    rules_path: Path = DEFAULT_RULES,
    fixtures_path: Path = DEFAULT_FIXTURES,
) -> list[str]:
    rules = load_rules(rules_path)
    rule_ids = {rule["id"] for rule in rules}
    fixture_doc = yaml.safe_load(fixtures_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    seen_ids: set[str] = set()
    exercised_rules: set[str] = set()
    guarded_rules: set[str] = set()

    for case in fixture_doc.get("cases", []):
        case_id = case["id"]
        if case_id in seen_ids:
            errors.append(f"NATURALNESS_FIXTURE duplicate case id {case_id}")
            continue
        seen_ids.add(case_id)
        unknown_expected = set(case.get("expected_rules", [])) - rule_ids
        unknown_guards = set(case.get("guards_rules", [])) - rule_ids
        if unknown_expected:
            errors.append(
                f"NATURALNESS_FIXTURE {case_id}: unknown expected rules "
                f"{sorted(unknown_expected)}"
            )
        if unknown_guards:
            errors.append(
                f"NATURALNESS_FIXTURE {case_id}: unknown guarded rules "
                f"{sorted(unknown_guards)}"
            )

        payload = analyze_text(case["text"], rules)
        actual = sorted({item["rule"] for item in payload["findings"]})
        expected = sorted(case.get("expected_rules", []))
        if actual != expected:
            errors.append(
                f"NATURALNESS_FIXTURE {case_id}: expected={expected} "
                f"actual={actual} text={case['text']!r}"
            )
        expected_status = case.get("expected_status")
        if expected_status is not None and payload["status"] != expected_status:
            errors.append(
                f"NATURALNESS_FIXTURE {case_id}: expected status={expected_status} "
                f"actual={payload['status']}"
            )
        exercised_rules.update(case.get("expected_rules", []))
        guarded_rules.update(case.get("guards_rules", []))

    missing_exercise = sorted(rule_ids - exercised_rules)
    missing_guards = sorted(rule_ids - guarded_rules)
    if missing_exercise:
        errors.append(f"NATURALNESS_FIXTURE rules without bad coverage: {missing_exercise}")
    if missing_guards:
        errors.append(f"NATURALNESS_FIXTURE rules without false-positive guards: {missing_guards}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Russian fiction naturalness regression checker.")
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", dest="json_output", action="store_true")
    parser.add_argument("--fail-on-block", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        errors = validate_fixture_corpus(args.rules, args.fixtures)
        if errors:
            print("RUSSIAN_NATURALNESS_CORPUS: FAIL")
            for error in errors:
                print(f"- {error}")
            return 1
        fixture_doc = yaml.safe_load(args.fixtures.read_text(encoding="utf-8"))
        rules = load_rules(args.rules)
        print(
            "RUSSIAN_NATURALNESS_CORPUS: PASS "
            f"cases={len(fixture_doc['cases'])} rules={len(rules)}"
        )
        return 0

    if args.path is None:
        parser.error("path is required unless --self-test is used")
    payload = analyze_text(args.path.read_text(encoding="utf-8"), load_rules(args.rules))
    payload["file"] = str(args.path)
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"RUSSIAN_NATURALNESS: {payload['status']} count={payload['count']} "
            f"BLOCK={payload['counts']['BLOCK']} REVIEW={payload['counts']['REVIEW']}"
        )
        for item in payload["findings"]:
            print(
                f"- {item['rule']} {item['severity']} line {item['line']}: "
                f"{item['message']} :: {item['sentence']}"
            )
    return 1 if args.fail_on_block and payload["counts"]["BLOCK"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
