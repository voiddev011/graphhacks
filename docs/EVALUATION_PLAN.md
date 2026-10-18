# Continuity evaluation: submission checks first, broader research later

Revised specification: 18 October 2026. **Core rule/workflow checks now run;
real database contract checks, Streamlit interaction tests and graceful restart passed.
Live manual task flows and one synthetic QA pilot worked; a full public benchmark,
checkpoint and load results remain unverified.** See
[PROJECT_PLAN.md](PROJECT_PLAN.md) for the contracts and [event facts](HACKATHON_BRIEF.md).
Actual evidence is recorded in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md),
`reports/ui-database-results.xml` and `reports/scenario-results.json`.
See [benchmark run instructions](BENCHMARKS.md) for the new experimental adapter.
The case families below are release targets;
passing RAM-adapter checks do not establish their database integration gates.

## Priorities and evidence

- **Submission-critical:** a small deterministic database suite plus several real-model cases.
- **Conditional integration gate:** checkpoint compatibility; failure activates the documented fresh-session fallback.
- **Extended roadmap:** historical queries, broad recall, benchmark adapters, lease reassignment, and load campaigns.

The public event pages reviewed prescribe no benchmark or numeric passing score.
These are our proposed engineering release gates, not organizer judging weights.
Use real database checks for state invariants. Scripted models help force race and
failure paths; they do not prove live extraction or grounded-answer quality.

Freeze synthetic fixtures before prompt tuning. Keep expected answers, source/evidence
labels, and expected graph states outside model inputs. Use two synthetic users
and two projects with different values. A distinctive user-B marker such as
`violet_bridge_72` must never enter A's context. Record per-case status as proposed,
implemented, or verified, with the actual command, date, and output for verified rows.

## Submission-critical suite

Each row is a case family; parameterize only the variations needed to establish
its contract. No large throughput run or external dataset is needed for these checks.

| ID | Scenario | Required result |
|---|---|---|
| C01 | Fresh process and persistent storage | Save a sourced decision; stop/start application; retrieve it in a fresh Helper session. Separately check a graceful DB restart without deleting the volume. |
| C02 | Correction and provenance | Latest typed version is current; earlier value/source is retained; assistant suggestion alone cannot overwrite it. |
| C03 | User/project separation | Other-user and other-project decisions, messages, tasks, handoffs, and checkpoint records are excluded; foreign referenced IDs are rejected. |
| C04 | Prerequisite validity | Pending or review-required prerequisites block downstream eligibility; accepted valid prerequisites permit it. |
| C05 | Durable handoff | Planner saves task/objective/input bundle; a fresh Helper process loads and validates it without old chat. |
| C06 | Decision impact on completed work | React-to-Streamlit change flags the declared interface result for review and blocks deployment; original work remains in history. Test each explicit user resolution. |
| C07 | Unrelated changes | New chat, response-style edit, independent task outcome, and saving/claiming the handoff do not cause false invalidation. Watermark may change; relevant bundle remains valid. |
| C08 | Change during generation | Hold Helper generation, change a required decision/procedure/prerequisite, then try completion. Preserve draft as stale attempt; no accepted completion; request replanning. |
| C09 | Same-operation replay | Commit then lose response; retry same scoped ID/hash or replay saved command. Return original receipt, with one logical effect and no extra version bump. |
| C10 | ID reused with different payload | Same scoped ID and altered normalized payload returns explicit conflict; graph state and old receipt stay unchanged. |
| C11 | Duplicate claims | Two service clients/threads claim the same pending task; exactly one succeeds. Explicit release changes version and prevents old claim completion. No automatic expiry is claimed. |
| C12 | Missing evidence and failed writes | Unknown references, speculative updates, malformed output, DB errors, and missing completion evidence do not produce invented memories or false success. |
| C13 | Procedure and outcome truthfulness | Only approved current procedure is used; approval is not execution; assistant draft, user-reported outcome, and observed result retain different provenance. |
| C14 | Model/request budget | Pure reads/checks use no model call; normal planning/helping uses one generation; extraction/repair/retries share the hard total provider-attempt cap. Exhaustion is reported honestly. |

### Controlled race tests

For C08, synchronize generation with a test barrier rather than an unreliable sleep:
load/claim, pause the generation stub, commit a relevant change, release the stub,
and run the final guarded transition. Repeat for a prerequisite review-state change
and an approved procedure change. These tests need no live model latency.

For C11, release two claim attempts together. Assert owner count, task version,
operation receipts, and conflict result. Small race checks establish finite
correctness evidence, not production-scale concurrency.

Also inject a failed conditional write and a lost response. Inspect actual graph
state; mocked errors are not the same as a database process crash. Do not broaden
failure testing until the core vertical slice works.

## Required decision-impact fixture

Use invented data and explicit dependency declarations:

1. Project Apollo has `interface_framework = React`, decision version D1.
2. Task interface is declared to require that decision. Its accepted result R1 is
   completed, review-valid, and BASED_ON D1. Save the source/outcome provenance.
