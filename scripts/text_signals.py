#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from razdel import tokenize

DIALOGUE_RE = re.compile(r"^\s*[—-]\s*(.+?)\s*$")
REVIEWER_PATTERNS = [
    re.compile(r"\b(это|вот это)\s+(хотя бы\s+)?честно\b", re.IGNORECASE),
    re.compile(r"\b(логично|разумно|нормальный ответ|вот теперь верю)\b", re.IGNORECASE),
]
FRAGMENTED_TIME_RE = re.compile(
    r"^\s*[—-]\s*[А-ЯЁа-яё]+[.!?]\s+(Сегодня|Завтра|Вечером|Утром|Потом)[.!?]\s*$"
)


def token_count(text: str) -> int:
    return sum(1 for token in tokenize(text) if re.search(r"\w", token.text, re.UNICODE))


def analyze_lines(lines: list[str]) -> list[dict]:
    findings: list[dict] = []
    short_run: list[tuple[int, str]] = []

    def flush_short_run() -> None:
        nonlocal short_run
        if len(short_run) >= 3:
            findings.append(
                {
                    "rule": "SB-DIA-001",
                    "severity": "REVIEW",
                    "line": short_run[0][0],
                    "message": (
                        f"{len(short_run)} consecutive short dialogue turns; "
                        "inspect for telegraph/AI ping-pong."
                    ),
                    "excerpt": " | ".join(text for _, text in short_run[:5]),
                }
            )
        short_run = []

    for number, line in enumerate(lines, 1):
        match = DIALOGUE_RE.match(line)
        if match:
            spoken = match.group(1)
            if token_count(spoken) <= 4:
                short_run.append((number, spoken))
            else:
                flush_short_run()

            if FRAGMENTED_TIME_RE.match(line):
                findings.append(
                    {
                        "rule": "SB-DIA-001",
                        "severity": "REVIEW",
                        "line": number,
                        "message": "Possible artificial sentence split before a simple time adverb.",
                        "excerpt": line.strip(),
                    }
                )

            for pattern in REVIEWER_PATTERNS:
                if pattern.search(spoken):
                    findings.append(
                        {
                            "rule": "SB-DIA-003",
                            "severity": "REVIEW",
                            "line": number,
                            "message": "Possible reviewer-agent response; verify character-owned function.",
                            "excerpt": line.strip(),
                        }
                    )
        else:
            flush_short_run()

    flush_short_run()
    return findings


def analyze_path(path: Path) -> dict:
    findings = analyze_lines(path.read_text(encoding="utf-8").splitlines())
    return {"file": str(path), "findings": findings, "count": len(findings)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Russian fiction dialogue/prose review signals.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", dest="json_output", action="store_true")
    args = parser.parse_args()

    payload = analyze_path(args.path)
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"TEXT_SIGNALS: {payload['count']} review finding(s)")
        for finding in payload["findings"]:
            print(
                f"- {finding['rule']} line {finding['line']}: {finding['message']} :: "
                f"{finding['excerpt']}"
            )

    # Signals intentionally do not fail CI: semantic editor decides whether each hit is a real defect.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
