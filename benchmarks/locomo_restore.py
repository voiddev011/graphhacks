"""Restore a frozen benchmark artifact into a NEW isolated graph, never a user graph."""
import copy
from app.domain import canonical, digest, empty_project
from app.repository import COMMIT, LABELS, RELATIONSHIPS, projection


def restored_state(project, artifact):
    allowed = {"messages", "memory_slots", "memory_versions", "chat_turns"}
    if set(artifact) - allowed:
        raise ValueError("Unexpected frozen memory collections")
    state = empty_project(project)
    state.update(copy.deepcopy(artifact))
    for vid in state.get("memory_slots", {}).values():
        if vid not in state.get("memory_versions", {}):
            raise ValueError("Missing current memory version")
    for vid, fact in state.get("memory_versions", {}).items():
        if fact["id"] != vid:
            raise ValueError("Memory ID mismatch")
        source = fact["source"]
        message = state["messages"][source["message"]]
        turns = message.get("metadata", {}).get("turns", [])
        originals = [t for t in turns if t["dia_id"] == source.get("dialogue_id")]
        if len(originals) != 1 or source.get("passage", "") not in originals[0]["text"]:
            raise ValueError("Frozen memory has invalid transcript source")
        if not fact["value"] or fact["value"].casefold() not in source["passage"].casefold():
            raise ValueError("Frozen value is not grounded in its source")
        if fact.get("supersedes") and fact["supersedes"] not in state["memory_versions"]:
            raise ValueError("Missing historical memory")
    return state


def restore_isolated(store, artifact):
    if not store.tenant.startswith("locomo_"):
        raise ValueError("Restore is restricted to isolated benchmark tenants")
    version, before = store.read_versioned()
    if version != 0 or before != empty_project(store.project):
        raise ValueError("Restore requires a completely empty benchmark project")
    state = restored_state(store.project, artifact)
    nodes, edges = projection(state, store.project)
    params = {"project": store.project, "operation": store.project + ":frozen_restore",
        "expected": 0, "next": 1, "snapshot": canonical(state), "revision": 0,
        "hash": digest(artifact), "result": canonical({"kind": "frozen_benchmark_restore"})}
    params.update({"nodes_"+label: [n for n in nodes if n["kind"] == label] for label in LABELS})
    params.update({"edges_"+rel: [e for e in edges if e["kind"] == rel] for rel in RELATIONSHIPS})
    if not store.graph.query(COMMIT, params).result_set:
        raise ValueError("Frozen restore lost its empty-project guard")
    return state
