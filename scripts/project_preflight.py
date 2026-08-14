#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_runtime(errors: list[str], runtime: dict) -> None:
    schema = json.loads((ROOT / "schemas/runtime.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(runtime), key=lambda e: list(e.path)):
        loc = ".".join(map(str, error.path)) or "<root>"
        fail(errors, f"RUNTIME_SCHEMA {loc}: {error.message}")


def scan_foreign_markers(errors: list[str], config: dict) -> None:
    markers = config.get("foreign_book_markers", [])
    roots = [ROOT / "canon", ROOT / "config", ROOT / "rules", ROOT / "scripts", ROOT / "schemas"]
    allow = {ROOT / "config/project.yaml", Path(__file__).resolve()}
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path in allow:
                continue
            if path.suffix.lower() not in {".md", ".yaml", ".yml", ".json", ".py"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in markers:
                if marker and marker in text:
                    fail(errors, f"FOREIGN_BOOK_MARKER {path.relative_to(ROOT)}: {marker}")


def main() -> int:
    errors: list[str] = []
    config = load_yaml(ROOT / "config/project.yaml")
    runtime = load_yaml(ROOT / "canon/runtime.yaml")
    system = load_yaml(ROOT / "canon/system.yaml")

    validate_runtime(errors, runtime)

    if runtime.get("book_id") != config.get("book_id"):
        fail(errors, "BOOK_ID mismatch between config and runtime")

    through = runtime["through_chapter"]
    approved = runtime["last_approved_chapter"]["number"]
    current = runtime["current_chapter"]["number"]

    if config["checks"].get("require_last_approved_equals_through") and approved != through:
        fail(errors, f"LAST_APPROVED {approved} != THROUGH_CHAPTER {through}")

    if config["checks"].get("require_current_equals_through_plus_one") and current != through + 1:
        fail(errors, f"CURRENT_CHAPTER {current} != THROUGH_CHAPTER+1 ({through + 1})")

    if config["checks"].get("require_system_runtime_sync"):
        new_cycles = [e for e in system.get("history", []) if e.get("event") == "NEW_CYCLE"]
        if not new_cycles:
            fail(errors, "SYSTEM history has no NEW_CYCLE event")
        else:
            latest = new_cycles[-1]
            if float(latest["quota_usd"]) != float(runtime["system"]["current_quota_usd"]):
                fail(errors, "SYSTEM quota != runtime quota")
            if latest["deadline"] != runtime["system"]["deadline"]:
                fail(errors, "SYSTEM deadline != runtime deadline")

    if config["checks"].get("block_foreign_book_dependencies"):
        scan_foreign_markers(errors, config)

    if errors:
        print("PROJECT_PREFLIGHT: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("PROJECT_PREFLIGHT: PASS")
    print(f"book={runtime['book_id']} through={through} current={current}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
