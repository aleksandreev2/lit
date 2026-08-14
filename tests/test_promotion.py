from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from freeze_manifest import build_manifest, sha256
from promote_chapter import promote, validate_promotion

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = 25
TITLE = "Synthetic Chapter Twenty Five"
APPROVAL_ID = "SB-APP-SYNTHETIC-025"


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def runtime_doc(through: int, current: int, status: str, title: str) -> dict:
    return {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "through_chapter": through,
        "last_approved_chapter": {"number": through, "title": title},
        "current_chapter": {"number": current, "status": status},
        "system": {"current_quota_usd": 1_000_000, "deadline": "2026-08-21T12:00:00+04:00"},
    }


def state_doc(as_of: int) -> dict:
    return {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "as_of_chapter": as_of,
        "characters": [],
        "relationships": [],
        "locations": [],
        "assets_money": [],
        "active_threads": [],
        "future_locks": [],
        "proposals": [],
    }


def system_doc() -> dict:
    return {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "rules": {
            "cycle_length_days": 7,
            "spending_recognition": {
                "bitcoin_purchase_counts_1_to_1": True,
                "direct_transfer_counts_1_to_1": True,
            },
            "current_transition_overrides": [],
        },
        "history": [
            {
                "chapter": 24,
                "event": "NEW_CYCLE",
                "quota_usd": 1_000_000,
                "deadline": "2026-08-21T12:00:00+04:00",
            }
        ],
    }


def active_arc_doc(canon_through: int) -> dict:
    return {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "canon_through": canon_through,
        "happened": [],
        "active_threads": [],
        "hard_future_locks": [],
        "proposals": [],
    }


def manifest_doc(chapter: int, stage: str, parent: int, chapter_hash: str | None = None) -> dict:
    approved = stage in {"AUTHOR_APPROVED", "HAPPENED"}
    frozen = stage in {"FINAL_TEXT_FROZEN", "AUTHOR_APPROVED", "HAPPENED"}
    return {
        "book_id": "SISTEMA_BOGATSTVA",
        "chapter": chapter,
        "stage": stage,
        "parent_runtime_through": parent,
        "author_instructions": [],
        "source_sync": {
            "runtime_sha256": None,
            "character_profiles": [],
            "approved_chapters": [],
            "production_rules": [],
        },
        "research": {"required": [], "completed": []},
        "qa": {
            "structural": "PASS" if approved else "PENDING",
            "dialogue": "PASS" if approved else "PENDING",
            "prose_pov": "PASS" if approved else "PENDING",
            "character": "PASS" if approved else "PENDING",
            "continuity_knowledge": "PASS" if approved else "PENDING",
            "regression": "PASS" if approved else "PENDING",
            "russian_proofread": "PASS" if approved else "PENDING",
            "fact_recheck": "PASS" if approved else "PENDING",
            "text_preflight": "PASS" if approved else "PENDING",
            "final_reread": "PASS" if approved else "PENDING",
        },
        "freeze": {
            "chapter_sha256": chapter_hash if frozen else None,
            "final_text_frozen": frozen,
            "author_approved": approved,
            "author_approval_evidence_id": APPROVAL_ID if approved else None,
        },
    }


