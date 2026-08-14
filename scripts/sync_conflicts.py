#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONFLICT_STATES = {"GITHUB_CHANGED", "DRIVE_CHANGED", "BOTH_CHANGED"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def schema_errors(manifest: dict, root: Path = ROOT) -> list[str]:
    schema = json.loads((root / "schemas/sync_manifest.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path)):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"SYNC_SCHEMA {location}: {error.message}")
    return errors


def observed_github_hash(entry: dict, root: Path) -> str | None:
    path = (root / entry["github"]["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        return None
    return sha256(path)


def classify(entry: dict, observation: dict, root: Path) -> str:
    baseline_github = entry["github"]["sha256"]
    current_github = observation.get("github_sha256") or observed_github_hash(entry, root)
    current_drive_revision = observation.get("drive_revision")
    current_drive_sha = observation.get("drive_sha256")

    if current_github is None or current_drive_revision is None:
        return "UNKNOWN"

    github_changed = current_github != baseline_github
    drive_changed = current_drive_revision != entry["drive"]["revision"]
    baseline_drive_sha = entry["drive"].get("sha256")
    if baseline_drive_sha is not None and current_drive_sha is not None:
        drive_changed = drive_changed or current_drive_sha != baseline_drive_sha

    if github_changed and drive_changed:
        return "BOTH_CHANGED"
    if github_changed:
        return "GITHUB_CHANGED"
    if drive_changed:
        return "DRIVE_CHANGED"
    return "CLEAN"


def evaluate_manifest(
    manifest: dict,
    observations: dict[str, dict] | None,
    root: Path,
) -> tuple[list[dict], list[str]]:
    errors = schema_errors(manifest, root)
    if errors:
        return [], errors

    entries = manifest["entries"]
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        errors.append("SYNC_ID duplicate sync entry ID")
        return [], errors

    observations = observations or {}
    results: list[dict] = []
    for entry in entries:
        entry_id = entry["id"]
        state = classify(entry, observations.get(entry_id, {}), root)
        results.append(
            {
                "id": entry_id,
                "state": state,
                "direction_allowed": entry["direction_allowed"],
                "authority_owner": entry["authority_owner"],
                "automatic_write_allowed": False,
            }
        )
    return results, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Drive/GitHub sync conflicts without writing either side.")
    parser.add_argument("manifest", type=Path, nargs="?", default=ROOT / "sync/manifest.yaml")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-conflict", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    observations = None
    if args.observations:
        observations = json.loads(args.observations.read_text(encoding="utf-8")).get("entries", {})

    results, errors = evaluate_manifest(manifest, observations, args.root.resolve())
    if errors:
        print("SYNC_CONFLICT_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    payload = {
        "book_id": manifest["book_id"],
        "results": results,
        "counts": {
            state: sum(1 for item in results if item["state"] == state)
            for state in ("CLEAN", "GITHUB_CHANGED", "DRIVE_CHANGED", "BOTH_CHANGED", "UNKNOWN")
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("SYNC_CONFLICT_CHECK: PASS")
    for item in results:
        print(f"- {item['id']}: {item['state']} ({item['direction_allowed']})")

    if args.fail_on_conflict and any(item["state"] in CONFLICT_STATES for item in results):
        print("SYNC_CONFLICT_CHECK: CONFLICT")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
