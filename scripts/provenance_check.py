#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Iterable

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_FACT_SOURCES = {
    "HAPPENED_CHAPTER",
    "RUNTIME",
    "SYSTEM",
    "AUTHOR_INSTRUCTION",
    "RESEARCH",
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def schema_errors(data: dict, schema_path: Path, label: str) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"{label}_SCHEMA {location}: {error.message}")
    return errors


def _duplicate_ids(items: Iterable[dict], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        item_id = item.get("id")
        if item_id in seen:
            errors.append(f"DUPLICATE_ID {label}: {item_id}")
        seen.add(item_id)
    return errors


def _collect_state_entities(state: dict) -> tuple[dict[str, dict], list[str]]:
    entity_groups = (
        "characters",
        "relationships",
        "locations",
        "assets_money",
        "active_threads",
        "future_locks",
        "proposals",
    )
    entities: dict[str, dict] = {}
    errors: list[str] = []
    for group in entity_groups:
        errors.extend(_duplicate_ids(state.get(group, []), f"state.{group}"))
        for item in state.get(group, []):
            item_id = item.get("id")
            if item_id in entities:
                errors.append(f"DUPLICATE_ENTITY_ID across state registries: {item_id}")
            entities[item_id] = item
    return entities, errors


def validate_bundle(
    runtime: dict,
    state: dict,
    facts_doc: dict,
    knowledge_doc: dict,
    research_doc: dict,
    instructions_doc: dict,
    *,
    today: date | None = None,
) -> list[str]:
    errors: list[str] = []
    today = today or date.today()

    facts = facts_doc.get("facts", [])
    knowledge = knowledge_doc.get("entries", [])
    research = research_doc.get("records", [])
    instructions = instructions_doc.get("instructions", [])

    errors.extend(_duplicate_ids(facts, "facts"))
    errors.extend(_duplicate_ids(knowledge, "knowledge"))
    errors.extend(_duplicate_ids(research, "research"))
    errors.extend(_duplicate_ids(instructions, "author_instructions"))

    entities, entity_errors = _collect_state_entities(state)
    errors.extend(entity_errors)

    fact_by_id = {item["id"]: item for item in facts if item.get("id")}
    research_by_id = {item["id"]: item for item in research if item.get("id")}
    instruction_by_id = {item["id"]: item for item in instructions if item.get("id")}
    character_ids = {item["id"] for item in state.get("characters", []) if item.get("id")}

    if state.get("as_of_chapter") != runtime.get("through_chapter"):
        errors.append(
            "STATE_RUNTIME_SYNC state.as_of_chapter "
            f"{state.get('as_of_chapter')} != runtime.through_chapter {runtime.get('through_chapter')}"
        )

    for fact in facts:
        fact_id = fact.get("id")
        classification = fact.get("classification")
        sources = fact.get("sources", [])

        if classification == "OBJECTIVE_FACT" and not any(
            source.get("source_type") in AUTHORITATIVE_FACT_SOURCES for source in sources
        ):
            errors.append(
                f"FACT_PROMOTION {fact_id}: OBJECTIVE_FACT needs a direct authoritative source; "
                "FACT-only provenance cannot promote plan/belief/proposal to objective fact"
            )

        for source in sources:
            source_type = source.get("source_type")
            source_id = source.get("source_id")
            if source_type == "FACT" and source_id not in fact_by_id:
                errors.append(f"FACT_SOURCE {fact_id}: unknown fact source {source_id}")
            elif source_type == "RESEARCH" and source_id not in research_by_id:
                errors.append(f"FACT_SOURCE {fact_id}: unknown research source {source_id}")
            elif source_type == "AUTHOR_INSTRUCTION" and source_id not in instruction_by_id:
                errors.append(f"FACT_SOURCE {fact_id}: unknown author instruction {source_id}")

        for superseded_id in fact.get("supersedes", []):
            if superseded_id == fact_id:
                errors.append(f"FACT_SUPERSESSION {fact_id}: cannot supersede itself")
            elif superseded_id not in fact_by_id:
                errors.append(f"FACT_SUPERSESSION {fact_id}: unknown superseded fact {superseded_id}")
            elif fact_by_id[superseded_id].get("superseded_by") != fact_id:
                errors.append(
                    f"FACT_SUPERSESSION {fact_id}: {superseded_id}.superseded_by must point back to {fact_id}"
                )

        superseded_by = fact.get("superseded_by")
        if superseded_by:
            if superseded_by not in fact_by_id:
                errors.append(f"FACT_SUPERSESSION {fact_id}: unknown superseding fact {superseded_by}")
            elif fact_id not in fact_by_id[superseded_by].get("supersedes", []):
                errors.append(
                    f"FACT_SUPERSESSION {fact_id}: {superseded_by}.supersedes must contain {fact_id}"
                )

    for group in (
        "characters",
        "relationships",
        "locations",
        "assets_money",
        "active_threads",
        "future_locks",
        "proposals",
    ):
        for item in state.get(group, []):
            for fact_id in item.get("fact_ids", []):
                if fact_id not in fact_by_id:
                    errors.append(f"STATE_FACT_REF {item.get('id')}: unknown fact {fact_id}")

    for relationship in state.get("relationships", []):
        for participant in relationship.get("participants", []):
            if participant not in character_ids:
                errors.append(
                    f"RELATIONSHIP_REF {relationship.get('id')}: unknown character {participant}"
                )

    for asset in state.get("assets_money", []):
        owner_id = asset.get("owner_id", "")
        if owner_id.startswith("SB-CHAR-") and owner_id not in character_ids:
            errors.append(f"ASSET_OWNER {asset.get('id')}: unknown character owner {owner_id}")

    for entry in knowledge:
        entry_id = entry.get("id")
        character_id = entry.get("character_id")
        fact_id = entry.get("fact_id")
        acquisition = entry.get("acquisition", {})
        if character_id not in character_ids:
            errors.append(f"KNOWLEDGE_REF {entry_id}: unknown character {character_id}")
        if fact_id not in fact_by_id:
            errors.append(f"KNOWLEDGE_REF {entry_id}: unknown fact {fact_id}")
        from_character = acquisition.get("from_character_id")
        if from_character and from_character not in character_ids:
            errors.append(f"KNOWLEDGE_SOURCE {entry_id}: unknown source character {from_character}")
        if acquisition.get("method") == "TOLD_BY" and from_character == character_id:
            errors.append(f"KNOWLEDGE_SOURCE {entry_id}: TOLD_BY cannot name the same character")

    for record in research:
        record_id = record.get("id")
        claim_id = record.get("claim_id")
        dependent_fact_ids = record.get("dependent_fact_ids", [])
        if claim_id not in fact_by_id:
            errors.append(f"RESEARCH_REF {record_id}: unknown claim fact {claim_id}")
        if claim_id not in dependent_fact_ids:
            errors.append(f"RESEARCH_REF {record_id}: claim_id must be included in dependent_fact_ids")
        for fact_id in dependent_fact_ids:
            if fact_id not in fact_by_id:
                errors.append(f"RESEARCH_REF {record_id}: unknown dependent fact {fact_id}")

        freshness_class = record.get("freshness_class")
        recheck_after = record.get("recheck_after")
        event_trigger = record.get("event_trigger")
        if freshness_class in {"VOLATILE", "EVENT_DRIVEN"} and not (recheck_after or event_trigger):
            errors.append(
                f"RESEARCH_FRESHNESS {record_id}: {freshness_class} requires recheck_after or event_trigger"
            )
        if recheck_after and date.fromisoformat(recheck_after) < today:
            errors.append(
                f"RESEARCH_STALE {record_id}: recheck_after {recheck_after} is before {today.isoformat()}"
            )

    for instruction in instructions:
        instruction_id = instruction.get("id")
        superseded_by = instruction.get("superseded_by")
        if superseded_by:
            if superseded_by == instruction_id:
                errors.append(f"AUTHOR_INSTRUCTION {instruction_id}: cannot supersede itself")
            elif superseded_by not in instruction_by_id:
                errors.append(
                    f"AUTHOR_INSTRUCTION {instruction_id}: unknown superseding instruction {superseded_by}"
                )

    return errors


def validate_repository(root: Path = ROOT, *, today: date | None = None) -> list[str]:
    docs = {
        "runtime": load_yaml(root / "canon/runtime.yaml"),
        "system": load_yaml(root / "canon/system.yaml"),
        "state": load_yaml(root / "canon/state.yaml"),
        "facts": load_yaml(root / "canon/facts.yaml"),
        "knowledge": load_yaml(root / "canon/knowledge.yaml"),
        "research": load_yaml(root / "research/ledger.yaml"),
        "instructions": load_yaml(root / "rules/author_instructions.yaml"),
    }
    schema_map = {
        "runtime": "runtime.schema.json",
        "system": "system.schema.json",
        "state": "structured_state.schema.json",
        "facts": "fact_ledger.schema.json",
        "knowledge": "knowledge.schema.json",
        "research": "research_ledger.schema.json",
        "instructions": "author_instructions.schema.json",
    }

    errors: list[str] = []
    for label, schema_name in schema_map.items():
        errors.extend(schema_errors(docs[label], root / "schemas" / schema_name, label.upper()))

    if errors:
        return errors

    errors.extend(
        validate_bundle(
            docs["runtime"],
            docs["state"],
            docs["facts"],
            docs["knowledge"],
            docs["research"],
            docs["instructions"],
            today=today,
        )
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structured canon and provenance ledgers.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--today", type=date.fromisoformat)
    args = parser.parse_args()

    errors = validate_repository(args.root, today=args.today)
    if errors:
        print("PROVENANCE_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PROVENANCE_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
