# How Continuity addresses Track 2

Source checked 18 October 2026: [official event](https://www.wemakedevs.org/hackathons/falkordb).
These are feature mappings, not claims about organizer judging scores.

| Track focus | Implementation | Evidence |
|---|---|---|
| Persistent conversations | Sourced successful chat turns and messages in FalkorDB | Reloaded AppTest, fresh-process recall |
| Semantic memory | Current user/entity facts and versioned corrections | Natural-message extraction + correction checks |
| Episodic memory | User-reported event memories and timestamped turns | Isolated memory-type tests |
| Procedural memory | Reusable user routines; separately approved task procedures | Memory-type + existing procedure guards |
| Shared state/handoffs | Assistant, Planner and Helper read common facts; saved task handoff | Live eight-check scenario |
| Concurrent reads/writes | Optimistic atomic commits, operation receipts, conflict checks | Concurrent independent writes, conflicting corrections, claim/budget tests |
| Separate users/tenants | Tenant graph and per-project query scope | Cross-project/tenant integration tests |
| FalkorDB central to product | Current-memory/entity/source traversals feed generation; evidence IDs persist | Projection/query integration checks |

The frontend is Streamlit; a ChatGPT-like product is not an event requirement.
Natural chat was added because it makes the memory useful and testable.

Prototype limits: selector-based profiles are not authentication. Whole-project
snapshot/projection commits prioritize correctness and inspectability; high-load
throughput is not proven. Memory extraction and lexical retrieval can miss facts.
The model provides suggestions; people execute work and explicitly report outcomes.
The app is not deployed or submitted. Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for
an honest local demo and [QUICKSTART.md](QUICKSTART.md) for manual testing.
