#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a chapter freeze manifest against exact file hashes.")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    base = args.manifest.parent
    errors: list[str] = []

    for key, item in manifest.get("files", {}).items():
        path = (base / item["path"]).resolve()
        expected = item["sha256"]
        if not path.exists():
            errors.append(f"{key}: missing {path}")
            continue
        actual = sha256(path)
        if actual != expected:
            errors.append(f"{key}: sha mismatch expected={expected} actual={actual}")

    gates = manifest.get("gates", {})
    for gate, status in gates.items():
        if status != "PASS":
            errors.append(f"gate {gate} is {status}, expected PASS")

    if errors:
        print("FREEZE_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("FREEZE_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
