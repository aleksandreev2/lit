from __future__ import annotations

import json
from pathlib import Path

import yaml
from dependency_graph import graph_errors, transitive_dependents, validate_graph_file
from freeze_manifest import build_manifest, verify_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_repository_dependency_graph_is_valid_and_acyclic() -> None:
    graph, errors = validate_graph_file(ROOT / "config/dependency_graph.yaml")
    assert errors == []
    assert len(graph["nodes"]) >= 19


def test_runtime_change_invalidates_only_transitive_dependents() -> None:
    graph = yaml.safe_load((ROOT / "config/dependency_graph.yaml").read_text(encoding="utf-8"))
    stale = transitive_dependents(graph, {"runtime"})
    assert "runtime" in stale
    assert "continuity_qa" in stale
    assert "qa_manifest" in stale
    assert "freeze" in stale
    assert "release_artifact_manifest" in stale
    assert "pdf_release" in stale
    assert "dialogue_qa" not in stale


def test_character_state_invalidates_coreference_and_generated_evidence() -> None:
    graph = yaml.safe_load((ROOT / "config/dependency_graph.yaml").read_text(encoding="utf-8"))
    stale = transitive_dependents(graph, {"character_state"})
    assert "pronoun_coreference_qa" in stale
    assert "semantic_coreference_qa" in stale
    assert "generated_artifact_manifest" in stale
    assert "qa_manifest" in stale
    assert "freeze" in stale
    assert "pdf_release" in stale


def test_cycle_is_rejected() -> None:
    graph = {
        "nodes": [
            {"id": "alpha", "depends_on": ["beta"]},
            {"id": "beta", "depends_on": ["alpha"]},
        ]
    }
    assert any(error.startswith("CYCLE ") for error in graph_errors(graph))


def _write_freeze_fixture(tmp_path: Path) -> Path:
    graph_path = tmp_path / "dependency_graph.yaml"
    graph_path.write_text(
        (ROOT / "config/dependency_graph.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    role_to_file_and_node = {
        "CHAPTER_TEXT": ("chapter.txt", "chapter_text"),
        "PARENT_RUNTIME": ("runtime.yaml", "runtime"),
        "CHARACTER_STATE": ("state.yaml", "character_state"),
        "REGRESSION_RULES": ("rules.yaml", "rules"),
        "RESEARCH_MANIFEST": ("research.yaml", "research"),
        "QA_MANIFEST": ("qa.json", "qa_manifest"),
        "GENERATED_ARTIFACT_MANIFEST": ("generated.json", "generated_artifact_manifest"),
    }
    inputs = []
    for index, (role, (filename, node_id)) in enumerate(role_to_file_and_node.items(), start=1):
        path = tmp_path / filename
        path.write_text(f"fixture-{index}\n", encoding="utf-8")
        inputs.append({"role": role, "node_id": node_id, "path": filename})

    spec = {
        "book_id": "SISTEMA_BOGATSTVA",
        "schema_version": 1,
        "chapter": 999,
        "inputs": inputs,
        "qa_gates": {
            "structural": "PASS",
            "dialogue": "PASS",
            "continuity": "PASS",
            "regression": "PASS",
            "fact": "PASS",
        },
        "graph_path": "dependency_graph.yaml",
    }
    spec_path = tmp_path / "freeze-spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    manifest_path = tmp_path / "freeze.json"
    manifest = build_manifest(spec_path, manifest_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_freeze_manifest_verifies_exact_dependency_hashes(tmp_path: Path) -> None:
    manifest_path = _write_freeze_fixture(tmp_path)
    errors, stale = verify_manifest(manifest_path)
    assert errors == []
    assert stale == set()


def test_dependency_change_invalidates_freeze_and_release(tmp_path: Path) -> None:
    manifest_path = _write_freeze_fixture(tmp_path)
    (tmp_path / "runtime.yaml").write_text("changed-runtime\n", encoding="utf-8")

    errors, stale = verify_manifest(manifest_path)
    assert any(error.startswith("FREEZE_HASH PARENT_RUNTIME") for error in errors)
    assert "runtime" in stale
    assert "continuity_qa" in stale
    assert "qa_manifest" in stale
    assert "freeze" in stale
    assert "pdf_release" in stale


def test_non_pass_qa_gate_invalidates_freeze(tmp_path: Path) -> None:
    manifest_path = _write_freeze_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["qa_gates"]["dialogue"] = "REVIEW"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors, stale = verify_manifest(manifest_path)
    assert "FREEZE_GATE dialogue: REVIEW, expected PASS" in errors
    assert "qa_manifest" in stale
    assert "freeze" in stale
    assert "pdf_release" in stale