3. Task deploy depends on task interface. A separate documentation task is independent.
4. User explicitly changes interface_framework to Streamlit, creating D2.
5. Assert D1 and R1 remain; R1 requires review; interface prerequisite is unsatisfied;
   deploy cannot be chosen. Do not label the implementation technically wrong.
6. On separate clean fixture copies, test all resolutions: user confirms R1 remains
   valid under D2, reopens interface, or creates a replacement with explicit dependency
   rewiring. Preserve original BASED_ON links and record review evidence.
7. Confirmation can unblock deploy if other prerequisites pass; reopening/replacement
   keeps deploy blocked until newly valid work is accepted.
8. In a separate control, change only response_style. Interface result stays valid;
   an otherwise valid handoff remains usable. The response can use the new style.

Assert record IDs, versions, review state, declared inputs, and exact eligible-task
sets in code. A compatibility confirmation records a user's judgment, not an observed
rebuild using Streamlit.

## Checkpoint compatibility gate and fallback

With the actual installed `langchain-falkordb`, LangGraph, checkpoint, and driver
versions pinned, test:

1. Save workflow state, exit application, and restore the same thread.
2. Separate tenant graphs and threads with distinct marker values.
3. Change a relevant decision after save, then restore: stored evidence must be
   refreshed before generation/action, and checked again at completion.
4. Lose a checkpoint response after a business commit: replay loads stable request
   and accepted operation IDs without duplicating the business effect.

