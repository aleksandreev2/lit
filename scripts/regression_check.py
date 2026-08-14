#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRIES = (
    ROOT / "rules/regressions.yaml",
    ROOT / "rules/pronoun_regressions.yaml",
)


def validate_regressions(path: Path, root: Path = ROOT) -> list[str]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = json.loads((root / "schemas/regressions.schema.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for error in Draft202012Validator(schema).iter_errors(document):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"REGRESSION_SCHEMA {location}: {error.message}")
    if errors:
        return errors

    rules = document["rules"]
    rule_by_id = {rule["id"]: rule for rule in rules}
    if len(rule_by_id) != len(rules):
        errors.append("REGRESSION_ID duplicate stable rule ID")

    for rule in rules:
        rule_id = rule["id"]
        fixture = rule["fixture_test_path"]
        if rule["detection_type"] in {"DETERMINISTIC", "HEURISTIC"}:
            fixture_path = (root / fixture).resolve()
            if not fixture_path.is_relative_to(root.resolve()) or not fixture_path.is_file():
                errors.append(f"REGRESSION_FIXTURE {rule_id}: missing fixture/test file {fixture}")

        if rule["owner_family"] == "russian_naturalness" and not rule.get("matcher"):
            errors.append(f"REGRESSION_MATCHER {rule_id}: naturalness rule requires matcher")

        superseded_by = rule["superseded_by"]
        if superseded_by:
            if superseded_by == rule_id:
                errors.append(f"REGRESSION_SUPERSESSION {rule_id}: cannot supersede itself")
            elif superseded_by not in rule_by_id:
                errors.append(
                    f"REGRESSION_SUPERSESSION {rule_id}: unknown rule {superseded_by}"
                )
    return errors


def validate_regression_registries(paths: tuple[Path, ...] = DEFAULT_REGISTRIES) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, Path] = {}
    for path in paths:
        errors.extend(validate_regressions(path))
        if not path.is_file():
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for rule in document.get("rules", []):
            rule_id = rule.get("id")
            if not rule_id:
                continue
            if rule_id in seen_ids:
                errors.append(
                    f"REGRESSION_ID {rule_id}: duplicated across {seen_ids[rule_id]} and {path}"
                )
            else:
                seen_ids[rule_id] = path
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate regression-lock metadata and fixture coverage.")
    parser.add_argument("path", type=Path, nargs="?")
    args = parser.parse_args()

    errors = (
        validate_regressions(args.path)
        if args.path is not None
        else validate_regression_registries()
    )
    if errors:
        print("REGRESSION_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("REGRESSION_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
