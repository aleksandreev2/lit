#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import yaml
from pronoun_coreference import (
    PERSONAL_PRONOUNS,
    _candidate_key,
    _candidate_payload,
    _compatible,
    _extract_candidates,
    _profile_aliases,
    _word_tokens,
    analyze_text as analyze_fast_pronouns,
    load_character_profiles,
)
from razdel import sentenize
from regression_check import validate_regressions
from text_signals import DIALOGUE_RE

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "rules/semantic_coreference_regressions.yaml"
DEFAULT_FIXTURES = ROOT / "tests/fixtures/semantic_coreference_cases.yaml"

SPEECH_VERB_RE = re.compile(
    r"\b(?:сказал(?:а|и)?|ответил(?:а|и)?|спросил(?:а|и)?|произн[её]с(?:ла|ли)?|"
    r"добавил(?:а|и)?|заметил(?:а|и)?|пояснил(?:а|и)?|возразил(?:а|и)?|"
    r"прошептал(?:а|и)?|крикнул(?:а|и)?|буркнул(?:а|и)?)\b",
    re.IGNORECASE,
)


def load_rules(path: Path = DEFAULT_RULES) -> dict[str, dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        rule["id"]: rule
        for rule in document.get("rules", [])
        if rule.get("owner_family") == "semantic_coreference"
    }


def _sentence_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    paragraph_index = -1
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        paragraph_index += 1
        for span in sentenize(line):
            sentence = span.text.strip()
            tokens = _word_tokens(sentence)
            if tokens:
                entries.append(
                    {
                        "line": line_number,
                        "paragraph": paragraph_index,
                        "sentence": sentence,
                        "tokens": tokens,
                        "dialogue": bool(DIALOGUE_RE.match(line)),
                    }
                )
    return entries


def _recent_candidates(
    all_candidates: list[list[dict]],
    sentence_index: int,
    token_index: int,
    lookback: int,
) -> list[dict]:
    recent: list[dict] = []
    start = max(0, sentence_index - lookback)
    for index in range(start, sentence_index + 1):
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


def _compatible_people(recent: list[dict], gender: str | None, number: str) -> list[dict]:
    return [
        item
        for item in recent
        if item["is_person"] and _compatible(item, gender, number)
    ]


def _finding(
    rule: dict,
    *,
    line: int,
    sentence: str,
    confidence: str,
    evidence: dict,
) -> dict:
    return {
        "rule": rule["id"],
        "name": rule["name"],
        "severity": rule["severity"],
        "detection": rule["detection_type"],
        "confidence": confidence,
        "line": line,
        "sentence": sentence,
        "message": rule["description"],
        "evidence": evidence,
        "automatic_rewrite_allowed": False,
    }


def _long_distance_findings(
    entries: list[dict],
    candidates_by_sentence: list[list[dict]],
    rules: dict[str, dict],
) -> list[dict]:
    findings: list[dict] = []
    for sentence_index, entry in enumerate(entries):
        for token_index, token in enumerate(entry["tokens"]):
            surface = token["normalized"]
            if surface not in PERSONAL_PRONOUNS:
                continue
            gender, number = PERSONAL_PRONOUNS[surface]
            immediate = _compatible_people(
                _recent_candidates(candidates_by_sentence, sentence_index, token_index, 1),
                gender,
                number,
            )
            if immediate:
                continue
            broad = _compatible_people(
                _recent_candidates(candidates_by_sentence, sentence_index, token_index, 4),
                gender,
                number,
            )
            far = [
                item
                for item in broad
                if sentence_index - item["sentence_index"] >= 2
            ]
            if not far:
                continue
            nearest_distance = min(sentence_index - item["sentence_index"] for item in far)
            findings.append(
                _finding(
                    rules["SB-CTX-001"],
                    line=entry["line"],
                    sentence=entry["sentence"],
                    confidence="MEDIUM",
                    evidence={
                        "pronoun": token["text"],
                        "sentence_index": sentence_index,
                        "nearest_sentence_distance": nearest_distance,
                        "candidates": [_candidate_payload(item) for item in far[:5]],
                    },
                )
            )
    return findings


