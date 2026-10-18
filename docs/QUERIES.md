# Inspect the memory graph

Open the graph printed by `doctor` in FalkorDB Browser. These are read-only demo
queries. The app uses fixed query text with parameters; it never executes model-generated Cypher.

Current decisions and their sources:

```cypher
MATCH (slot:DecisionSlot)-[:CURRENT]->(d:DecisionVersion)-[:FROM_MESSAGE]->(m:Message)
RETURN slot.key, d.data, m.data
```

Correction history:

```cypher
MATCH (new:DecisionVersion)-[:SUPERSEDES]->(old:DecisionVersion)
RETURN new.data, old.data
```

Task prerequisites:

```cypher
MATCH (t:Task)-[:DEPENDS_ON]->(prerequisite:Task)
RETURN t.key, prerequisite.key, prerequisite.data
```

The exact decision versions used by earlier completed work:

```cypher
MATCH (t:Task)-[:HAS_RESULT]->(r:Result)-[:BASED_ON]->(d:DecisionVersion)
RETURN t.key, r.data, d.data
```

Compatibility acceptance preserves the original result:

```cypher
MATCH (review:Review)-[:ACCEPTS]->(r:Result)
MATCH (review)-[:VALIDATED_AGAINST]->(d:DecisionVersion)
RETURN review.data, r.data, d.data
```

Saved handoff inputs:

```cypher
MATCH (h:Handoff)-[:FOR_TASK]->(t:Task)
OPTIONAL MATCH (h)-[:USES_INPUT]->(d:DecisionVersion)
RETURN h.data, t.key, collect(d.data)
```

Rows contain a `data` JSON property for inspectable typed contents. Node business
IDs are stable strings; internal database IDs change when the small projection
is rebuilt. Filter by `project` when inspecting several projects in one tenant graph.
