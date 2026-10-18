# What exists and what has been checked

Implementation session: 18 October 2026. This records actual code and executed
checks, separately from the larger specification.

## Implemented

- Terminal app with synthetic tenant/project selectors, seed data, history,
  typed decisions, tasks, approved procedures, Planner/Helper, review and release.
- Explicit LangGraph workflow with bounded LangChain/Gemini structured responses.
- Decision versions with exact user sources; earlier versions remain in history.
- Declared prerequisites and technical inputs; affected completed results require
  review when a decision changes. Confirm, reopen and replacement resolutions exist.
- Durable request/handoff/claim schema; final input/version checks; stale drafts
  and outcomes retained without accepting stale completion.
- Scoped operation hashes, immutable accepted envelopes and original-receipt replay.
- Persisted three-attempt request budget, including failed provider calls; each
  dispatch reserves its own slot. Reads/rule checks require zero model calls.
- FalkorDB repository, graph evidence traversal and conditional single-query commit.
- Docker Compose with localhost bindings, named volume and AOF configuration.
- Streamlit browser interface: task dashboard, Planner/Helper, readable drafts,
  reported completion, decision history, procedure approval, claim release and review.
- Fourteen isolated synthetic contract checks, available through the UI and CLI.
- Experimental original-LongMemEval-format conversation adapter with graph, BM25,
  full-history and no-memory modes, call budgets, traces and judge-log aggregation.

## Executed locally

Python **3.13.9**, in project-local `.tools/python`; packages are frozen in
`requirements.lock`. This does not install Python system-wide.

```powershell
$env:PYTHONNOUSERSITE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.\.tools\python\python.exe -m pytest -q --junitxml=reports/unit-results.xml
.\.tools\python\python.exe -m app.demo
.\.tools\python\python.exe -m compileall -q app tests
.\.tools\python\python.exe -m pip check
```

Original offline run: **25 passed, 25 skipped, 0 failed**.
Database-enabled run: **49 passed, 1 skipped, 0 failed**. That run skipped the live Gemini case. A later explicit live run failed with
`504 DEADLINE_EXCEEDED`; Google model lookup recognized the configured key/model.
Checks now run against both the **RAM adapter and real FalkorDB**, using scripted models.
They cover correction history, three review resolutions, prerequisites, unrelated
changes, controlled changes during generation, stale claim ownership, idempotent
replay/hash conflict, failed-write replay, malformed output and call budgeting.
The SDK retry configuration is checked against the actual installed package.
See `reports/unit-results.xml`, `reports/database-results.xml`,
`reports/persistence-results.json` and `reports/manifest.json` for evidence.
Compilation completed successfully; `pip check` reported **No broken requirements found**.
The offline walkthrough and command-line help both ran successfully.

## Integration status

| Gate | Actual status |
|---|---|
| FalkorDB query execution and guarded commits | Contract suite passed on the real server, including races/replay; not a general concurrency proof |
| User/project isolation and graph traversal on server | Scoped integration test passed; local selectors remain unauthenticated |
| Fresh-process graph retrieval | Integration test passed |
| Graceful database restart | Exact logical state hash retained; fresh-process Helper resumed saved handoff |
| Container replacement with retained volume | Exact logical state hash retained after `--force-recreate` |
| AOF/volume configuration | Observed `/data`, `appendonly=yes`, `appendfsync=everysec`; `/data` is mounted |
| Docker image and digest | Published v4.22.1 pulled and healthy; registry digest pinned in Compose |
| Live Gemini output, grounding, quota and latency | Key/model lookup passed; two generation smoke attempts returned 504 deadline errors. Live generation is not verified. |
| FalkorDBSaver workflow checkpoints | Deferred; fresh-session business handoffs are the intended fallback |
| External memory benchmarks and load tests | Deferred; no score or production performance claim |
| Public deployment, demo video, hackathon submission | Not performed |

Docker Desktop is installed and the project database is running. A service on host
port 6379 rejected `GRAPH.QUERY`, so Compose and `.env` use **6380**.
The user has configured `.env`; keep its key private and do not publish it.
The graph browser responded with HTTP 200 at `http://localhost:3000`.
`docker.ps1` locates Docker Desktop even when the terminal PATH has not refreshed.

