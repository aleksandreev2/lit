#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CHECK_COMMANDS = (
    ("project_preflight", ["scripts/project_preflight.py"]),
    ("provenance", ["scripts/provenance_check.py"]),
    ("regression_locks", ["scripts/regression_check.py"]),
    ("dependency_graph", ["scripts/dependency_graph.py", "config/dependency_graph.yaml"]),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_check(root: Path, args: list[str]) -> tuple[str, str]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = completed.stdout or "<no output>\n"
    return ("PASS" if completed.returncode == 0 else "BLOCK"), output


def _dependency_paths(root: Path, chapter: int) -> list[Path]:
    return [
        root / "canon/runtime.yaml",
        root / "canon/state.yaml",
        root / "canon/system.yaml",
        root / "canon/active_arc.yaml",
        root / "rules/regressions.yaml",
        root / "research/ledger.yaml",
        root / "config/dependency_graph.yaml",
        root / "sync/manifest.yaml",
        root / "current" / f"{chapter:03d}" / "manifest.yaml",
    ]


def _research_warnings(root: Path) -> list[str]:
    document = yaml.safe_load((root / "research/ledger.yaml").read_text(encoding="utf-8"))
    warnings: list[str] = []
    for record in document.get("records", []):
        if record.get("confidence") == "LOW":
            warnings.append(f"{record.get('id')}: LOW confidence")
        if record.get("freshness_class") in {"VOLATILE", "EVENT_DRIVEN"}:
            warnings.append(
                f"{record.get('id')}: {record.get('freshness_class')} requires freshness attention"
            )
    return warnings


def generate_report(root: Path, output_dir: Path, revision: str) -> dict:
    root = root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True)

    runtime = yaml.safe_load((root / "canon/runtime.yaml").read_text(encoding="utf-8"))
    chapter = runtime["current_chapter"]["number"]
    stage = runtime["current_chapter"]["status"]

    checks: list[dict] = []
    for check_id, command in CHECK_COMMANDS:
        status, output = _run_check(root, command)
        log_name = f"logs/{check_id}.log"
        (output_dir / log_name).write_text(output, encoding="utf-8")
        checks.append({"id": check_id, "status": status, "log": log_name})

    readiness_log = "logs/current_chapter_readiness.log"
    if stage == "NOT_STARTED":
        readiness_status = "REVIEW"
        readiness_text = (
            f"current chapter {chapter} is NOT_STARTED; no chapter prose, semantic QA, or freeze is claimed.\n"
        )
    else:
        readiness_status = "REVIEW"
        readiness_text = (
            f"current chapter {chapter} is {stage}; semantic/editorial evidence must be inspected separately.\n"
        )
    (output_dir / readiness_log).write_text(readiness_text, encoding="utf-8")
    checks.append(
        {"id": "current_chapter_readiness", "status": readiness_status, "log": readiness_log}
    )

    dependency_hashes: dict[str, str] = {}
    for path in _dependency_paths(root, chapter):
        if path.is_file():
            dependency_hashes[str(path.relative_to(root))] = sha256(path)

    freeze_manifest_path = root / "current" / f"{chapter:03d}" / "freeze.json"
    if freeze_manifest_path.is_file():
        freeze = {
            "status": "BLOCKED",
            "manifest_path": str(freeze_manifest_path.relative_to(root)),
        }
    else:
        freeze = {"status": "NOT_AVAILABLE", "manifest_path": None}

    generated_audits = [
        {
            "id": "chapter_qa_artifacts",
            "status": "NOT_RUN",
            "note": "No explicit current chapter source was supplied to the artifact generator.",
        },
        {
            "id": "drive_sync",
            "status": "REVIEW",
            "note": (
                "Sync mappings are MANUAL_ONLY; CI has no live Drive revision observation and performs no writes."
            ),
        },
        {
            "id": "pdf_provenance",
            "status": "NOT_RUN",
            "note": "No frozen source/PDF provenance record exists for the current NOT_STARTED chapter.",
        },
    ]

    counts = Counter(item["status"] for item in checks)
    summary = {
        "book_id": runtime["book_id"],
        "schema_version": 1,
        "revision": revision,
        "current_chapter": chapter,
        "current_stage": stage,
        "checks": checks,
        "counts": {
            "PASS": counts.get("PASS", 0),
            "BLOCK": counts.get("BLOCK", 0),
            "REVIEW": counts.get("REVIEW", 0),
        },
        "dependency_hashes": dependency_hashes,
        "generated_audits": generated_audits,
        "stale_evidence": [],
        "research_warnings": _research_warnings(root),
        "freeze": freeze,
        "semantic_review_status": "NOT_RUN",
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    manifest = {
        "schema_version": 1,
        "revision": revision,
        "files": [
            {
                "path": str(path.relative_to(output_dir)),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def validate_summary(summary_path: Path) -> list[str]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/qa_report.schema.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for error in Draft202012Validator(schema).iter_errors(summary):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"QA_REPORT_SCHEMA {location}: {error.message}")
    actual_counts = Counter(item["status"] for item in summary.get("checks", []))
    for status in ("PASS", "BLOCK", "REVIEW"):
        if summary.get("counts", {}).get(status) != actual_counts.get(status, 0):
            errors.append(f"QA_REPORT_COUNT {status}: summary count does not match checks")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one compact reproducible Production Engine QA report artifact.")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()

    generate_report(args.root, args.output_dir, args.revision)
    errors = validate_summary(args.output_dir / "summary.json")
    if errors:
        print("QA_REPORT: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    summary = json.loads((args.output_dir / "summary.json").read_text(encoding="utf-8"))
    print(
        "QA_REPORT: PASS "
        f"PASS={summary['counts']['PASS']} BLOCK={summary['counts']['BLOCK']} "
        f"REVIEW={summary['counts']['REVIEW']} freeze={summary['freeze']['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