def _zero_subject_findings(
    entries: list[dict],
    candidates_by_sentence: list[list[dict]],
    rules: dict[str, dict],
) -> list[dict]:
    findings: list[dict] = []
    for sentence_index, entry in enumerate(entries):
        tokens = entry["tokens"]
        verb_index = next(
            (
                index
                for index, token in enumerate(tokens[:4])
                if token.get("pos") == "VERB"
                and token.get("gender") in {"masc", "femn", "neut"}
            ),
            None,
        )
        if verb_index is None:
            continue

        if any(
            token["normalized"] in PERSONAL_PRONOUNS
            for token in tokens[:verb_index]
        ):
            continue

        current_subjects = [
            item
            for item in candidates_by_sentence[sentence_index]
            if item["is_person"] and item["subject_candidate"]
        ]
        if current_subjects:
            continue

        verb = tokens[verb_index]
        number = verb.get("number") or "sing"
        recent = _recent_candidates(
            candidates_by_sentence,
            sentence_index,
            0,
            2,
        )
        compatible = _compatible_people(recent, verb.get("gender"), number)
        if len(compatible) < 2:
            continue

        findings.append(
            _finding(
                rules["SB-CTX-003"],
                line=entry["line"],
                sentence=entry["sentence"],
                confidence="MEDIUM",
                evidence={
                    "verb": verb["text"],
                    "verb_gender": verb.get("gender"),
                    "verb_number": number,
                    "candidate_subjects": [_candidate_payload(item) for item in compatible[:5]],
                },
            )
        )
    return findings


def _line_person_candidates(
    lines: list[str],
    line_number: int,
    aliases: list[dict],
) -> list[dict]:
    if line_number < 1 or line_number > len(lines):
        return []
    tokens = _word_tokens(lines[line_number - 1])
    if not tokens:
        return []
    entry = {"tokens": tokens}
    return [
        item
        for item in _extract_candidates(entry, 0, aliases)
        if item["is_person"]
    ]


def _dialogue_runs(lines: list[str]) -> list[list[int]]:
    runs: list[list[int]] = []
    current: list[int] = []
    for line_number, line in enumerate(lines, 1):
        if DIALOGUE_RE.match(line):
            current.append(line_number)
            continue
        if current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def _dialogue_findings(
    lines: list[str],
    aliases: list[dict],
    rules: dict[str, dict],
) -> list[dict]:
    findings: list[dict] = []
    for run in _dialogue_runs(lines):
        if len(run) < 3:
            continue

        context_lines = list(range(max(1, run[0] - 2), run[0]))
        context_lines.extend(range(run[-1] + 1, min(len(lines), run[-1] + 2) + 1))
        participants: dict[tuple, dict] = {}
        for line_number in context_lines:
            if DIALOGUE_RE.match(lines[line_number - 1]):
                continue
            for candidate in _line_person_candidates(lines, line_number, aliases):
                participants[_candidate_key(candidate)] = candidate

        if len(participants) < 3:
            continue

        attributed_lines: list[int] = []
        for line_number in run:
            line = lines[line_number - 1]
            if not SPEECH_VERB_RE.search(line):
                continue
            if _line_person_candidates(lines, line_number, aliases):
                attributed_lines.append(line_number)

        if len(attributed_lines) >= len(run) - 1:
            continue

        findings.append(
            _finding(
                rules["SB-CTX-002"],
                line=run[0],
                sentence=" | ".join(lines[number - 1].strip() for number in run[:4]),
                confidence="MEDIUM",
                evidence={
                    "dialogue_lines": run,
                    "attributed_lines": attributed_lines,
                    "unattributed_lines": [number for number in run if number not in attributed_lines],
                    "participants": [
                        _candidate_payload(item) for item in list(participants.values())[:8]
                    ],
                },
            )
        )
    return findings