def make_promotion_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    package = tmp_path / "package"
    package.mkdir(parents=True)

    current_runtime = runtime_doc(24, 25, "AUTHOR_APPROVED", "Synthetic Chapter Twenty Four")
    current_state = state_doc(24)
    current_system = system_doc()
    current_arc = active_arc_doc(24)
    write_yaml(root / "canon/runtime.yaml", current_runtime)
    write_yaml(root / "canon/state.yaml", current_state)
    write_yaml(root / "canon/system.yaml", current_system)
    write_yaml(root / "canon/active_arc.yaml", current_arc)

    chapter_text = package / "chapter.txt"
    chapter_text.write_text("Synthetic approved chapter fixture.\n", encoding="utf-8")
    chapter_hash = sha256(chapter_text)
    write_yaml(
        root / "current/025/manifest.yaml",
        manifest_doc(25, "AUTHOR_APPROVED", 24, chapter_hash),
    )

    rules = package / "rules.yaml"
    research = package / "research.yaml"
    qa = package / "qa.json"
    generated = package / "generated.json"
    rules.write_text("rules: []\n", encoding="utf-8")
    research.write_text("records: []\n", encoding="utf-8")
    qa.write_text("{}\n", encoding="utf-8")
    generated.write_text("{}\n", encoding="utf-8")
    graph = package / "dependency_graph.yaml"
    graph.write_text((ROOT / "config/dependency_graph.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    freeze_spec = {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "chapter": 25,
        "inputs": [
            {"role": "CHAPTER_TEXT", "node_id": "chapter_text", "path": "chapter.txt"},
            {
                "role": "PARENT_RUNTIME",
                "node_id": "runtime",
                "path": "../repo/canon/runtime.yaml",
            },
            {
                "role": "CHARACTER_STATE",
                "node_id": "character_state",
                "path": "../repo/canon/state.yaml",
            },
            {"role": "REGRESSION_RULES", "node_id": "rules", "path": "rules.yaml"},
            {"role": "RESEARCH_MANIFEST", "node_id": "research", "path": "research.yaml"},
            {"role": "QA_MANIFEST", "node_id": "qa_manifest", "path": "qa.json"},
            {
                "role": "GENERATED_ARTIFACT_MANIFEST",
                "node_id": "generated_artifact_manifest",
                "path": "generated.json",
            },
        ],
        "qa_gates": {
            "structural": "PASS",
            "dialogue": "PASS",
            "prose_pov": "PASS",
            "character": "PASS",
            "continuity_knowledge": "PASS",
            "regression": "PASS",
            "russian_proofread": "PASS",
            "fact_recheck": "PASS",
            "text_preflight": "PASS",
            "final_reread": "PASS",
        },
        "graph_path": "dependency_graph.yaml",
    }
    spec_path = package / "freeze-spec.json"
    write_json(spec_path, freeze_spec)
    freeze_path = package / "freeze.json"
    freeze = build_manifest(spec_path, freeze_path)
    write_json(freeze_path, freeze)

    approval = {
        "id": APPROVAL_ID,
        "book_id": "SISTEMA_BOGATSTVA",
        "chapter": 25,
        "approver_role": "AUTHOR",
        "source_type": "EXPLICIT_AUTHOR_ACTION",
        "approved_at": "2026-08-14T20:00:00+04:00",
        "freeze_manifest_sha256": sha256(freeze_path),
        "chapter_sha256": chapter_hash,
        "source_context": "Synthetic explicit-author-action fixture",
        "status": "ACTIVE",
    }
    write_json(package / "approval.json", approval)

    delta = {
        "book_id": "SISTEMA_BOGATSTVA",
        "chapter": 25,
        "source_sha256": chapter_hash,
        "fact_changes": [],
        "knowledge_changes": [],
        "state_changes": [],
        "research_changes": [],
        "system_changes": [],
        "arc_changes": [],
    }
    write_json(package / "delta.json", delta)

    write_yaml(package / "candidate-runtime.yaml", runtime_doc(25, 26, "NOT_STARTED", TITLE))
    write_yaml(package / "candidate-state.yaml", state_doc(25))
    write_yaml(package / "candidate-system.yaml", system_doc())
    write_yaml(package / "candidate-active-arc.yaml", active_arc_doc(25))
    write_yaml(package / "next-manifest.yaml", manifest_doc(26, "NOT_STARTED", 25))

    plan = {
        "book_id": "SISTEMA_BOGATSTVA",
        "chapter": 25,
        "chapter_title": TITLE,
        "freeze_manifest": "freeze.json",
        "author_approval": "approval.json",
        "chapter_delta": "delta.json",
        "candidate_runtime": "candidate-runtime.yaml",
        "candidate_state": "candidate-state.yaml",
        "candidate_system": "candidate-system.yaml",
        "candidate_active_arc": "candidate-active-arc.yaml",
        "next_manifest": "next-manifest.yaml",
    }
    plan_path = package / "promotion-plan.json"
    write_json(plan_path, plan)
    return root, package, plan_path


def test_valid_promotion_advances_all_authorities_and_creates_next_chapter(tmp_path: Path) -> None:
    root, _, plan_path = make_promotion_fixture(tmp_path)
    assert validate_promotion(root, plan_path)[0] == []
    assert promote(root, plan_path) == []

    runtime = yaml.safe_load((root / "canon/runtime.yaml").read_text(encoding="utf-8"))
    assert runtime["through_chapter"] == 25
    assert runtime["last_approved_chapter"]["number"] == 25
    assert runtime["current_chapter"] == {"number": 26, "status": "NOT_STARTED"}

    assert not (root / "current/025/manifest.yaml").exists()
    archived = yaml.safe_load((root / "chapters/025/manifest.yaml").read_text(encoding="utf-8"))
    assert archived["stage"] == "HAPPENED"
    next_manifest = yaml.safe_load((root / "current/026/manifest.yaml").read_text(encoding="utf-8"))
    assert next_manifest["stage"] == "NOT_STARTED"

    report = json.loads((root / "promotion/025.json").read_text(encoding="utf-8"))
    assert report["result"] == "PROMOTED"
    assert report["author_approval_id"] == APPROVAL_ID


def test_missing_author_approval_blocks_without_mutation(tmp_path: Path) -> None:
    root, package, plan_path = make_promotion_fixture(tmp_path)
    before = (root / "canon/runtime.yaml").read_bytes()
    (package / "approval.json").unlink()

    errors, _ = validate_promotion(root, plan_path)
    assert any("author_approval: missing" in error for error in errors)
    assert (root / "canon/runtime.yaml").read_bytes() == before
    assert (root / "current/025/manifest.yaml").exists()


def test_approval_must_bind_exact_freeze_hash(tmp_path: Path) -> None:
    root, package, plan_path = make_promotion_fixture(tmp_path)
    approval_path = package / "approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["freeze_manifest_sha256"] = "0" * 64
    write_json(approval_path, approval)

    errors, _ = validate_promotion(root, plan_path)
    assert "PROMOTION_APPROVAL freeze manifest hash mismatch" in errors
    assert (root / "current/025/manifest.yaml").exists()


def test_delta_must_bind_exact_frozen_chapter_hash(tmp_path: Path) -> None:
    root, package, plan_path = make_promotion_fixture(tmp_path)
    delta_path = package / "delta.json"
    delta = json.loads(delta_path.read_text(encoding="utf-8"))
    delta["source_sha256"] = "f" * 64
    write_json(delta_path, delta)

    errors, _ = validate_promotion(root, plan_path)
    assert "PROMOTION_DELTA must bind the exact frozen chapter hash" in errors
    assert (root / "current/025/manifest.yaml").exists()


def test_injected_mid_commit_failure_rolls_back_every_authority(tmp_path: Path) -> None:
    root, _, plan_path = make_promotion_fixture(tmp_path)
    tracked = [
        root / "canon/runtime.yaml",
        root / "canon/state.yaml",
        root / "canon/system.yaml",
        root / "canon/active_arc.yaml",
        root / "current/025/manifest.yaml",
    ]
    before = {path: path.read_bytes() for path in tracked}

    with pytest.raises(RuntimeError, match="injected transaction failure"):
        promote(root, plan_path, fault_after=4)

    for path, original in before.items():
        assert path.read_bytes() == original
    assert not (root / "chapters/025/manifest.yaml").exists()
    assert not (root / "current/026/manifest.yaml").exists()
    assert not (root / "promotion/025.json").exists()
    assert not (root / ".production-promotion.lock").exists()
