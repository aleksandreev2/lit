#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml
from atomic_transaction import FileOperation, apply_failure_atomic
from freeze_manifest import verify_manifest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(data: dict, schema_name: str, label: str) -> list[str]:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"{label}_SCHEMA {location}: {error.message}")
    return errors


def resolve_package_path(package_dir: Path, value: str) -> Path:
    path = (package_dir / value).resolve()
    if not path.is_relative_to(package_dir.resolve()):
        raise ValueError(f"promotion package path escapes package directory: {value}")
    return path


def _chapter_hash_from_freeze(freeze: dict) -> str | None:
    for item in freeze.get("inputs", []):
        if item.get("role") == "CHAPTER_TEXT":
            return item.get("sha256")
    return None


def validate_promotion(root: Path, plan_path: Path) -> tuple[list[str], dict]:
    root = root.resolve()
    plan_path = plan_path.resolve()
    package_dir = plan_path.parent
    errors: list[str] = []

    plan = load_json(plan_path)
    errors.extend(schema_errors(plan, "promotion_plan.schema.json", "PROMOTION_PLAN"))
    if errors:
        return errors, {}

    chapter = plan["chapter"]
    paths = {
        key: resolve_package_path(package_dir, plan[key])
        for key in (
            "freeze_manifest",
            "author_approval",
            "chapter_delta",
            "candidate_runtime",
            "candidate_state",
            "candidate_system",
            "candidate_active_arc",
            "next_manifest",
        )
    }
    for label, path in paths.items():
        if not path.is_file():
            errors.append(f"PROMOTION_INPUT {label}: missing {path}")
    if errors:
        return errors, {}

    current_manifest_path = root / "current" / f"{chapter:03d}" / "manifest.yaml"
    if not current_manifest_path.is_file():
        errors.append(f"PROMOTION_CURRENT missing: {current_manifest_path}")
        return errors, {}

    runtime_path = root / "canon/runtime.yaml"
    state_path = root / "canon/state.yaml"
    system_path = root / "canon/system.yaml"
    active_arc_path = root / "canon/active_arc.yaml"
    for path in (runtime_path, state_path, system_path, active_arc_path):
        if not path.is_file():
            errors.append(f"PROMOTION_AUTHORITY missing: {path}")
    if errors:
        return errors, {}

    runtime = load_yaml(runtime_path)
    current_manifest = load_yaml(current_manifest_path)
    approval = load_json(paths["author_approval"])
    delta = load_json(paths["chapter_delta"])
    freeze = load_json(paths["freeze_manifest"])
    candidate_runtime = load_yaml(paths["candidate_runtime"])
    candidate_state = load_yaml(paths["candidate_state"])
    candidate_system = load_yaml(paths["candidate_system"])
    candidate_active_arc = load_yaml(paths["candidate_active_arc"])
    next_manifest = load_yaml(paths["next_manifest"])

    schema_inputs = (
        (current_manifest, "chapter_manifest.schema.json", "CURRENT_MANIFEST"),
        (approval, "author_approval_evidence.schema.json", "AUTHOR_APPROVAL"),
        (delta, "chapter_delta.schema.json", "CHAPTER_DELTA"),
        (candidate_runtime, "runtime.schema.json", "CANDIDATE_RUNTIME"),
        (candidate_state, "structured_state.schema.json", "CANDIDATE_STATE"),
        (candidate_system, "system.schema.json", "CANDIDATE_SYSTEM"),
        (candidate_active_arc, "active_arc.schema.json", "CANDIDATE_ACTIVE_ARC"),
        (next_manifest, "chapter_manifest.schema.json", "NEXT_MANIFEST"),
    )
    for data, schema_name, label in schema_inputs:
        errors.extend(schema_errors(data, schema_name, label))

    freeze_errors, _ = verify_manifest(paths["freeze_manifest"])
    errors.extend(f"PROMOTION_FREEZE {error}" for error in freeze_errors)
    if errors:
        return errors, {}

    freeze_sha = sha256(paths["freeze_manifest"])
    chapter_sha = _chapter_hash_from_freeze(freeze)

    if runtime.get("current_chapter", {}).get("number") != chapter:
        errors.append("PROMOTION_RUNTIME current chapter does not match plan chapter")
    if runtime.get("current_chapter", {}).get("status") != "AUTHOR_APPROVED":
        errors.append("PROMOTION_RUNTIME current status must be AUTHOR_APPROVED")
    if current_manifest.get("chapter") != chapter or current_manifest.get("stage") != "AUTHOR_APPROVED":
        errors.append("PROMOTION_CURRENT manifest must be AUTHOR_APPROVED for plan chapter")

    freeze_state = current_manifest.get("freeze", {})
    if freeze_state.get("chapter_sha256") != chapter_sha:
        errors.append("PROMOTION_CURRENT chapter hash does not match verified freeze")
    if freeze_state.get("author_approval_evidence_id") != approval.get("id"):
        errors.append("PROMOTION_APPROVAL manifest evidence id does not match approval artifact")

    if approval.get("chapter") != chapter:
        errors.append("PROMOTION_APPROVAL chapter mismatch")
    if approval.get("freeze_manifest_sha256") != freeze_sha:
        errors.append("PROMOTION_APPROVAL freeze manifest hash mismatch")
    if approval.get("chapter_sha256") != chapter_sha:
        errors.append("PROMOTION_APPROVAL chapter hash mismatch")

    if delta.get("chapter") != chapter or delta.get("source_sha256") != chapter_sha:
        errors.append("PROMOTION_DELTA must bind the exact frozen chapter hash")

    next_chapter = chapter + 1
    if candidate_runtime.get("through_chapter") != chapter:
        errors.append("PROMOTION_RUNTIME candidate through_chapter must equal promoted chapter")
    if candidate_runtime.get("last_approved_chapter", {}).get("number") != chapter:
        errors.append("PROMOTION_RUNTIME candidate last_approved_chapter must equal promoted chapter")
    if candidate_runtime.get("last_approved_chapter", {}).get("title") != plan["chapter_title"]:
        errors.append("PROMOTION_RUNTIME candidate approved title must match promotion plan")
    if candidate_runtime.get("current_chapter", {}).get("number") != next_chapter:
        errors.append("PROMOTION_RUNTIME candidate current chapter must be chapter+1")
    if candidate_runtime.get("current_chapter", {}).get("status") != "NOT_STARTED":
        errors.append("PROMOTION_RUNTIME candidate next chapter must be NOT_STARTED")
    if candidate_state.get("as_of_chapter") != chapter:
        errors.append("PROMOTION_STATE candidate as_of_chapter must equal promoted chapter")
    if candidate_active_arc.get("canon_through") != chapter:
        errors.append("PROMOTION_ARC candidate canon_through must equal promoted chapter")
    if next_manifest.get("chapter") != next_chapter:
        errors.append("PROMOTION_NEXT manifest chapter must be chapter+1")
    if next_manifest.get("stage") != "NOT_STARTED":
        errors.append("PROMOTION_NEXT manifest must be NOT_STARTED")
    if next_manifest.get("parent_runtime_through") != chapter:
        errors.append("PROMOTION_NEXT parent_runtime_through must equal promoted chapter")

    archive_manifest_path = root / "chapters" / f"{chapter:03d}" / "manifest.yaml"
    next_manifest_target = root / "current" / f"{next_chapter:03d}" / "manifest.yaml"
    report_path = root / "promotion" / f"{chapter:03d}.json"
    for label, target in (
        ("archive", archive_manifest_path),
        ("next_manifest", next_manifest_target),
        ("report", report_path),
    ):
        if target.exists():
            errors.append(f"PROMOTION_TARGET {label} already exists: {target}")

    if errors:
        return errors, {}

    happened_manifest = dict(current_manifest)
    happened_manifest["stage"] = "HAPPENED"
    errors.extend(schema_errors(happened_manifest, "chapter_manifest.schema.json", "HAPPENED_MANIFEST"))
    if errors:
        return errors, {}

    report = {
        "book_id": plan["book_id"],
        "chapter": chapter,
        "result": "PROMOTED",
        "freeze_manifest_sha256": freeze_sha,
        "chapter_sha256": chapter_sha,
        "author_approval_id": approval["id"],
        "chapter_delta_sha256": sha256(paths["chapter_delta"]),
        "candidate_hashes": {
            "runtime": sha256(paths["candidate_runtime"]),
            "state": sha256(paths["candidate_state"]),
            "system": sha256(paths["candidate_system"]),
            "active_arc": sha256(paths["candidate_active_arc"]),
            "next_manifest": sha256(paths["next_manifest"]),
        },
        "next_chapter": next_chapter,
    }
    errors.extend(schema_errors(report, "promotion_report.schema.json", "PROMOTION_REPORT"))
    if errors:
        return errors, {}

    context = {
        "paths": paths,
        "targets": {
            "runtime": runtime_path,
            "state": state_path,
            "system": system_path,
            "active_arc": active_arc_path,
            "current_manifest": current_manifest_path,
            "archive_manifest": archive_manifest_path,
            "next_manifest": next_manifest_target,
            "report": report_path,
        },
        "happened_manifest": happened_manifest,
        "report": report,
    }
    return [], context


