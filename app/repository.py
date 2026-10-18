"""FalkorDB persistence with a whole-project optimistic concurrency guard.

The small demo keeps a canonical JSON snapshot AND its browsable graph projection.
One conditional Cypher query commits snapshot, projection and operation receipt.
The internal storage version guards ALL intervening writes; the domain retries
against fresh state and compares only relevant inputs, never global revision.
This deliberately trades scaling for an auditable single-project atomic boundary.
"""
from __future__ import annotations

import copy
import json
import os
import threading

from .domain import Rejected, canonical, digest, empty_project, identifier, transition


def projection(state, project_key):
    nodes, edges = [], []

    def node(kind, key, content):
        nid = f"{project_key}:{kind}:{key}"
        nodes.append({"id": nid, "kind": kind, "key": key, "data": canonical(content)})
        return nid

    def edge(kind, a_kind, a, b_kind, b):
        if a is not None and b is not None:
            edges.append({"kind": kind, "a": f"{project_key}:{a_kind}:{a}", "b": f"{project_key}:{b_kind}:{b}"})

    for kind, collection in [("Message", "messages"), ("DecisionVersion", "versions"),
                              ("Task", "tasks"), ("Result", "results"), ("Review", "reviews"),
                              ("Handoff", "handoffs"), ("Attempt", "attempts"),
                              ("Procedure", "procedure_versions"), ("Request", "requests")]:
        for key, value in state.get(collection, {}).items():
            node(kind, key, value)
    for key, did in state["decisions"].items():
        node("DecisionSlot", key, {"key": key, "current": did})
        edge("CURRENT", "DecisionSlot", key, "DecisionVersion", did)
    for did, d in state["versions"].items():
        edge("SUPERSEDES", "DecisionVersion", did, "DecisionVersion", d["supersedes"])
        edge("FROM_MESSAGE", "DecisionVersion", did, "Message", d["source"]["message"])
    for tid, t in state["tasks"].items():
        for dep in t["prerequisites"]:
            edge("DEPENDS_ON", "Task", tid, "Task", dep)
        for key in t["requires"]:
            # A slot exists even before a value is chosen.
            if key not in state["decisions"]:
                node("DecisionSlot", key, {"key": key, "current": None})
            edge("REQUIRES_DECISION", "Task", tid, "DecisionSlot", key)
        edge("REPLACES", "Task", tid, "Task", t.get("replaces"))
    for rid, r in state["results"].items():
        edge("HAS_RESULT", "Task", r["task"], "Result", rid)
        edge("FROM_MESSAGE", "Result", rid, "Message", r["source"]["message"])
        for did in r["based_on"].values():
            edge("BASED_ON", "Result", rid, "DecisionVersion", did)
    for rid, r in state["reviews"].items():
        edge("ACCEPTS", "Review", rid, "Result", r["result"])
        edge("FROM_MESSAGE", "Review", rid, "Message", r["source"]["message"])
        for did in r["validated_against"].values():
            edge("VALIDATED_AGAINST", "Review", rid, "DecisionVersion", did)
    for hid, h in state["handoffs"].items():
        edge("FOR_TASK", "Handoff", hid, "Task", h["bundle"]["task"])
        for did in h["bundle"]["decisions"].values():
            edge("USES_INPUT", "Handoff", hid, "DecisionVersion", did)
        for proc in h["bundle"]["procedures"].values():
            edge("USES_PROCEDURE", "Handoff", hid, "Procedure", proc)
    for aid, a in state["attempts"].items():
        edge("HAS_ATTEMPT", "Task", a["task"], "Attempt", aid)
    for pid, proc in state.get("procedure_versions", {}).items():
        edge("FROM_MESSAGE", "Procedure", pid, "Message", proc["source"]["message"])
    # Repeated empty slots from multiple tasks are one graph record.
    return list({n["id"]: n for n in nodes}.values()), edges


LABELS = ("Message", "DecisionSlot", "DecisionVersion", "Task", "Result", "Review", "Handoff", "Attempt", "Procedure", "Request")
RELATIONSHIPS = ("CURRENT", "SUPERSEDES", "FROM_MESSAGE", "DEPENDS_ON", "REQUIRES_DECISION", "REPLACES", "HAS_RESULT", "BASED_ON", "ACCEPTS", "VALIDATED_AGAINST", "FOR_TASK", "USES_INPUT", "USES_PROCEDURE", "HAS_ATTEMPT")

