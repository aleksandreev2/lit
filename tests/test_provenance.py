from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

from provenance_check import validate_bundle, validate_repository

ROOT = Path(__file__).resolve().parents[1]


def empty_bundle() -> tuple[dict, dict, dict, dict, dict, dict]:
    runtime = {"through_chapter": 24}
    state = {
        "as_of_chapter": 24,
        "characters": [],
        "relationships": [],
        "locations": [],
        "assets_money": [],
        "active_threads": [],
        "future_locks": [],
        "proposals": [],
    }
    facts = {"facts": []}
    knowledge = {"entries": []}
    research = {"records": []}
    instructions = {"instructions": []}
    return runtime, state, facts, knowledge, research, instructions


def test_repository_provenance_authorities_are_valid() -> None:
    assert validate_repository(ROOT, today=date(2026, 8, 14)) == []


def test_objective_fact_cannot_be_promoted_from_plan_only() -> None:
    bundle = list(empty_bundle())
    bundle[2]["facts"] = [
        {
            "id": "SB-F-PLAN-001",
            "classification": "PLAN",
            "sources": [{"source_type": "RUNTIME", "source_id": "runtime", "revision": "abc"}],
            "supersedes": [],
            "superseded_by": None,
        },
        {
            "id": "SB-F-FACT-001",
            "classification": "OBJECTIVE_FACT",
            "sources": [{"source_type": "FACT", "source_id": "SB-F-PLAN-001", "revision": "abc"}],
            "supersedes": [],
            "superseded_by": None,
        },
    ]
    errors = validate_bundle(*bundle, today=date(2026, 8, 14))
    assert any(error.startswith("FACT_PROMOTION SB-F-FACT-001") for error in errors)


def test_character_knowledge_requires_real_character_and_fact() -> None:
    bundle = list(empty_bundle())
    bundle[3]["entries"] = [
        {
            "id": "SB-KNW-001",
            "character_id": "SB-CHAR-GHOST",
            "fact_id": "SB-F-MISSING",
            "acquisition": {
                "method": "WITNESSED",
                "chapter": 24,
                "source_id": "chapter:024",
                "from_character_id": None,
            },
        }
    ]
    errors = validate_bundle(*bundle, today=date(2026, 8, 14))
    assert "KNOWLEDGE_REF SB-KNW-001: unknown character SB-CHAR-GHOST" in errors
    assert "KNOWLEDGE_REF SB-KNW-001: unknown fact SB-F-MISSING" in errors


def test_research_freshness_and_claim_linkage_are_enforced() -> None:
    bundle = list(empty_bundle())
    bundle[2]["facts"] = [
        {
            "id": "SB-F-PRICE-001",
            "classification": "OBJECTIVE_FACT",
            "sources": [{"source_type": "RESEARCH", "source_id": "SB-RES-001", "revision": "r1"}],
            "supersedes": [],
            "superseded_by": None,
        }
    ]
    bundle[4]["records"] = [
        {
            "id": "SB-RES-001",
            "claim_id": "SB-F-PRICE-001",
            "dependent_fact_ids": [],
            "freshness_class": "VOLATILE",
            "recheck_after": "2026-08-13",
            "event_trigger": None,
        }
    ]
    errors = validate_bundle(*bundle, today=date(2026, 8, 14))
    assert "RESEARCH_REF SB-RES-001: claim_id must be included in dependent_fact_ids" in errors
    assert "RESEARCH_STALE SB-RES-001: recheck_after 2026-08-13 is before 2026-08-14" in errors


def test_fact_supersession_must_be_bidirectional() -> None:
    bundle = list(empty_bundle())
    source = {"source_type": "RUNTIME", "source_id": "runtime", "revision": "r1"}
    bundle[2]["facts"] = [
        {
            "id": "SB-F-OLD",
            "classification": "OBJECTIVE_FACT",
            "sources": [source],
            "supersedes": [],
            "superseded_by": None,
        },
        {
            "id": "SB-F-NEW",
            "classification": "OBJECTIVE_FACT",
            "sources": [deepcopy(source)],
            "supersedes": ["SB-F-OLD"],
            "superseded_by": None,
        },
    ]
    errors = validate_bundle(*bundle, today=date(2026, 8, 14))
    assert (
        "FACT_SUPERSESSION SB-F-NEW: SB-F-OLD.superseded_by must point back to SB-F-NEW"
        in errors
    )