def promotion_operations(context: dict) -> list[FileOperation]:
    paths = context["paths"]
    targets = context["targets"]
    happened_bytes = yaml.safe_dump(
        context["happened_manifest"], allow_unicode=True, sort_keys=False
    ).encode("utf-8")
    report_bytes = (json.dumps(context["report"], ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    return [
        FileOperation(targets["runtime"], paths["candidate_runtime"].read_bytes()),
        FileOperation(targets["state"], paths["candidate_state"].read_bytes()),
        FileOperation(targets["system"], paths["candidate_system"].read_bytes()),
        FileOperation(targets["active_arc"], paths["candidate_active_arc"].read_bytes()),
        FileOperation(targets["archive_manifest"], happened_bytes),
        FileOperation(targets["current_manifest"], None),
        FileOperation(targets["next_manifest"], paths["next_manifest"].read_bytes()),
        FileOperation(targets["report"], report_bytes),
    ]


def promote(root: Path, plan_path: Path, *, fault_after: int | None = None) -> list[str]:
    errors, context = validate_promotion(root, plan_path)
    if errors:
        return errors
    apply_failure_atomic(root, promotion_operations(context), fault_after=fault_after)
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote an explicitly author-approved frozen chapter as one failure-atomic transaction."
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    errors, context = validate_promotion(args.root, args.plan)
    if errors:
        print("PROMOTION: BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.validate_only:
        print("PROMOTION: VALID")
        return 0

    apply_failure_atomic(args.root, promotion_operations(context))
    print(
        f"PROMOTION: PASS chapter={context['report']['chapter']} "
        f"next={context['report']['next_chapter']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
