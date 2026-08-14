from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def test_current_manifest_schema_and_parentage() -> None:
    runtime = yaml.safe_load((ROOT / "canon/runtime.yaml").read_text(encoding="utf-8"))
    current = runtime["current_chapter"]["number"]
    manifest_path = ROOT / "current" / f"{current:03d}" / "manifest.yaml"
    assert manifest_path.exists(), f"missing current manifest: {manifest_path}"

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/chapter_manifest.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    assert not errors, "\n".join(error.message for error in errors)

    assert manifest["chapter"] == current
    assert manifest["parent_runtime_through"] == runtime["through_chapter"]

    if manifest["stage"] == "NOT_STARTED":
        assert manifest["freeze"]["final_text_frozen"] is False
        assert manifest["freeze"]["author_approved"] is False
        assert manifest["freeze"]["chapter_sha256"] is None