## Prototype design choices

For the tiny fixtures, each project has a canonical JSON snapshot and connected
typed graph records. One optimistic compare-and-swap query commits that snapshot,
its graph projection and operation receipt. The service retries conflicting writes
against fresh state; only relevant business inputs invalidate work. Helper retrieves
connected decision and prerequisite evidence through actual graph paths.

This differs from a fully normalized graph-only implementation: the projection
is rebuilt per transition, so stable business IDs matter and internal node IDs do
not survive. The real-server contract suite verifies the current small scenarios;
this design is for the small demo, not growing production data.

Memory writes are explicit typed commands. General natural-language extraction,
observed execution tools and authentication are not implemented. The conversational
benchmark adapter is a separate experimental raw-history retrieval extension, not
general fact extraction in the task service. Outcomes
are labeled **user-reported**, and AI drafts never establish task completion.

## Next manual setup

Docker and synthetic demo data are ready. To check or start the local database:

```powershell
.\docker.ps1 compose up -d --wait
.\run.ps1 doctor
.\run.ps1 seed
$env:CONTINUITY_DB_TESTS = '1'
.\.tools\python\python.exe -m pytest -q
```

Then follow the persistence and live-model gates in [README.md](README.md).
Stop on any server test failure and fix it before claiming the app is ready to submit.

## Earlier live-test issue

The key and `gemini-3.8-flash` were recognized by a short Google model lookup.
Generation returned `504 DEADLINE_EXCEEDED` at both 45-second and 90-second
request limits. The adapter now requests low thinking for Gemini 3 models and
allows 90 seconds, with no hidden retries. The CLI explains deadline errors
without printing the key. See `reports/live-results.xml`; this is a failed
live test, not a passing end-to-end result.

## Streamlit and evaluation update

- The user subsequently demonstrated successful live Planner and Helper commands
  and a successful graceful database restart in their pasted terminal output.
- Streamlit 1.66.0 is installed in the isolated runtime; `ui.ps1` serves localhost:8501.
  Root and health routes responded with HTTP 200. AppTest exercised the actual widgets
  with scripted models and both RAM/FalkorDB backends; no browser screenshot was taken.
- Expanded full suite: **64 passed, 2 skipped**. The skips are the opt-in older live
  model test and a graph-only test on the RAM fixture. See `reports/ui-database-results.xml`.
- A later focused UI/adapter suite checks the final retrieval indexes, ordering and UI
  notice changes; see `reports/ui-adapter-final.xml` for the executed result.
- The 14 deterministic project checks passed on FalkorDB, with zero model calls.
- Three bundled synthetic cases completed a graph-retrieval dry run with zero calls.
- One bundled synthetic correction question completed a live Gemini answer with
  citations. The answer matched the fixture on manual inspection; no official judge
  or numeric public-benchmark score was produced.
- The complete external dataset, cross-model quality comparison and V2 leaderboard
  integration/submission remain unperformed. See `BENCHMARKS.md` for reproducible steps.

The first expanded pytest run hit Windows temporary-directory permissions.
Pytest now uses `.tools/pytest-temp` inside the workspace; the corrected full run passed.

## Live-only correction

The user requested removal of fake/static content from the live app. The live
UI and CLI now use Gemini only: no sample-loading buttons, scripted switch,
seed command or demo flag. Projects start empty. A user-entered task creates a
real task record and a focused live Planner request before Helper continuation.

Only known seeded Apollo data was cleared, after a private `.local-backups/`
export and a conditional storage-version check. No custom tasks were present.
`apollo` and the new default `my_project` were checked for zero tasks, messages
and handoffs. Automated test fixtures/model doubles remain under `tests/` only;
fixed checks moved to the developer command `benchmarks.contracts`. The app's
benchmark page no longer loads canned conversations.

The corrected full suite passed **65 tests, with 2 intentional skips**. Evidence:
`reports/live-only-results.xml`. The live smoke result is recorded separately in
`reports/live-only-smoke.json` when completed. Earlier sample-based walkthroughs
and results above are historical; the current walkthrough is QUICKSTART.md.
