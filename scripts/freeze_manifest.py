#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from dependency_graph import transitive_dependents, validate_graph_file
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ROLES = {
    "CHAPTER_TEXT",
    "PARENT_RUNTIME",
    "CHARACTER_STATE",
    "REGRESSION_RULES",
    "RESEARCH_MANIFEST",
    "QA_MANIFEST",
    "GENERATED_ARTIFACT_MANIFEST",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _schema_errors(manifest: dict, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for error in Draft202012Validator(schema).iter_errors(manifest):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"FREEZE_SCHEMA {location}: {error.message}")
    return errors


def build_manifest(spec_path: Path, output_path: Path) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_base = spec_path.parent
    output_base = output_path.parent.resolve()
    inputs: list[dict] = []
    for item in spec["inputs"]:
        source_path = _resolve(spec_base, item["path"])
        relative = source_path.relative_to(output_base) if source_path.is_relative_to(output_base) else source_path
        inputs.append(
            {
                "role": item["role"],
                "node_id": item["node_id"],
                "path": str(relative),
                "sha256": sha256(source_path),
            }
        )

    graph_path = _resolve(spec_base, spec["graph_path"])
    graph_relative = (
        graph_path.relative_to(output_base) if graph_path.is_relative_to(output_base) else graph_path
    )
    return {
        "book_id": spec["book_id"],
        "schema_version": spec["schema_version"],
        "chapter": spec["chapter"],
        "inputs": inputs,
        "qa_gates": spec["qa_gates"],
        "graph_path": str(graph_relative),
    }


def verify_manifest(manifest_path: Path) -> tuple[list[str], set[str]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent.resolve()
    errors = _schema_errors(manifest, ROOT / "schemas/freeze_manifest.schema.json")
    if errors:
        return errors, set()

    roles = [item["role"] for item in manifest["inputs"]]
    missing_roles = REQUIRED_ROLES - set(roles)
    duplicate_roles = sorted({role for role in roles if roles.count(role) > 1})
    if missing_roles:
        errors.append("FREEZE_ROLES missing: " + ",".join(sorted(missing_roles)))
    if duplicate_roles:
        errors.append("FREEZE_ROLES duplicated: " + ",".join(duplicate_roles))

    graph_path = _resolve(base, manifest["graph_path"])
    graph, graph_validation_errors = validate_graph_file(graph_path)
    errors.extend(graph_validation_errors)
    if graph_validation_errors:
        return errors, set()

    graph_nodes = {node["id"] for node in graph["nodes"]}
    changed_nodes: set[str] = set()
    for item in manifest["inputs"]:
        node_id = item["node_id"]
        if node_id not in graph_nodes:
            errors.append(f"FREEZE_NODE {item['role']}: unknown graph node {node_id}")
            continue
        path = _resolve(base, item["path"])
        if not path.exists():
            errors.append(f"FREEZE_INPUT {item['role']}: missing {path}")
            changed_nodes.add(node_id)
            continue
        actual = sha256(path)
        if actual != item["sha256"]:
            errors.append(
                f"FREEZE_HASH {item['role']}: expected={item['sha256']} actual={actual}"
            )
            changed_nodes.add(node_id)

    for gate, status in manifest["qa_gates"].items():
        if status != "PASS":
            errors.append(f"FREEZE_GATE {gate}: {status}, expected PASS")
            changed_nodes.add("qa_manifest")

    stale = transitive_dependents(graph, changed_nodes) if changed_nodes else set()
    if stale:
        errors.append("STALE_EVIDENCE: " + ",".join(sorted(stale)))
    return errors, stale


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify a cryptographic chapter freeze manifest.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("spec", type=Path)
    build_parser.add_argument("output", type=Path)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("manifest", type=Path)

    args = parser.parse_args()
    if args.command == "build":
        manifest = build_manifest(args.spec, args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        errors, _ = verify_manifest(args.output)
        if errors:
            print("FREEZE_BUILD: FAIL")
            for error in errors:
                print(f"- {error}")
            return 1
        print(f"FREEZE_BUILD: PASS {args.output}")
        return 0

    errors, _ = verify_manifest(args.manifest)
    if errors:
        print("FREEZE_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("FREEZE_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
