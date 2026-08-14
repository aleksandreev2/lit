#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def graph_errors(graph: dict) -> list[str]:
    errors: list[str] = []
    nodes = graph.get("nodes", [])
    ids = [node.get("id") for node in nodes]
    if len(ids) != len(set(ids)):
        seen: set[str] = set()
        for node_id in ids:
            if node_id in seen:
                errors.append(f"DUPLICATE_NODE {node_id}")
            seen.add(node_id)

    node_ids = set(ids)
    dependencies = {node["id"]: node.get("depends_on", []) for node in nodes if node.get("id")}
    for node_id, deps in dependencies.items():
        for dep in deps:
            if dep not in node_ids:
                errors.append(f"UNKNOWN_DEPENDENCY {node_id} -> {dep}")
            if dep == node_id:
                errors.append(f"SELF_DEPENDENCY {node_id}")

    state: dict[str, int] = {}

    def visit(node_id: str, path: list[str]) -> None:
        if state.get(node_id) == 1:
            cycle_start = path.index(node_id) if node_id in path else 0
            errors.append("CYCLE " + " -> ".join(path[cycle_start:] + [node_id]))
            return
        if state.get(node_id) == 2:
            return
        state[node_id] = 1
        for dep in dependencies.get(node_id, []):
            if dep in node_ids:
                visit(dep, path + [node_id])
        state[node_id] = 2

    for node_id in node_ids:
        if state.get(node_id, 0) == 0:
            visit(node_id, [])
    return errors


def transitive_dependents(graph: dict, changed: set[str]) -> set[str]:
    reverse: dict[str, set[str]] = {}
    for node in graph.get("nodes", []):
        for dep in node.get("depends_on", []):
            reverse.setdefault(dep, set()).add(node["id"])

    stale = set(changed)
    queue = deque(changed)
    while queue:
        node_id = queue.popleft()
        for dependent in reverse.get(node_id, set()):
            if dependent not in stale:
                stale.add(dependent)
                queue.append(dependent)
    return stale


def validate_graph_file(path: Path, schema_path: Path | None = None) -> tuple[dict, list[str]]:
    graph = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema_path = schema_path or ROOT / "schemas/dependency_graph.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = [
        f"GRAPH_SCHEMA {'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(graph)
    ]
    if not errors:
        errors.extend(graph_errors(graph))
    return graph, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dependency DAG and calculate stale dependents.")
    parser.add_argument("graph", type=Path, nargs="?", default=ROOT / "config/dependency_graph.yaml")
    parser.add_argument("--changed", action="append", default=[])
    args = parser.parse_args()

    graph, errors = validate_graph_file(args.graph)
    if errors:
        print("DEPENDENCY_GRAPH: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"DEPENDENCY_GRAPH: PASS nodes={len(graph['nodes'])}")
    if args.changed:
        node_ids = {node["id"] for node in graph["nodes"]}
        unknown = sorted(set(args.changed) - node_ids)
        if unknown:
            print("DEPENDENCY_GRAPH: FAIL")
            for node_id in unknown:
                print(f"- UNKNOWN_CHANGED_NODE {node_id}")
            return 1
        stale = sorted(transitive_dependents(graph, set(args.changed)))
        print("STALE_NODES: " + ",".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
