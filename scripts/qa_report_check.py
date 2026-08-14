#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from qa_report import validate_summary


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_report(report_dir: Path) -> list[str]:
    report_dir = report_dir.resolve()
    summary_path = report_dir / "summary.json"
    manifest_path = report_dir / "manifest.json"
    errors: list[str] = []
    if not summary_path.is_file():
        errors.append("QA_REPORT_FILE missing summary.json")
    else:
        errors.extend(validate_summary(summary_path))
    if not manifest_path.is_file():
        errors.append("QA_REPORT_FILE missing manifest.json")
        return errors

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for item in manifest.get("files", []):
        relative = item.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append("QA_REPORT_MANIFEST invalid file path")
            continue
        if relative in seen:
            errors.append(f"QA_REPORT_MANIFEST duplicate path: {relative}")
            continue
        seen.add(relative)
        path = (report_dir / relative).resolve()
        if not path.is_relative_to(report_dir):
            errors.append(f"QA_REPORT_MANIFEST path escapes report: {relative}")
            continue
        if not path.is_file():
            errors.append(f"QA_REPORT_MANIFEST missing file: {relative}")
            continue
        actual_hash = sha256(path)
        if actual_hash != item.get("sha256"):
            errors.append(
                f"QA_REPORT_MANIFEST hash mismatch {relative}: "
                f"expected={item.get('sha256')} actual={actual_hash}"
            )
        if path.stat().st_size != item.get("bytes"):
            errors.append(f"QA_REPORT_MANIFEST byte-size mismatch: {relative}")

    actual_files = {
        str(path.relative_to(report_dir))
        for path in report_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_files != seen:
        missing_from_manifest = sorted(actual_files - seen)
        extra_in_manifest = sorted(seen - actual_files)
        if missing_from_manifest:
            errors.append(
                "QA_REPORT_MANIFEST unlisted files: " + ",".join(missing_from_manifest)
            )
        if extra_in_manifest:
            errors.append(
                "QA_REPORT_MANIFEST listed missing files: " + ",".join(extra_in_manifest)
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify QA report schema, file inventory and hashes.")
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()

    errors = validate_report(args.report_dir)
    if errors:
        print("QA_REPORT_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("QA_REPORT_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
