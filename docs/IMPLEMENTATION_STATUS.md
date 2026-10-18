# Implementation and verification

Continuity runs locally with Python, Streamlit, LangChain, LangGraph and FalkorDB.
It supports sourced conversation memories, corrections, new-thread recall,
and shared Planner/Helper handoffs. NVIDIA Direct, Gemini and OpenRouter are supported.

## Saved evidence

| Check | Actual result | Report in `reports/` |
|---|---|---|
| Full regression before NVIDIA support | 121 passed, 2 skipped | `locomo-full-regression.xml` |
| Affected NVIDIA/routing/benchmark/UI checks | 41 passed | `nvidia-integration-tests.xml` |
| Final NVIDIA-specific checks | 6 passed | `nvidia-provider-tests.xml` |
| Coordination contracts | 14/14 | `scenario-results.json` |
| Live memory and handoff scenario | 8/8 | `final-live-memory-v2.json` |
| Real Streamlit execution checks | 5/5 | `final-live-ui-v3.json` |
| NVIDIA fact-save and new-thread Helper recall | Passed, 2 real calls | `nvidia-live-memory-check.json` |
| NVIDIA provider selector and HTTP health | Passed | `nvidia-ui-check.json` |
| Exact restaurant message: save cuisines and recall in a new thread | Passed, 2 real NVIDIA calls | `restaurant-grounding-live-check.json` |
| Invalid-proposal UI warning and valid fact retained | 2 passed | `chat-grounding-warning-ui-tests.xml` |
| Affected chat, LoCoMo, UI and workflow regression | 86 passed | `chat-grounding-fix-tests.xml` |
| Original LoCoMo scorer parity | 24 comparisons passed | `locomo-scorer-parity.json` |

These checks have different scopes; their counts must not be added into one accuracy score.
AppTest verifies Streamlit execution, not a visual browser screenshot review.

Chat now skips individually ungrounded memory proposals with a visible warning
while preserving grounded facts and the reply. Unknown citations, stale evidence,
and conflicting updates still reject the turn. An assertion ending with a period
is no longer rejected merely because the next sentence is a question.

## Benchmark limits

The LoCoMo pilot tested **8 unique questions**, each with and without memory.
Graph memory: **18.75% token F1 / 37.5% local-judge accuracy**. Baseline: **0% / 0%**.
Answering and judging had no API errors, but the earlier memory import failed
on 3 of 19 chunks and rejected 190 proposals. This is an incomplete-import pilot,
not a full benchmark or a result comparable with Mem0's published score.

See [the results](../reports/LOCOMO_RESULTS.md) and [repeat commands](LOCOMO.md).
The NVIDIA smoke checks did not rerun or improve those benchmark scores.

## Prototype limits

Profiles are selectors, not authentication. Models can miss facts; retrieval is
bounded lexical/entity selection. Whole-project graph/snapshot commits suit
small projects. The agents suggest work; people execute it. High-load operation,
public deployment and independent verification of user claims are not demonstrated.

Use [the recording script](DEMO_SCRIPT.md) for the working demo. No automated
commit, push, repository-visibility change or hackathon submission was performed.
