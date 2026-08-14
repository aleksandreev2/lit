from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_schema() -> None:
    runtime = yaml.safe_load((ROOT / "canon/runtime.yaml").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/runtime.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(runtime))
    assert not errors, "\n".join(error.message for error in errors)


def test_chapter_sequence() -> None:
    runtime = yaml.safe_load((ROOT / "canon/runtime.yaml").read_text(encoding="utf-8"))
    assert runtime["last_approved_chapter"]["number"] == runtime["through_chapter"]
    assert runtime["current_chapter"]["number"] == runtime["through_chapter"] + 1


def test_system_runtime_sync() -> None:
    runtime = yaml.safe_load((ROOT / "canon/runtime.yaml").read_text(encoding="utf-8"))
    system = yaml.safe_load((ROOT / "canon/system.yaml").read_text(encoding="utf-8"))
    cycles = [event for event in system["history"] if event["event"] == "NEW_CYCLE"]
    latest = cycles[-1]
    assert float(latest["quota_usd"]) == float(runtime["system"]["current_quota_usd"])
    assert latest["deadline"] == runtime["system"]["deadline"]
