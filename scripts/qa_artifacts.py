#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import yaml
from pronoun_coreference import analyze_lines as analyze_pronoun_lines
from pronoun_coreference import load_character_profiles as load_pronoun_profiles
from pronoun_coreference import load_rules as load_pronoun_rules
from razdel import sentenize, tokenize
from russian_naturalness import analyze_lines as analyze_naturalness_lines
from russian_naturalness import load_rules as load_naturalness_rules
from text_signals import DIALOGUE_RE, token_count
from text_signals import analyze_lines as analyze_text_signals

ROOT = Path(__file__).resolve().parents[1]
ENTITY_RE = re.compile(r"(?<![.!?]\s)\b(?:[А-ЯЁ][а-яё]{2,}|[A-Z][A-Za-z0-9&._-]{2,})(?:\s+[А-ЯЁA-Z][\w.-]{2,}){0,2}\b")
NUMBER_RE = re.compile(
    r"(?<!\w)(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d+(?:[.,]\d+)?)"
    r"(?:\s?(?:₽|\$|€|USD|EUR|RUB|BTC|ETH|%|руб(?:лей|ля|ль)?|доллар(?:ов|а)?|евро))?",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s)\]}>,]+", re.IGNORECASE)
KNOWLEDGE_RE = re.compile(
    r"\b(знаю|знал|знала|слышал|слышала|помню|видел|видела|узнал|узнала|"
    r"мне\s+сказали|мне\s+говорили|я\s+думаю|я\s+понял|я\s+поняла|я\s+догадался|я\s+догадалась)\b",
    re.IGNORECASE,
)
COMEBACK_RE = re.compile(r"\b(поэтому|вот\s+именно|тем\s+более)\b", re.IGNORECASE)
QUESTION_CUE_RE = re.compile(
    r"\b(почему|зачем|откуда|как\s+так|что\s+значит|сколько|когда|кто\s+такой|кто\s+такая)\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"^[\w-]+$", re.UNICODE)
STOPWORDS = {
    "это",
    "что",
    "как",
    "для",
    "его",
    "она",
    "они",
    "был",
    "была",
    "были",
    "есть",
    "так",
    "уже",
    "только",
    "если",
    "когда",
    "потом",
    "сейчас",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dialogue_turns(lines: list[str]) -> list[dict]:
    turns: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        match = DIALOGUE_RE.match(line)
        if match:
            turns.append(
                {
                    "turn": len(turns) + 1,
                    "line": line_number,
                    "text": match.group(1),
                    "token_count": token_count(match.group(1)),
                }
            )
    return turns


def question_audit(turns: list[dict]) -> list[dict]:
    findings: list[dict] = []
    for index, turn in enumerate(turns):
        if "?" not in turn["text"]:
            continue
        next_turn = turns[index + 1] if index + 1 < len(turns) else None
        cue = bool(QUESTION_CUE_RE.search(turn["text"]))
        long_answer = bool(next_turn and next_turn["token_count"] >= 12)
        findings.append(
            {
                "line": turn["line"],
                "question": turn["text"],
                "next_dialogue_line": next_turn["line"] if next_turn else None,
                "next_dialogue_tokens": next_turn["token_count"] if next_turn else None,
                "convenient_exposition_candidate": cue and long_answer,
                "detection": "HEURISTIC",
                "status": "REVIEW",
            }
        )
    return findings


def turn_windows(turns: list[dict], radius: int = 1) -> list[dict]:
    windows: list[dict] = []
    for index, turn in enumerate(turns):
        start = max(0, index - radius)
        end = min(len(turns), index + radius + 1)
        windows.append({"focus_turn": turn["turn"], "turns": turns[start:end]})
    return windows


def repeated_phrases(text: str) -> list[dict]:
    counts: Counter[tuple[str, ...]] = Counter()
    for sentence in sentenize(text):
        words = [
            token.text.casefold()
            for token in tokenize(sentence.text)
            if WORD_RE.match(token.text) and any(char.isalpha() for char in token.text)
        ]
        for size in (3, 4, 5):
            for index in range(max(0, len(words) - size + 1)):
                phrase = tuple(words[index : index + size])
                if sum(word in STOPWORDS for word in phrase) >= size - 1:
                    continue
                counts[phrase] += 1
    return [
        {"phrase": " ".join(phrase), "count": count, "detection": "DETERMINISTIC"}
        for phrase, count in counts.most_common()
        if count >= 2
    ][:50]


def entity_candidates(lines: list[str]) -> list[dict]:
    candidates: dict[str, dict] = {}
    for line_number, line in enumerate(lines, 1):
        for match in ENTITY_RE.finditer(line):
            value = match.group(0).strip()
            if len(value) < 3:
                continue
            item = candidates.setdefault(
                value,
                {
                    "text": value,
                    "lines": [],
                    "detection": "HEURISTIC",
                    "confidence": "LOW",
                    "status": "REVIEW",
                },
            )
            item["lines"].append(line_number)
    for item in candidates.values():
        item["lines"] = sorted(set(item["lines"]))
    return sorted(candidates.values(), key=lambda item: (item["lines"][0], item["text"]))


def numeric_mentions(lines: list[str]) -> list[dict]:
    mentions: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        for match in NUMBER_RE.finditer(line):
            value = match.group(0).strip()
            mentions.append(
                {
                    "line": line_number,
                    "text": value,
                    "context": line.strip(),
                    "money_or_rate": bool(
                        re.search(
                            r"₽|\$|€|USD|EUR|RUB|BTC|ETH|%|руб|доллар|евро",
                            value,
                            re.IGNORECASE,
                        )
                    ),
                    "status": "REVIEW",
                }
            )
    return mentions


def knowledge_candidates(lines: list[str]) -> list[dict]:
    return [
        {
            "line": number,
            "text": line.strip(),
            "detection": "HEURISTIC",
            "status": "REVIEW",
            "reason": "knowledge/belief acquisition language",
        }
        for number, line in enumerate(lines, 1)
        if KNOWLEDGE_RE.search(line)
    ]


def comeback_candidates(lines: list[str]) -> list[dict]:
    return [
        {
            "line": number,
            "text": line.strip(),
            "marker": match.group(0),
            "detection": "HEURISTIC",
            "status": "REVIEW",
        }
        for number, line in enumerate(lines, 1)
        if (match := COMEBACK_RE.search(line))
    ]


def research_candidates(
    lines: list[str], entities: list[dict], numbers: list[dict]
) -> list[dict]:
    candidates: list[dict] = []
    for number in numbers:
        if number["money_or_rate"]:
            candidates.append(
                {
                    "line": number["line"],
                    "text": number["text"],
                    "reason": "money/rate/percentage claim may be date-sensitive",
                    "status": "REVIEW",
                }
            )
    for line_number, line in enumerate(lines, 1):
        for match in URL_RE.finditer(line):
            candidates.append(
                {
                    "line": line_number,
                    "text": match.group(0),
                    "reason": "explicit external source/reference",
                    "status": "REVIEW",
                }
            )
    for entity in entities:
        if re.search(r"[A-Za-z]", entity["text"]):
            candidates.append(
                {
                    "line": entity["lines"][0],
                    "text": entity["text"],
                    "reason": "Latin-script entity/brand candidate",
                    "status": "REVIEW",
                }
            )
    return candidates


def continuity_audit(
    entities: list[dict], parent_runtime: Path | None, character_state: Path | None
) -> dict:
    known_names: set[str] = set()
    character_state_sha = None
    if character_state:
        state_doc = yaml.safe_load(character_state.read_text(encoding="utf-8"))
        known_names = {
            item["display_name"]
            for item in state_doc.get("characters", [])
            if item.get("display_name")
        }
        character_state_sha = sha256(character_state)

    mentioned_names = {item["text"] for item in entities}
    return {
        "status": "REVIEW",
        "detection": "HEURISTIC",
        "parent_runtime_sha256": sha256(parent_runtime) if parent_runtime else None,
        "character_state_sha256": character_state_sha,
        "known_character_mentions": sorted(mentioned_names & known_names),
        "unresolved_entity_mentions": sorted(mentioned_names - known_names),
        "automatic_canon_delta": False,
        "note": "Candidate report only; semantic continuity review remains mandatory.",
    }


def generate_artifacts(
    source: Path,
    output_dir: Path,
    *,
    parent_runtime: Path | None = None,
    character_state: Path | None = None,
    regression_rules: Path | None = None,
    pronoun_rules: Path | None = None,
) -> dict:
    source = source.resolve()
    output_dir = output_dir.resolve()
    regression_rules = (regression_rules or ROOT / "rules/regressions.yaml").resolve()
    pronoun_rules = (pronoun_rules or ROOT / "rules/pronoun_regressions.yaml").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    lines = text.splitlines()
    turns = dialogue_turns(lines)
    dialogue_lines = [line for line in lines if DIALOGUE_RE.match(line)]
    narration_lines = [line for line in lines if line.strip() and not DIALOGUE_RE.match(line)]

    entities = entity_candidates(lines)
    numbers = numeric_mentions(lines)
    questions = question_audit(turns)
    signals = analyze_text_signals(lines)
    naturalness = analyze_naturalness_lines(lines, load_naturalness_rules(regression_rules))
    pronouns = analyze_pronoun_lines(
        lines,
        load_pronoun_rules(pronoun_rules),
        load_pronoun_profiles(character_state),
    )

    (output_dir / "dialogue_only.txt").write_text("\n".join(dialogue_lines) + "\n", encoding="utf-8")
    (output_dir / "narration_only.txt").write_text("\n".join(narration_lines) + "\n", encoding="utf-8")

    payloads = {
        "question_audit.json": {"questions": questions, "count": len(questions)},
        "dialogue_windows.json": {"windows": turn_windows(turns), "count": len(turns)},
        "repeated_phrases.json": {"phrases": repeated_phrases(text)},
        "text_signals.json": {"findings": signals, "count": len(signals)},
        "russian_naturalness.json": naturalness,
        "pronoun_coreference.json": pronouns,
        "comeback_signals.json": {"candidates": comeback_candidates(lines)},
        "entity_mentions.json": {"candidates": entities},
        "knowledge_claim_candidates.json": {"candidates": knowledge_candidates(lines)},
        "numeric_mentions.json": {"mentions": numbers},
        "research_candidates.json": {
            "candidates": research_candidates(lines, entities, numbers),
            "automatic_research_pass": False,
        },
        "continuity_audit.json": continuity_audit(entities, parent_runtime, character_state),
        "chapter_delta_candidate.json": {
            "status": "REVIEW",
            "source_sha256": sha256(source),
            "automatic_promotion_allowed": False,
            "fact_changes": [],
            "knowledge_changes": [],
            "state_changes": [],
            "note": "Populate only after semantic review; candidate extraction never promotes canon.",
        },
    }
    for filename, payload in payloads.items():
        write_json(output_dir / filename, payload)

    artifact_names = ["dialogue_only.txt", "narration_only.txt", *payloads.keys()]
    artifacts = [
        {
            "path": name,
            "sha256": sha256(output_dir / name),
            "bytes": (output_dir / name).stat().st_size,
        }
        for name in sorted(artifact_names)
    ]
    manifest = {
        "schema_version": 1,
        "source": {
            "path": os.path.relpath(source, output_dir),
            "sha256": sha256(source),
        },
        "regression_rules": {
            "path": os.path.relpath(regression_rules, output_dir),
            "sha256": sha256(regression_rules),
        },
        "pronoun_rules": {
            "path": os.path.relpath(pronoun_rules, output_dir),
            "sha256": sha256(pronoun_rules),
        },
        "parent_runtime_sha256": sha256(parent_runtime) if parent_runtime else None,
        "character_state_sha256": sha256(character_state) if character_state else None,
        "artifacts": artifacts,
    }
    write_json(output_dir / "artifact_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic editor-support artifacts from a chapter candidate.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--parent-runtime", type=Path)
    parser.add_argument("--character-state", type=Path)
    parser.add_argument("--regression-rules", type=Path, default=ROOT / "rules/regressions.yaml")
    parser.add_argument(
        "--pronoun-rules",
        type=Path,
        default=ROOT / "rules/pronoun_regressions.yaml",
    )
    args = parser.parse_args()

    manifest = generate_artifacts(
        args.source,
        args.output_dir,
        parent_runtime=args.parent_runtime,
        character_state=args.character_state,
        regression_rules=args.regression_rules,
        pronoun_rules=args.pronoun_rules,
    )
    print(
        f"QA_ARTIFACTS: PASS count={len(manifest['artifacts'])} "
        f"source_sha256={manifest['source']['sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
