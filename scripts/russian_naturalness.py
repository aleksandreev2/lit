#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "rules/regressions.yaml"
DEFAULT_FIXTURES = ROOT / "tests/fixtures/russian_naturalness_cases.yaml"
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:-[A-Za-zА-Яа-яЁё]+)*")
SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)")


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in WORD_RE.finditer(text)]


def load_rules(path: Path = DEFAULT_RULES) -> list[dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        rule
        for rule in document.get("rules", [])
        if rule.get("owner_family") == "russian_naturalness" and rule.get("matcher")
    ]


def _matches(tokens: list[str], matcher: dict) -> bool:
    pattern = matcher["tokens"]
    if len(tokens) != len(pattern):
        return False
    return all(
        token in {item.casefold() for item in spec["any_of"]}
        for token, spec in zip(tokens, pattern)
    )


def analyze_lines(lines: list[str], rules: list[dict] | None = None) -> dict:
    rules = rules if rules is not None else load_rules()
    findings: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        for sentence_match in SENTENCE_RE.finditer(line):
            sentence = sentence_match.group(0).strip()
            if not sentence:
                continue
            tokens = _tokens(sentence)
            if not tokens:
                continue
            for rule in rules:
                matcher = rule["matcher"]
                if matcher.get("skip_if_question", False) and "?" in sentence:
                    continue
                if not _matches(tokens, matcher):
                    continue
                findings.append(
                    {
                        "rule": rule["id"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "confidence": matcher["confidence"],
                        "detection": rule["detection_type"],
                        "line": line_number,
                        "sentence": sentence,
                        "tokens": tokens,
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
    fixture_doc = yaml.safe_load(fixtures_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    seen_ids: set[str] = set()
    for case in fixture_doc.get("cases", []):
        case_id = case["id"]
        if case_id in seen_ids:
            errors.append(f"NATURALNESS_FIXTURE duplicate case id {case_id}")
            continue
        seen_ids.add(case_id)
        payload = analyze_text(case["text"], rules)
        actual = sorted({item["rule"] for item in payload["findings"]})
        expected = sorted(case["expected_rules"])
        if actual != expected:
            errors.append(
                f"NATURALNESS_FIXTURE {case_id}: expected={expected} "
                f"actual={actual} text={case['text']!r}"
            )
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
        print(f"RUSSIAN_NATURALNESS_CORPUS: PASS cases={len(fixture_doc['cases'])}")
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
