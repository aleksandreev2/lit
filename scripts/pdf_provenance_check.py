#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freeze_manifest import verify_manifest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_inside(base: Path, value: str) -> Path | None:
    path = (base / value).resolve()
    if not path.is_relative_to(base.resolve()):
        return None
    return path


def _verify_binding(base: Path, label: str, binding: dict) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    path = _resolve_inside(base, binding["path"])
    if path is None:
        return None, [f"PDF_PROVENANCE_PATH {label}: escapes provenance directory"]
    if not path.is_file():
        return path, [f"PDF_PROVENANCE_FILE {label}: missing {binding['path']}"]
    actual = sha256(path)
    if actual != binding["sha256"]:
        errors.append(
            f"PDF_PROVENANCE_HASH {label}: expected={binding['sha256']} actual={actual}"
        )
    return path, errors


def validate_record(record_path: Path) -> list[str]:
    record_path = record_path.resolve()
    base = record_path.parent
    record = json.loads(record_path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/pdf_provenance.schema.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for error in Draft202012Validator(schema).iter_errors(record):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"PDF_PROVENANCE_SCHEMA {location}: {error.message}")
    if errors:
        return errors

    resolved: dict[str, Path | None] = {}
    for label in ("frozen_source", "freeze_manifest", "pdf"):
        path, binding_errors = _verify_binding(base, label, record[label])
        resolved[label] = path
        errors.extend(binding_errors)

    for gate_name in ("technical_preflight", "visual_qa"):
        gate = record[gate_name]
        if gate["status"] == "PASS":
            evidence_path, binding_errors = _verify_binding(base, gate_name, gate["evidence"])
            resolved[gate_name] = evidence_path
            errors.extend(binding_errors)
        elif gate["evidence"] is not None:
            errors.append(f"PDF_PROVENANCE_GATE {gate_name}: non-PASS gate must not carry PASS evidence")

    freeze_path = resolved.get("freeze_manifest")
    source_path = resolved.get("frozen_source")
    if freeze_path and freeze_path.is_file():
        freeze_errors, _ = verify_manifest(freeze_path)
        errors.extend(f"PDF_FREEZE {error}" for error in freeze_errors)
        if not freeze_errors and source_path and source_path.is_file():
            freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
            chapter_bindings = [
                item for item in freeze["inputs"] if item["role"] == "CHAPTER_TEXT"
            ]
            if len(chapter_bindings) != 1:
                errors.append("PDF_FREEZE expected exactly one CHAPTER_TEXT binding")
            elif chapter_bindings[0]["sha256"] != record["frozen_source"]["sha256"]:
                errors.append("PDF_FREEZE frozen source hash does not match freeze CHAPTER_TEXT")

    both_pass = (
        record["technical_preflight"]["status"] == "PASS"
        and record["visual_qa"]["status"] == "PASS"
    )
    if record["deliverable_status"] == "READY" and not both_pass:
        errors.append("PDF_DELIVERABLE READY requires technical preflight and visual QA PASS")
    if record["deliverable_status"] == "BLOCKED" and both_pass:
        errors.append("PDF_DELIVERABLE both evidence gates PASS but deliverable remains BLOCKED")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PDF provenance and release evidence.")
    parser.add_argument("record", type=Path)
    args = parser.parse_args()

    errors = validate_record(args.record)
    if errors:
        print("PDF_PROVENANCE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PDF_PROVENANCE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