def _stanza_findings(
    entries: list[dict],
    fast_payload: dict,
    stanza_payload: dict | None,
    rules: dict[str, dict],
) -> list[dict]:
    if not stanza_payload or stanza_payload.get("status") not in {"REVIEW", "PASS"}:
        return []

    findings: list[dict] = []
    fast_ambiguous_by_sentence: dict[str, list[dict]] = {}
    for item in fast_payload.get("findings", []):
        if item.get("rule") != "SB-PRN-001":
            continue
        fast_ambiguous_by_sentence.setdefault(item["sentence"], []).append(item)

    for chain in stanza_payload.get("coreference_chains", []):
        mentions = chain.get("mentions", [])
        sentence_ids = [
            mention.get("sentence")
            for mention in mentions
            if isinstance(mention.get("sentence"), int)
        ]
        pronoun_mentions = [
            mention
            for mention in mentions
            if str(mention.get("text", "")).casefold() in PERSONAL_PRONOUNS
        ]

        for mention in pronoun_mentions:
            sentence_index = mention.get("sentence")
            if not isinstance(sentence_index, int) or sentence_index >= len(entries):
                continue
            sentence = entries[sentence_index]["sentence"]
            if sentence in fast_ambiguous_by_sentence:
                findings.append(
                    _finding(
                        rules["SB-CTX-004"],
                        line=entries[sentence_index]["line"],
                        sentence=sentence,
                        confidence="MEDIUM",
                        evidence={
                            "pronoun": mention.get("text"),
                            "representative_text": chain.get("representative_text"),
                            "chain_index": chain.get("index"),
                            "fast_rule": "SB-PRN-001",
                            "fast_candidates": fast_ambiguous_by_sentence[sentence][0]
                            .get("evidence", {})
                            .get("candidates", []),
                        },
                    )
                )

        if sentence_ids and max(sentence_ids) - min(sentence_ids) >= 2:
            anchor_index = max(sentence_ids)
            line = entries[anchor_index]["line"] if anchor_index < len(entries) else 1
            sentence = entries[anchor_index]["sentence"] if anchor_index < len(entries) else ""
            findings.append(
                _finding(
                    rules["SB-CTX-005"],
                    line=line,
                    sentence=sentence,
                    confidence="MEDIUM",
                    evidence={
                        "chain_index": chain.get("index"),
                        "representative_text": chain.get("representative_text"),
                        "sentence_span": [min(sentence_ids), max(sentence_ids)],
                        "mentions": mentions,
                    },
                )
            )

        zero_mentions = [
            mention
            for mention in mentions
            if mention.get("is_zero") is True or mention.get("text") == "_"
        ]
        for mention in zero_mentions:
            sentence_index = mention.get("sentence")
            if isinstance(sentence_index, int) and sentence_index < len(entries):
                line = entries[sentence_index]["line"]
                sentence = entries[sentence_index]["sentence"]
            else:
                line = 1
                sentence = ""
            findings.append(
                _finding(
                    rules["SB-CTX-006"],
                    line=line,
                    sentence=sentence,
                    confidence="LOW",
                    evidence={
                        "chain_index": chain.get("index"),
                        "representative_text": chain.get("representative_text"),
                        "zero_mention": mention,
                    },
                )
            )
    return findings


