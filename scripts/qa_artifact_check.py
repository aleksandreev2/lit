#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(manifest_path: Path) -> list[str]:
    manifest_path = manifest_path.resolve()
    base = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "schemas/qa_artifact_manifest.schema.json").read_text(encoding="utf-8")
    )
    errors: list[str] = []
    for error in Draft202012Validator(schema).iter_errors(manifest):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"QA_ARTIFACT_SCHEMA {location}: {error.message}")
    if errors:
        return errors

    source_path = (base / manifest["source"]["path"]).resolve()
    if not source_path.exists():
        errors.append(f"QA_ARTIFACT_SOURCE missing: {source_path}")
    else:
        actual_source = sha256(source_path)
        if actual_source != manifest["source"]["sha256"]:
            errors.append(
                "QA_ARTIFACT_SOURCE hash mismatch: "
                f"expected={manifest['source']['sha256']} actual={actual_source}"
            )

    seen_paths: set[str] = set()
    for artifact in manifest["artifacts"]:
        artifact_path = artifact["path"]
        if artifact_path in seen_paths:
            errors.append(f"QA_ARTIFACT duplicate path: {artifact_path}")
            continue
        seen_paths.add(artifact_path)
        path = (base / artifact_path).resolve()
        if not path.is_relative_to(base):
            errors.append(f"QA_ARTIFACT escapes output directory: {artifact_path}")
            continue
        if not path.exists():
            errors.append(f"QA_ARTIFACT missing: {artifact_path}")
            continue
        actual_hash = sha256(path)
        if actual_hash != artifact["sha256"]:
            errors.append(
                f"QA_ARTIFACT hash mismatch {artifact_path}: "
                f"expected={artifact['sha256']} actual={actual_hash}"
            )
        actual_bytes = path.stat().st_size
        if actual_bytes != artifact["bytes"]:
            errors.append(
                f"QA_ARTIFACT byte-size mismatch {artifact_path}: "
                f"expected={artifact['bytes']} actual={actual_bytes}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify generated QA artifact schema and hashes.")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    errors = validate_manifest(args.manifest)
    if errors:
        print("QA_ARTIFACT_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("QA_ARTIFACT_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