Timebox the gate. If incompatible, verify durable business facts/handoffs and fresh
conversation resumption, then mark arbitrary workflow checkpoint recovery deferred.
Never report InMemorySaver as persistent. No cross-graph atomicity is assumed.
Reference: [official integration](https://github.com/FalkorDB/langchain-falkordb).

## Several real-model checks

Run a small fixed set after deterministic storage checks pass:

- Extract an explicit allowed decision with its exact source passage.
- Distinguish "maybe change" from a confirmed correction.
- Planner selects an eligible task and cites the supplied records.
- Helper uses the approved procedure and relevant prior attempt without inventing execution.
- Missing evidence produces a focused question or honest limitation.

Inspect returned structured fields, evidence, actual database state, and displayed
answer. Record all failures and repeats, not only the best output. Use held-out
paraphrases/values. Token/model limits may make a case incomplete; report that.
Citation resolution checks IDs/scope, while human review checks whether the cited
source actually supports the claim.

## Metrics and finite release gates

| Measure | Definition and reporting |
|---|---|
| Core correctness | Passing applicable critical cases / executed critical cases; release-blocking failures remain visible |
| Separation | Foreign records in returned evidence/model context; target zero in this finite suite |
| Impact correctness | Correct review-required result set and exact downstream eligibility; include unrelated-change controls |
| Stale completion | Accepted stale results in controlled races; target zero |
| Claims/replay | Multiple owners, duplicate effects, or wrong-hash acceptance; target zero |
| Grounded answer quality | Correct answers with supported sources / evaluated live cases; report counts, not invented percentages |
| Abstention | Correct unknown answers and false refusals; report both |
| Calls/cost | Generation/extraction/repair attempts including retries, tokens when available, account model ID/settings |
| Latency | Per-case graph retrieval and live-turn time separately; percentile claims only with adequate sample counts |

Inspect the actual Gemini API project's quotas before configuring rate limits.
Count every provider attempt against the request-wide cap, including SDK retries.
Do not call the model to compute eligibility, validity, graph writes, or these metrics.

## Fair retrieval comparisons

Optional once the core is stable: compare recent-history, flat-retrieval, and
connected-retrieval modes with the same model, source corpus, user/project scope,
current-version filtering, context ceiling, generation settings, and scoring rubric.
The no-persistent-memory baseline intentionally omits past context and must be
labeled that way; it is not the comparison that isolates graph traversal.

Flat retrieval keeps relationship facts available as text/triples rather than being
artificially denied source information. Use separate reset state per mode and matched
histories. Hide expected answers/evidence annotations from ingestion, retrieval, and
generation. Report source retrieval separately from final-answer quality.

The deterministic task controller gets its own exact-state tests in every mode;
do not disable its guards to make another retrieval mode look worse. A QA comparison
is not a benchmark of task ownership or decision-impact correctness.

## Full evaluation roadmap: coverage of the earlier 24 cases

Keep this roadmap, but do not run all extensions before submitting.

| Earlier ID | Coverage | Priority |
|---|---|---|
| 01 Fresh-session recall | C01/C05 | Critical |
| 02 Fresh-process recall | C01 | Critical |
| 03 Database restart | C01, graceful restart with retained volume | Critical |
| 04 Correction | C02 | Critical |
| 05 Historical-time questions | General valid-time and backdated semantics | Deferred |
| 06 Project-scoped preference | C03 | Critical |
| 07 User-wide fallback | Global-to-project inheritance | Deferred |
| 08 Duplicate request | C09/C10, payload identity strengthened | Critical |
| 09 Simultaneous corrections | Expected-version write conflict; extend C08/C11 | Next correctness extension |
| 10 Ambiguous update | C02/C12 and live cases | Critical |
| 11 Missing information | C12 and live cases | Critical |
| 12 Episodic recall | C13 and Helper live case; broad search later | Narrow critical scope |
| 13 Procedure reuse | C13 | Critical |
| 14 Unapproved procedure | C13 | Critical |
| 15 Blocked task | C04 | Critical |
| 16 Dependency change | C04/C06, including decision impact | Critical |
| 17 Saved handoff | C05 | Critical |
| 18 Stale handoff | C07/C08 plus checkpoint gate | Critical |
| 19 Duplicate claims | C11 | Critical |
| 20 Lease recovery | Automatic expiry/reassignment with fencing and multi-worker tests | Deferred; explicit release only initially |
| 21 User isolation | C03 | Critical |
| 22 Scope tampering | C03/C12 | Critical |
| 23 Evidence/tool failure | C12 | Critical |
| 24 Crash/replay | C09; checkpoint gate if enabled | Critical within the declared durability limits |

Future failures to examine: write interruption, checkpoint interruption, hard database
crash, scope access after a public auth boundary, broad paraphrase retrieval, and
larger histories. State exact environment and AOF policy. A graceful restart cannot
establish zero-loss power-failure durability.

## External memory benchmarks: optional and off the critical path

[Original LongMemEval](https://github.com/xiaowu0162/LongMemEval) covers extraction,
multi-session reasoning, updates, time reasoning, and abstention. A future adapter
can use the cleaned S release. A separate experimental adapter now imports raw
timestamped sessions and retrieves lexical graph neighborhoods. General fact
extraction is still outside the typed task controller; a complete S run is unperformed.

Preserve the earlier protocol as a research plan:

1. Measure one or two complete-instance runs before committing to cost/time.
2. Optionally freeze a stratified 25-instance subset including unknown-answer items;
   save selected IDs, dataset revision/checksum, and selection rule.
3. Use fresh isolated state; ingest timestamped history chronologically. Archive
   speakers distinctly and do not treat assistant suggestions as user-confirmed facts.
4. Keep gold answers, answer-session IDs, `has_answer`, and task-type hints strictly
   in the evaluator, outside all application inputs.
5. Ask the question in a fresh thread with its given date; retain full non-oracle
   histories and record selected context, model settings, calls, tokens, errors, and timing.
6. Produce `question_id`/`hypothesis` JSONL and use the reference evaluator. Disclose
   changed judges/manual scoring and every other protocol deviation.
7. Label a subset as a subset. Oracle evidence is a separate reader diagnostic,
   not measured retrieval. Truncated histories are an adapted test, not a standard score.
8. Use validated ingestion snapshots for fair read-only comparisons where possible;
   do not let tuning use held-out answers. Expand only within remaining time/budget.

[LoCoMo](https://github.com/snap-research/locomo) remains a possible second long-chat
QA check. [LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2) targets
agent-trajectory experience and requires a different adapter. Follow each official
release's permissions, inputs, categories, and scorer. These benchmarks do not
validate our handoffs, claims, or review transitions.

Three bundled synthetic format examples were imported in a dry run; one was
answered by live Gemini. No official external dataset or judge score is claimed.

## Load campaign: deferred roadmap

After the submission, record hardware, graph sizes, process count, pool settings,
and pinned versions. Warm up and test 100 operations at 1, 5, and 10 clients, then
repeat if justified. Separate graph-only reads; 80/20 read/write mixes within one
and across ten tenants; and same-record conflict races. Report actual completions,
conflicts, errors, timeouts, duplicates, missing effects, throughput, and p50/p95.
Keep LLM generation out of graph-only measurements; report live turns separately.
Ten clients are not proof of production scale. Automatic reassignment requires
claim fencing and multi-process checks before it can be advertised.

## Delivery artifacts and demo

Proposed artifacts after implementation:

```text
tests/fixtures/                 # small frozen synthetic scenarios
reports/manifest.json           # git SHA, versions, container digest, environment
reports/core-checks.json        # actual executed checks and results
reports/live-cases.jsonl        # structured outputs, evidence, budget, honest failures
reports/notes.md                # deferred behavior, checkpoint gate, deviations
# Only if an optional benchmark is run:
eval/selected_question_ids.json
reports/predictions.jsonl
reports/metrics.json
```

Reserve submission time. A suggested 3-4 minute demo, not an official video limit,
shows the completed React interface, changed Streamlit decision, blocked deployment,
explicit review resolution, durable handoff, fresh Helper resumption, user separation,
and actual test results. Include assistant-use disclosure and explain the queries.
Label implemented and verified features from repository evidence; never show proposed
checks as passing results.