def analyze_lines(
    lines: list[str],
    rules: dict[str, dict] | None = None,
    character_profiles: list[dict] | None = None,
    stanza_payload: dict | None = None,
) -> dict:
    rules = rules if rules is not None else load_rules()
    profiles = character_profiles or []
    entries = _sentence_entries(lines)
    aliases = _profile_aliases(profiles)
    candidates_by_sentence = [
        _extract_candidates(entry, index, aliases) for index, entry in enumerate(entries)
    ]
    fast_payload = analyze_fast_pronouns("\n".join(lines), character_profiles=profiles)

    findings = []
    findings.extend(_long_distance_findings(entries, candidates_by_sentence, rules))
    findings.extend(_dialogue_findings(lines, aliases, rules))
    findings.extend(_zero_subject_findings(entries, candidates_by_sentence, rules))
    findings.extend(_stanza_findings(entries, fast_payload, stanza_payload, rules))

    deduped: list[dict] = []
    seen: set[tuple] = set()
    for item in findings:
        key = (item["rule"], item["line"], item["sentence"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    counts = Counter(item["severity"] for item in deduped)
    stanza_status = "NOT_RUN" if stanza_payload is None else stanza_payload.get("status", "UNKNOWN")
    return {
        "status": "REVIEW" if deduped else "PASS",
        "count": len(deduped),
        "counts": {"BLOCK": counts["BLOCK"], "REVIEW": counts["REVIEW"]},
        "stanza_status": stanza_status,
        "fast_pronoun_status": fast_payload.get("status"),
        "findings": deduped,
        "automatic_rewrite_allowed": False,
        "note": (
            "Contextual editorial evidence only. Long-distance links, dialogue speaker uncertainty, "
            "zero subjects and Stanza chains are REVIEW signals; none may silently rewrite prose."
        ),
    }


def analyze_text(
    text: str,
    rules: dict[str, dict] | None = None,
    character_profiles: list[dict] | None = None,
    stanza_payload: dict | None = None,
) -> dict:
    return analyze_lines(text.splitlines(), rules, character_profiles, stanza_payload)


def validate_fixture_corpus(
    rules_path: Path = DEFAULT_RULES,
    fixtures_path: Path = DEFAULT_FIXTURES,
) -> list[str]:
    errors = validate_regressions(rules_path)
    if errors:
        return errors

    rules = load_rules(rules_path)
    rule_ids = set(rules)
    fixture_doc = yaml.safe_load(fixtures_path.read_text(encoding="utf-8"))
    seen_ids: set[str] = set()
    exercised_rules: set[str] = set()
    guarded_rules: set[str] = set()

    for case in fixture_doc.get("cases", []):
        case_id = case["id"]
        if case_id in seen_ids:
            errors.append(f"SEMANTIC_COREF_FIXTURE duplicate case id {case_id}")
            continue
        seen_ids.add(case_id)

        expected = set(case.get("expected_rules", []))
        guards = set(case.get("guards_rules", []))
        if expected - rule_ids:
            errors.append(
                f"SEMANTIC_COREF_FIXTURE {case_id}: unknown expected rules "
                f"{sorted(expected - rule_ids)}"
            )
        if guards - rule_ids:
            errors.append(
                f"SEMANTIC_COREF_FIXTURE {case_id}: unknown guarded rules "
                f"{sorted(guards - rule_ids)}"
            )

        payload = analyze_text(
            case["text"],
            rules,
            case.get("characters", []),
            case.get("stanza_evidence"),
        )
        actual = {item["rule"] for item in payload["findings"]}
        if actual != expected:
            errors.append(
                f"SEMANTIC_COREF_FIXTURE {case_id}: expected={sorted(expected)} "
                f"actual={sorted(actual)} text={case['text']!r}"
            )
        expected_status = case.get("expected_status")
        if expected_status is not None and payload["status"] != expected_status:
            errors.append(
                f"SEMANTIC_COREF_FIXTURE {case_id}: expected status={expected_status} "
                f"actual={payload['status']}"
            )
        exercised_rules.update(expected)
        guarded_rules.update(guards)

    missing_exercise = sorted(rule_ids - exercised_rules)
    missing_guards = sorted(rule_ids - guarded_rules)
    if missing_exercise:
        errors.append(f"SEMANTIC_COREF_FIXTURE rules without bad coverage: {missing_exercise}")
    if missing_guards:
        errors.append(f"SEMANTIC_COREF_FIXTURE rules without false-positive guards: {missing_guards}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Contextual Russian semantic/coreference review.")
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--character-state", type=Path)
    parser.add_argument("--stanza-json", type=Path)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", dest="json_output", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        errors = validate_fixture_corpus(args.rules, args.fixtures)
        if errors:
            print("SEMANTIC_COREFERENCE_CORPUS: FAIL")
            for error in errors:
                print(f"- {error}")
            return 1
        fixture_doc = yaml.safe_load(args.fixtures.read_text(encoding="utf-8"))
        print(
            "SEMANTIC_COREFERENCE_CORPUS: PASS "
            f"cases={len(fixture_doc['cases'])} rules={len(load_rules(args.rules))}"
        )
        return 0

    if args.path is None:
        parser.error("path is required unless --self-test is used")

    stanza_payload = None
    if args.stanza_json:
        stanza_payload = json.loads(args.stanza_json.read_text(encoding="utf-8"))

    payload = analyze_text(
        args.path.read_text(encoding="utf-8"),
        load_rules(args.rules),
        load_character_profiles(args.character_state),
        stanza_payload,
    )
    payload["file"] = str(args.path)
    payload["character_state"] = str(args.character_state) if args.character_state else None
    payload["stanza_json"] = str(args.stanza_json) if args.stanza_json else None

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"SEMANTIC_COREFERENCE: {payload['status']} count={payload['count']} "
            f"stanza={payload['stanza_status']}"
        )
        for item in payload["findings"]:
            print(
                f"- {item['rule']} {item['severity']} line {item['line']}: "
                f"{item['message']} :: {item['sentence']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
