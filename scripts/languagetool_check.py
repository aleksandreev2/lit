#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional local Russian LanguageTool review adapter.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--language", default="ru-RU")
    parser.add_argument("--json", dest="json_output", action="store_true")
    args = parser.parse_args()

    try:
        import language_tool_python
    except ImportError as exc:
        raise SystemExit("Install optional grammar dependencies first: pip install '.[grammar]'") from exc

    text = args.path.read_text(encoding="utf-8")
    tool = language_tool_python.LanguageTool(args.language)
    try:
        matches = tool.check(text)
    finally:
        tool.close()

    findings = []
    for match in matches:
        findings.append(
            {
                "rule_id": getattr(match, "rule_id", None),
                "message": match.message,
                "offset": match.offset,
                "error_length": match.error_length,
                "replacements": list(match.replacements[:5]),
            }
        )

    if args.json_output:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        for finding in findings:
            print(
                f"{finding['rule_id']}: offset={finding['offset']} len={finding['error_length']} "
                f"{finding['message']} -> {finding['replacements']}"
            )
        print(f"LANGUAGETOOL_REVIEW: {len(findings)} finding(s)")

    # LanguageTool is a REVIEW source, not an automatic FAIL gate for fiction.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
