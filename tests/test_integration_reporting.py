from __future__ import annotations

import json
from pathlib import Path

import yaml
from freeze_manifest import build_manifest, sha256
from pdf_provenance_check import validate_record
from qa_report import generate_report
from qa_report_check import validate_report
from sync_conflicts import evaluate_manifest, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_sync_manifest_is_manual_only_and_conflict_aware() -> None:
    manifest = load_manifest(ROOT / "sync/manifest.yaml")
    observations = {
        entry["id"]: {
            "github_sha256": entry["github"]["sha256"],
            "drive_revision": entry["drive"]["revision"],
        }
        for entry in manifest["entries"]
    }
    results, errors = evaluate_manifest(manifest, observations, ROOT)
    assert errors == []
    assert {item["state"] for item in results} == {"CLEAN"}
    assert all(item["direction_allowed"] == "MANUAL_ONLY" for item in results)
    assert all(item["automatic_write_allowed"] is False for item in results)


def test_sync_conflict_classifier_detects_each_side_and_both() -> None:
    manifest = load_manifest(ROOT / "sync/manifest.yaml")
    entry = manifest["entries"][0]

    drive_only = {
        entry["id"]: {
            "github_sha256": entry["github"]["sha256"],
            "drive_revision": "999",
        }
    }
    results, errors = evaluate_manifest(manifest, drive_only, ROOT)
    assert errors == []
    assert results[0]["state"] == "DRIVE_CHANGED"

    both = {
        entry["id"]: {
            "github_sha256": "f" * 64,
            "drive_revision": "999",
        }
    }
    results, errors = evaluate_manifest(manifest, both, ROOT)
    assert errors == []
    assert results[0]["state"] == "BOTH_CHANGED"


def test_sync_without_live_drive_observation_is_unknown_not_clean() -> None:
    manifest = load_manifest(ROOT / "sync/manifest.yaml")
    results, errors = evaluate_manifest(manifest, None, ROOT)
    assert errors == []
    assert {item["state"] for item in results} == {"UNKNOWN"}


def test_qa_report_is_compact_hashed_and_tracks_current_runtime(tmp_path: Path) -> None:
    report_dir = tmp_path / "qa-report"
    summary = generate_report(ROOT, report_dir, "deadbeefcafebabe")
    runtime = yaml.safe_load((ROOT / "canon/runtime.yaml").read_text(encoding="utf-8"))
    assert summary["counts"] == {"PASS": 7, "BLOCK": 0, "REVIEW": 1}
    assert {item["id"] for item in summary["checks"]} >= {
        "russian_naturalness_corpus",
        "pronoun_coreference_corpus",
        "semantic_coreference_corpus",
    }
    assert "rules/pronoun_regressions.yaml" in summary["dependency_hashes"]
    assert "rules/semantic_coreference_regressions.yaml" in summary["dependency_hashes"]
    assert summary["current_chapter"] == runtime["current_chapter"]["number"]
    assert summary["current_stage"] == runtime["current_chapter"]["status"]
    assert summary["freeze"]["status"] == "NOT_AVAILABLE"
    assert summary["semantic_review_status"] == "NOT_RUN"
    assert validate_report(report_dir) == []


def test_qa_report_tamper_is_detected(tmp_path: Path) -> None:
    report_dir = tmp_path / "qa-report"
    generate_report(ROOT, report_dir, "deadbeefcafebabe")
    log_path = report_dir / "logs/project_preflight.log"
    log_path.write_text("tampered\n", encoding="utf-8")
    errors = validate_report(report_dir)
    assert any("hash mismatch logs/project_preflight.log" in error for error in errors)


def make_pdf_fixture(tmp_path: Path) -> Path:
    package = tmp_path / "pdf-package"
    package.mkdir()
    graph = package / "dependency_graph.yaml"
    graph.write_text(
        (ROOT / "config/dependency_graph.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    files_and_nodes = {
        "CHAPTER_TEXT": ("chapter.txt", "chapter_text"),
        "PARENT_RUNTIME": ("runtime.yaml", "runtime"),
        "CHARACTER_STATE": ("state.yaml", "character_state"),
        "REGRESSION_RULES": ("rules.yaml", "rules"),
        "RESEARCH_MANIFEST": ("research.yaml", "research"),
        "QA_MANIFEST": ("qa.json", "qa_manifest"),
        "GENERATED_ARTIFACT_MANIFEST": ("generated.json", "generated_artifact_manifest"),
    }
    inputs = []
    for index, (role, (name, node_id)) in enumerate(files_and_nodes.items(), start=1):
        path = package / name
        path.write_text(f"synthetic-{index}\n", encoding="utf-8")
        inputs.append({"role": role, "node_id": node_id, "path": name})

    spec = {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "chapter": 999,
        "inputs": inputs,
        "qa_gates": {"all_blocking": "PASS"},
        "graph_path": "dependency_graph.yaml",
    }
    spec_path = package / "freeze-spec.json"
    write_json(spec_path, spec)
    freeze_path = package / "freeze.json"
    freeze = build_manifest(spec_path, freeze_path)
    write_json(freeze_path, freeze)

    pdf_path = package / "release.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF\n")
    technical = package / "technical.json"
    technical.write_text('{"status":"PASS"}\n', encoding="utf-8")
    visual = package / "visual.txt"
    visual.write_text("synthetic rendered visual QA evidence\n", encoding="utf-8")

    record = {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "chapter": 999,
        "frozen_source": {"path": "chapter.txt", "sha256": sha256(package / "chapter.txt")},
        "freeze_manifest": {"path": "freeze.json", "sha256": sha256(freeze_path)},
        "pdf": {"path": "release.pdf", "sha256": sha256(pdf_path)},
        "technical_preflight": {
            "status": "PASS",
            "evidence": {"path": "technical.json", "sha256": sha256(technical)},
        },
        "visual_qa": {
            "status": "PASS",
            "evidence": {"path": "visual.txt", "sha256": sha256(visual)},
        },
        "deliverable_status": "READY",
    }
    record_path = package / "pdf-provenance.json"
    write_json(record_path, record)
    return record_path


def test_pdf_ready_requires_exact_frozen_source_and_both_qa_evidence(tmp_path: Path) -> None:
    record_path = make_pdf_fixture(tmp_path)
    assert validate_record(record_path) == []


def test_pdf_source_or_visual_evidence_change_blocks_provenance(tmp_path: Path) -> None:
    record_path = make_pdf_fixture(tmp_path)
    package = record_path.parent
    (package / "chapter.txt").write_text("changed after freeze\n", encoding="utf-8")
    (package / "visual.txt").write_text("changed visual evidence\n", encoding="utf-8")

    errors = validate_record(record_path)
    assert any("PDF_PROVENANCE_HASH frozen_source" in error for error in errors)
    assert any("PDF_PROVENANCE_HASH visual_qa" in error for error in errors)