# Only fixed names from the lists above enter query text. All user data is params.
COMMIT = """
MATCH (p:Project {id: $project})
OPTIONAL MATCH (o:Operation {id: $operation})
WITH p, o WHERE p.storage_version = $expected AND o IS NULL
OPTIONAL MATCH (old:Record {project: $project})
WITH p, collect(old) AS old_nodes
FOREACH (n IN old_nodes | DETACH DELETE n)
SET p.snapshot = $snapshot, p.storage_version = $next, p.revision = $revision
CREATE (receipt:Operation {id: $operation, project: $project, hash: $hash, result: $result})
MERGE (p)-[:HAS_OPERATION]->(receipt)
""" + "\n".join(
    f"FOREACH (row IN $nodes_{label} | CREATE (n:Record:{label} {{id: row.id, project: $project, key: row.key, data: row.data}}) CREATE (p)-[:{'HAS_TASK' if label == 'Task' else 'CONTAINS'}]->(n))"
    for label in LABELS
) + "\n" + "\n".join(
    f"FOREACH (row IN $edges_{kind} | MERGE (a:Record {{id: row.a}}) MERGE (b:Record {{id: row.b}}) MERGE (a)-[:{kind}]->(b))"
    for kind in RELATIONSHIPS
) + "\nRETURN p.storage_version"


class FalkorStore:
    def __init__(self, tenant, project):
        from falkordb import FalkorDB
        identifier(tenant)
        identifier(project)
        self.project = project
        self.tenant = tenant
        # Hash hides raw synthetic usernames in graph names; this is not authentication.
        self.graph_name = "continuity_" + digest(tenant)[:24]
        self.graph = FalkorDB(host=os.getenv("FALKOR_HOST", "localhost"),
                              port=int(os.getenv("FALKOR_PORT", "6380")),
                              username=os.getenv("FALKOR_USERNAME") or None,
                              password=os.getenv("FALKOR_PASSWORD") or None,
                              ssl=os.getenv("FALKOR_SSL", "false").lower() == "true",
                              socket_connect_timeout=5, socket_timeout=15).select_graph(self.graph_name)
        self.graph.query("MERGE (p:Project {id: $id}) ON CREATE SET p.snapshot = $snapshot, p.storage_version = 0, p.revision = 0",
                         {"id": project, "snapshot": canonical(empty_project(project))})

    def read_versioned(self):
        rows = self.graph.ro_query("MATCH (p:Project {id: $id}) RETURN p.storage_version, p.snapshot", {"id": self.project}).result_set
        if len(rows) != 1:
            raise Rejected("Expected exactly one scoped project record.")
        return rows[0][0], json.loads(rows[0][1])

    def read(self):
        return self.read_versioned()[1]

    def task_context(self, task_id):
        # Actual graph traversal supplies the Helper's connected evidence.
        # Snapshot and graph evidence are read in the SAME query/snapshot.
        task_key = f"{self.project}:Task:{task_id}"
        rows = self.graph.ro_query("""
          MATCH (p:Project {id: $project})
          MATCH (t:Task {id: $task})
          OPTIONAL MATCH (t)-[:REQUIRES_DECISION]->(:DecisionSlot)-[:CURRENT]->(d:DecisionVersion)
          WITH p,t,collect(DISTINCT d.data) AS decisions
          OPTIONAL MATCH (t)-[:DEPENDS_ON*1..16]->(dep:Task)
          RETURN p.snapshot,t.data,decisions,collect(DISTINCT dep.data)
        """, {"project": self.project, "task": task_key}).result_set
        if len(rows) != 1:
            raise Rejected("Task evidence not found in this scoped project graph.")
        snapshot, task, decisions, deps = rows[0]
        return json.loads(snapshot), {"task": json.loads(task),
                                     "decisions": {json.loads(d)["key"]: json.loads(d) for d in decisions if d is not None},
                                     "prerequisites": [json.loads(d) for d in deps if d is not None]}

    def execute(self, kind, payload, operation_id):
        for _ in range(12):
            version, before = self.read_versioned()
            after, receipt, changed = transition(before, kind, payload, operation_id)
            if not changed:
                return receipt
            nodes, edges = projection(after, self.project)
            params = {"project": self.project, "operation": f"{self.project}:{kind}:{operation_id}",
                      "expected": version, "next": version + 1, "snapshot": canonical(after),
                      "revision": after["revision"], "hash": digest(payload), "result": canonical(receipt)}
            params.update({"nodes_" + label: [n for n in nodes if n["kind"] == label] for label in LABELS})
            params.update({"edges_" + rel: [e for e in edges if e["kind"] == rel] for rel in RELATIONSHIPS})
            if self.graph.query(COMMIT, params).result_set:
                return receipt
            # CAS conflict: recompute validity from new state, preserve accepted payload/ID.
        raise Rejected("Project is busy; retry the SAME operation ID and payload.")


class MemoryStore:
    """Thread-safe TEST adapter. Explicitly not persistent and not the app default."""
    def __init__(self, project="apollo"):
        self.state = empty_project(project)
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def execute(self, kind, payload, operation_id):
        with self.lock:
            self.state, receipt, _ = transition(self.state, kind, payload, operation_id)
            return receipt

    def task_context(self, task_id):
        from .domain import required
        s = self.read()
        t = required(s["tasks"], task_id)
        return s, {"task": t, "decisions": {k: s["versions"][s["decisions"][k]] for k in t["requires"]},
                   "prerequisites": [s["tasks"][k] for k in t["prerequisites"]]}
