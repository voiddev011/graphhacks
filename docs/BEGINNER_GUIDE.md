# Continuity: a beginner's guide to the code and a hands-on lab

This guide describes the code in this folder, inspected on 18 October 2026.
Read parts 1–3 first, try the lab in part 5, then return to the function reference.

## 1. What are we building?

Imagine working with two assistants who share a project notebook.

- **Planner** chooses a task that is ready and saves an objective plus the inputs it used.
- **Helper** opens that saved plan, retrieves the relevant project information, and suggests steps.
- **You** perform the steps and report the outcome.
- **Memory** keeps decisions, their sources, tasks, plans, drafts, outcomes, and history.

Example: you chose React for an interface. You finish some interface work. Later you
change the choice to Streamlit. The system keeps the old React decision, makes
Streamlit current, and flags the earlier result for review. It will not silently
assume that work done for React is suitable for Streamlit.

Planner and Helper are two roles in one workflow. They are not two independently
running robots. Both use the same model adapter with different instructions.
They have no terminal, code editor, deployment tool, or autonomous execution loop.

The UI itself uses Streamlit. The remembered `interface_framework` choice describes
the example project you are tracking; changing it does not rewrite Continuity's UI.

## 2. Vocabulary before reading Python

| Code word | Plain meaning |
|---|---|
| Variable | A name holding a value, such as `role = "planner"` |
| String | Text in quotes |
| List | An ordered collection: `["interface", "storage"]` |
| Dictionary (`dict`) | Labeled values: `{"status": "pending"}` |
| `s["tasks"]` | Read the value labeled `tasks` from dictionary `s` |
| `def` | Define a reusable function |
| `return` | Send a function's result back to its caller |
| Class | A definition for objects that group data and functions |
| `self` | The particular object whose method is running |
| Import | Bring code from another module into this file |
| `if` / `elif` / `else` | Choose which branch to execute |
| `for` | Repeat over items |
| `raise` | Stop the current operation with an error |
| `try` / `except` | Attempt something and handle an error |
| JSON | A text format for dictionaries, lists, strings, and numbers |
| API | A way for programs to communicate; here Python calls Gemini |
| Database | Storage that can survive closing Python |
| Graph | Records connected by named relationships |
| State / snapshot | The project's recorded information at one moment |
| Payload | The data submitted for a command |
| Receipt | A saved answer saying what an operation did |
| Handoff | A saved plan with the exact inputs behind it |
| Claim | A record saying a Helper has taken a task |
| Prerequisite | Work that must be validly completed before another task starts |
| Schema | The shape and constraints an answer must satisfy |
| Adapter | Code that gives different systems the same interface |

`from __future__ import annotations` supports Python type annotations without
immediately evaluating all referenced types. An annotation such as `role: str`
documents the expected type; ordinary annotations alone do not validate input.
Pydantic models perform actual runtime validation here.

## 3. The whole journey through the files

```text
You click Create plan in streamlit_app.py
    -> actions.workflow() in app/actions.py
    -> build(...).invoke(...) in app/workflow.py
        retrieve: register request and read project memory
        generate: ask DemoModel or Gemini for a structured proposal
        guarded_commit: submit the accepted proposal
    -> Service in app/service.py coordinates each operation
    -> FalkorStore.execute() in app/repository.py
        -> transition()/apply() in app/domain.py check the rules
        -> database saves the accepted state and receipt
    -> UI reloads and displays the saved plan
```

The terminal entry point, `app/cli.py`, reaches the same workflow and service.
Changing between UI and CLI does not create a different memory system, provided
you use the same practice user and project.

The model generates words and selects a permitted task. Python decides whether
that proposal is acceptable. FalkorDB saves what Python accepts.

## 4. Every application file, function by function

### app/fixtures.py — the example project

`seed(service)` creates invented starting data through the normal service rules:

- Decisions: `interface_framework=React`, `database_engine=FalkorDB`, `response_style=simple`.
- Approved `build` procedure: check decisions, perform the task, verify/report.
- Tasks: `interface`, `storage`, `deploy`, and `readme`.
- `deploy` depends on both `interface` and `storage`.

The local `decision()` helper first saves a user message, then saves a decision
that cites the exact message. Fixed operation IDs make seeding repeatable without
creating the same records again. Seeding an existing project is not a reset.

### app/models.py — talk to AI, or use fixed practice answers

`Plan(BaseModel)` specifies a Planner answer: `task_id` and `objective`.
`Help(BaseModel)` specifies a Helper answer: `summary` and one to eight `steps`.
`Field(...)` adds length limits. `extra="forbid"` rejects unexpected fields.
These are answer schemas; this file is not the database schema.

`Gemini.__init__()` checks `GOOGLE_API_KEY` and `GOOGLE_MODEL`, then creates a
LangChain `ChatGoogleGenerativeAI` adapter. It sets a 90-second timeout,
temperature 0, an output-token limit, and no automatic SDK retry loop.

`Gemini.generate(role, context)`:

1. Chooses the Planner or Helper schema and instructions.
2. Sends instructions as a system message and context as JSON in a human message.
3. Requests structured output matching the chosen schema.
4. Captures usage metadata and rejects missing/malformed structured answers.
5. Checks Helper step lengths and returns a Python dictionary.

The prompt tells the model to treat supplied text as data and avoid claiming it
executed or tested work. Those instructions help behavior; the Python rules remain
responsible for accepting writes.

`DemoModel.generate()` makes no AI call. Planner selects the first eligible task;
Helper returns two generic fixed steps. It demonstrates workflow mechanics, not
understanding or meaningful prompt following.

### app/domain.py — the project's rules

This file has no database calls or AI calls. Its input is data; its output is an
accepted new state and receipt, or an error.

| Function/class | What its code does |
|---|---|
| `Rejected` | An operation violates a rule |
| `Conflict` | A more specific rejection, such as reusing an ID for different input |
| `canonical(value)` | Converts data to consistently ordered JSON |
| `digest(value)` | Makes a SHA-256 fingerprint of that consistent representation |
| `now()` | Produces a UTC timestamp |
| `identifier(value)` | Allows only 1–80 letters, digits, underscores, or hyphens |
| `empty_project(project)` | Creates the empty dictionaries used for project memory |
| `required(mapping, key)` | Looks up a record or rejects an unknown reference |
| `current_inputs(s, task)` | Gets the current decision-version IDs required by this task |
| `satisfied(s, task_id, trail)` | Checks completion, result validity, decision coverage, and prerequisites recursively; detects cycles |
| `ready(s)` | Lists pending tasks whose required decisions/procedures exist and prerequisites are satisfied |
| `bundle(s, task_id)` | Captures task version, decision versions, procedure versions, and prerequisite facts |
| `valid_bundle(s, b, execution_version)` | Compares remembered inputs with current inputs; accounts for claiming changing the task version |
| `source(s, message_id, passage)` | Checks that the exact passage occurs in the saved message, and usually that its speaker is the user |
| `transition(state, kind, payload, operation_id)` | Copies state, checks replay/conflict, applies an operation, and saves a receipt |
| `apply(s, kind, p, oid)` | Dispatches to the particular command's rule branch |

`ALLOWED` limits decision memory to three configured keys and enumerated values:

```python
interface_framework: React, Streamlit
database_engine: FalkorDB, SQLite, PostgreSQL
response_style: short, simple, detailed
```

Choosing `SQLite` here records a choice for the example project. Continuity's own
storage implementation still uses FalkorDB.

`source()` also rejects selected speculative words and question marks for explicit
user changes. This is a small text heuristic, not general language understanding.

The branches inside `apply()` are the main state machine:

| `kind` | What happens |
|---|---|
| `message` | Save user/assistant text and its origin; reject conflicting reuse of the same message ID |
| `decision` | Validate an explicit allowed choice, save a new version, point current choice to it, and flag affected completed results |
| `task` | Create pending work with declared decisions, procedures, and prerequisites |
| `procedure` | Save explicitly approved steps and preserve procedure-version history |
| `handoff` | Save a plan only if its task is ready and its captured inputs still match |
| `claim` | Take an available task, record owner, and change it to `in_progress` |
| `draft` | Save Helper's proposal; it does not complete the task |
| `complete` | Accept a sourced user-reported outcome only with the matching claim and current inputs |
| `release` | Explicitly release the current claim and return the task to pending |
| `review` | Confirm compatibility, reopen work, or create replacement work and rewire exact dependents |
| `request` | Register request identity and reject different input under the same ID |
| `attempt_call` | Reserve one provider attempt; reject attempts beyond three per request |
| `envelope` | Save the exact command chosen for that request; prevent changing an accepted envelope |

For stale drafts/completions, the attempt is retained with `stale=True` rather
than treated as a valid result. A matching old claim can be released, but cannot
clear a newer owner's claim.

Code example, explained:

```python
s = copy.deepcopy(state)
fingerprint = digest(payload)
old = s["operations"].get(opkey)
```

The first line makes an independent copy so a rejected operation does not partly
edit the original project. The second fingerprints the command data. The third
checks whether this operation already happened. The following branch returns the
old receipt for identical input, or rejects different input. This is called
**idempotency**: retrying the same command has one logical effect.

`revision` is a visible business-change counter. The database's separate
`storage_version` also tracks internal writes such as request bookkeeping.

### app/repository.py — persistent storage and graph connections

`projection(state, project_key)` turns the project dictionary into graph records.
Its nested `node()` makes a record and `edge()` connects records. For example:

```text
Task(interface) --REQUIRES_DECISION--> DecisionSlot(interface_framework)
DecisionSlot(interface_framework) --CURRENT--> DecisionVersion(Streamlit)
DecisionVersion(Streamlit) --SUPERSEDES--> DecisionVersion(React)
DecisionVersion(Streamlit) --FROM_MESSAGE--> Message(user's explicit choice)
Task(deploy) --DEPENDS_ON--> Task(interface)
```

`LABELS` and `RELATIONSHIPS` list the fixed allowed graph types.
`COMMIT` is a Cypher query, the language used to read/write this graph.
It checks the expected storage version and atomically saves the snapshot,
rebuilt graph projection, and operation receipt. User values are query parameters;
the model never writes database queries.

`FalkorStore` is the real persistent adapter:

- `__init__(tenant, project)` validates selectors, connects using environment
  settings, selects the tenant graph, and creates the project if absent.
- `read_versioned()` returns both storage version and JSON snapshot.
- `read()` returns just the snapshot as a dictionary.
- `task_context(task_id)` traverses current decision relationships and up to
  16 levels of prerequisites, reading those facts and the snapshot together.
- `execute(kind, payload, operation_id)` reads state, runs `transition()`, builds
  the graph, and tries the guarded commit. If another writer changed storage,
  it recomputes from fresh state, for up to 12 tries.

The version guard is like saying, "Save this only if nobody changed the notebook
since I read it." A conflict triggers rechecking; an unrelated decision change
does not automatically invalidate a task.

`MemoryStore` implements the same read/execute/context operations in Python RAM
with a lock. It is useful for tests and the offline demo. It loses all records
when the process ends.

Real storage holds both a canonical JSON project snapshot and a connected graph.
It is not a graph-only design or a vector/embedding memory system. Rebuilding the
small graph on each write favors inspectability over large-scale performance.

### app/service.py — coordinate identity, context, and budgets

`new_id()` generates a random UUID string. `operation(request_id, stage)` derives
a stable operation ID for a particular step of a request.

| Service method | Purpose |
|---|---|
| `__init__(store)` | Keep the storage adapter and a local lock |
| `command(...)` | Limit payload size to 32,000 characters and call storage |
| `message(...)` | Give source text a stable identity and save it |
| `begin(...)` | Register the request's role, text, handoff, and owner |
| `context(...)` | Assemble eligible tasks, current decisions, and procedures |
| `generate(...)` | Limit context to 24,000 characters; persist a call reservation before invoking the model |
| `accept_envelope(...)` | Save the exact accepted command for later application/replay |
| `replay(...)` | Reapply that saved command with its original operation ID |
| `planning_snapshot()` | Read Planner context and input bundles from one snapshot |
| `helper_context(...)` | Retrieve connected task evidence and verify its claim/inputs before generation |

The call budget is persisted before dispatch so an interrupted or failed provider
call still consumes an attempt. There is no automatic three-call loop: a normal
generation uses one call; explicit retries may use the remaining budget.
The same service counter is exercised in scripted mode too, although scripted
mode makes zero external API calls.

### app/workflow.py — the ordered agent workflow

`State(TypedDict)` documents the data carried between workflow steps, including
request ID, role, context, claim, envelope, and receipt.

`build(service, model)` defines three functions and connects them using LangGraph:

```text
START -> retrieve -> generate -> guarded_commit -> END
                 \-> END if a saved result can be replayed
```

- `retrieve(st)` registers request/source text, tries replay, and either reads
  eligible planning context or claims the Helper's handoff.
- `generate(st)` checks replay again. Planner refreshes eligible work, generates
  a `Plan`, rejects a task outside the permitted set, and builds a handoff payload.
  Helper retrieves current evidence and generates a `Help` draft. Both save the
  accepted command envelope.
- `commit(st)` applies that envelope through the service; the domain/database
  guards make the final acceptance decision.
- `g.add_node(...)` registers a step. `g.add_edge(...)` sets its successor.
  The conditional edge skips generation when retrieve already recovered a receipt.
- `g.compile()` returns a runnable workflow. `.invoke({...})` executes it.

LangGraph controls step order. LangChain connects to Gemini. FalkorDB stores
business memory. Workflow-node checkpoint recovery is deferred; fresh workflow
sessions recover saved business records rather than resuming arbitrary code lines.

### app/actions.py — bridge browser actions to the service

- `connect()` creates a Service with real FalkorDB storage.
- `error_message()` turns common errors into readable messages without exposing keys.
- `workflow()` chooses DemoModel or Gemini and invokes Planner/Helper.
- `resume_helper()` invokes a previously saved Helper request.
- `mutate()` registers a stable request, tries replay, constructs explicit source
  text for changes, saves an envelope, and applies the command.
- `helper_request()` finds the original request owning a claim so an interrupted
  Helper operation can be retried with its original identity.

### streamlit_app.py — the page you interact with

Imports load Streamlit, `.env` settings, and app functions. `set_page_config()`
sets page title/layout; the CSS string sets simple visual styling.

Helper functions at the top:

- `flash()` remembers a notice and reruns the page.
- `request_id()` keeps a pending request ID keyed by scope/action/input.
- `execute()` displays progress, dispatches an action, saves its receipt in UI
  state, and reruns after success. Failure retains the pending ID for retry.
- `draft_view()` parses a saved JSON draft into a summary and numbered steps.

Sidebar code chooses practice user/project, page, and scripted/live mode. It
connects to FalkorDB, offers refresh, and can seed a separate practice project.

The four page branches are:

1. **Workspace:** ready/in-progress/review/completed counts, planning form, task
   list and creation, handoff selection, remembered inputs, Helper draft,
   completion report, claim release, and review resolution.
2. **Memory:** current decision forms, earlier decision versions and sources,
   approved procedure creation, attempts, requests, and reviews.
3. **Checks:** runs the isolated 14-scenario evaluation and offers a report download.
4. **Benchmark:** explains the separate conversation-memory evaluation process.

Streamlit reruns this Python file when you interact. `st.session_state` retains
temporary UI values across reruns; FalkorDB retains project facts across processes.
Opening a different browser session can lose selection/pending-form state, but
does not delete saved project memory.

### app/cli.py — the terminal version

`parser()` defines commands and arguments using `argparse`. Global `--tenant` and
`--project` options come before the command. `run(args)` connects to the service
and dispatches the selected command. Its nested `accept()` saves/applies envelopes.
`main()` loads `.env`, parses arguments, prints JSON, and handles errors.

Useful commands: `doctor`, `seed`, `status`, `history`, `requests`, `plan`, `help`,
`complete`, `decide`, `task`, `procedure`, `review`, `release`, and `replay`.

`if __name__ == "__main__":` means "run main when launched as a program, rather
than when another file imports it." `python -m app.cli` launches this module.

### app/demo.py — an automatic offline story

`main()` creates MemoryStore and DemoModel, seeds examples, runs Planner and
Helper, supplies a clearly synthetic completion, changes React to Streamlit,
and prints the review/blocking behavior. No database or real AI is involved.

### app/evaluate.py — 14 deterministic scenario checks

`run_checks()` creates a separate random database graph unless given a store.
The nested `check()` collects results; `finish()` supplies synthetic completion
evidence. The scenario tests sources, readiness, handoff retrieval, unrelated
changes, claim versions, draft separation, completion, replay, conflicting input,
correction history, invalidation, deployment blocking, and compatibility review.
Its temporary graph is deleted afterward. Running as a module writes
`reports/scenario-results.json`. No model calls are made.

### app/__init__.py

Marks/describes the `app` Python package. It contains a descriptive docstring.

## 5. Try the memory yourself in the browser

### Start the app

Open a PowerShell terminal in this project folder. Start Docker Desktop if needed:

```powershell
.\docker.ps1 compose up -d --wait
.\run.ps1 doctor
.\ui.ps1
```

The last command stays running to serve the page. Open http://localhost:8501.
The database/browser use ports 6380/3000; the app UI uses 8501.

### Experiment A: remember a plan across app restarts

1. Enable **Scripted practice** so there are no external model calls.
2. Click **Create fresh practice project**. Write down its `practice_...` name
   and Practice user; these selectors identify the memory you will reopen.
3. In Workspace click **Create plan**. In this fresh seeded project, scripted
   Planner picks `interface` first.
4. Expand **Inputs remembered for this plan**. Observe React and the build procedure.
5. Click **Get Helper steps**. The task becomes in progress; a draft is saved.
6. Close the browser tab. In the terminal press Ctrl+C to stop Streamlit.
7. Run `.\ui.ps1` again, reopen the URL, enter the same user/project, and click
   **Open project**. Enable scripted mode again for further practice actions.
8. Your saved plan/draft should reappear. Do not create another fresh project:
   that would select different memory.

What this shows: the notebook lives in FalkorDB, not just in the browser or Python
process. It does not prove crash-proof disk persistence; that is a separate test.

### Experiment B: actually finish a tiny task

For the seeded interface task, make a small real React component in a separate
scratch project if you already know React. If you do not, release that task using
**Return unfinished work to the queue**, and use an easier custom task instead:

1. Under **Add your own task**, use ID `intro`, title `Write a two-sentence project introduction`,
   with no requirements/prerequisites/procedures, then save it.
2. Scripted Planner always chooses the first eligible task. To make selection
   predictable, open a separate empty project, for example `my_intro_lab`, and
   add only this task there rather than loading examples.
3. Create a plan and get Helper steps.
4. Write the two sentences yourself in a local text file and read them back.
5. Expand **Report work you actually finished**, describe that actual result,
   check the confirmation, and click **Record completed work**.
6. Observe completed status. Reopen the same project and see the outcome retained.

What this shows: a draft and a completed user-reported result are different records.
The app records your report; it does not independently inspect your text file.

### Experiment C: catch a stale plan without doing React work

1. Create another fresh practice project, with scripted mode enabled.
2. Create an interface plan, but do not click Get Helper steps yet.
3. On Memory choose `interface_framework`, choose `Streamlit`, click **Save decision**.
4. Observe Streamlit current and React in earlier history.
5. Return to Workspace and select the old plan. Its inputs changed; it should
   be unusable and Helper generation should be disabled.
6. Create a new plan. Expand remembered inputs and observe Streamlit.

What this shows: a saved plan is tied to exact decision versions. The system
does not silently apply a React plan after you switch its technical inputs.

### Experiment D: affected completed work and dependency blocking

Use the **Checks** page and click **Run project checks**. It performs the synthetic
completion/correction/review scenario in a separate graph and displays each check.
Expect 14/14 if the database integration works. It uses zero Gemini calls.

For a manual version, use an interface task you actually completed under React,
then switch `interface_framework` to Streamlit. Observe **Needs review**. The
`deploy` task waits for valid interface and storage results. Resolve review using:

- **Existing work is compatible:** records your compatibility judgment.
- **Do this task again:** returns it to pending.
- **Create replacement work:** creates a new task and redirects dependents.

Choose one resolution based on what is true. Finishing interface alone never
unblocks deploy while storage is still unfinished.

### Experiment E: use real Gemini

Open the existing `.env` privately. Set `GOOGLE_API_KEY` and `GOOGLE_MODEL` to your
own configured values; do not overwrite existing credentials or paste them into
source files. Restart the UI after changing environment settings.

1. Create a fresh practice project.
2. Turn **Scripted practice** off.
3. Ask: "Choose a small ready task and explain the objective for a beginner."
4. Create the plan, inspect its inputs, then get Helper steps.
5. Compare the generated steps with the fixed scripted steps.
6. On Memory change `response_style` to `short`, then use a new eligible request
   to see whether Planner follows that preference. It is not a hard guarantee;
   Helper's context currently includes only the task's required technical decisions.

These actions use your API quota. Existing saved drafts display without another
generation. A failed request can be retried with the same inputs/ID, up to its
three-attempt budget. Switching model mode does not rewrite an existing saved draft.
The previous project status document records live-provider timeouts; this guide
does not claim live generation succeeded today.

### Experiment F: inspect the graph

Open http://localhost:3000. Run `.\run.ps1 doctor` to see the tenant graph name.
The default UI user is `userA`, so the default doctor graph matches that user.
For another user run `.\run.ps1 --tenant YOUR_USER doctor`.

Select that graph. To inspect current decisions for one chosen project:

```cypher
MATCH (slot:DecisionSlot)-[:CURRENT]->(d:DecisionVersion)
WHERE slot.project = 'REPLACE_WITH_YOUR_PROJECT'
RETURN slot, d
```

To see the old and new versions:

```cypher
MATCH (new:DecisionVersion)-[:SUPERSEDES]->(old:DecisionVersion)
WHERE new.project = 'REPLACE_WITH_YOUR_PROJECT'
RETURN new, old
```

These are read-only queries. `QUERIES.md` contains more examples.

### Optional: test database restart persistence

Save a plan and write down its ID and project, then in a separate terminal:

```powershell
.\docker.ps1 compose restart falkordb
.\docker.ps1 compose up -d --wait
```

Refresh the UI after the server is healthy and reopen the same project. The
same records should remain. Restart briefly interrupts other local users of this
database. Keep the volume; `compose down -v` removes its stored data.

## 6. Remaining files and folders

| File | Purpose |
|---|---|
| `run.ps1` | Selects `.venv` Python or `.tools/python`, sets working folder, runs `app.cli`, forwards your arguments |
| `ui.ps1` | Selects Python and runs Streamlit locally on port 8501 |
| `docker.ps1` | Locates Docker Desktop's CLI/helper and forwards Docker arguments |
| `compose.yaml` | Defines pinned FalkorDB container, localhost ports, healthcheck, and persistent volume |
| `.env` | Your local connection/model settings and private API key; not printed in this guide |
| `.env.example` | Blank/example names of environment settings |
| `requirements.txt` | Allowed dependency version ranges |
| `requirements.lock` | Frozen package versions for a reproducible installation; verify installed packages if dependencies change |
| `pytest.ini` | Test folder and database/live marker names |
| `.gitignore` | Excludes secrets, installed tools, caches, and generated benchmark folders from Git |
| `.vscode/settings.json` | Tells VS Code's Python terminal to use environment-file settings |
| `README.md` | Setup, CLI walkthrough, architecture, and persistence commands |
| `IMPLEMENTATION_STATUS.md` | Earlier implementation evidence and known limits; may lag newer code |
| `PROJECT_PLAN.md` | Broader intended design; not proof everything is implemented |
| `EVALUATION_PLAN.md` | Intended evaluation strategy and gates |
| `HACKATHON_BRIEF.md` | Event/submission context |
| `roadmap.md` | Roadmap and planning context |
| `QUERIES.md` | Read-only graph inspection queries |
| `BENCHMARKS.md` | UI/checks/experimental memory-benchmark instructions |
| `reports/` | Saved test reports, persistence evidence, manifests, and scenario results |
| `.tools/` | Project-local Python and installed tooling; external package implementation is not Continuity application code |
| `.pytest_cache/`, `__pycache__/` | Generated test/Python caches, not memory storage |

The Compose volume stores database files under `/data` inside the container. AOF
logs database operations to disk, with an every-second flush policy. A hard crash
can lose a small recent window. `restart: unless-stopped` controls container restart
behavior; the named volume is what lets files survive replacing the container.

### Test files

| File | What it checks |
|---|---|
| `tests/conftest.py` | Shared `service` fixture; supplies RAM or isolated database graphs and cleans up only its own graphs |
| `tests/test_contracts.py` | Decision history, provenance, reviews, prerequisites, changing inputs, claims, replay, budgets, workflow behavior |
| `tests/test_workflow_edges.py` | Invalid model choices, malformed output, write failure recovery, stale owners, concurrent reservations, stale reviews |
| `tests/test_integrations.py` | Fresh-process database retrieval, project/user separation, graph paths; separately gated live Gemini smoke check |
| `tests/test_ui.py` | Streamlit interaction flows, completion/correction/review, rerun behavior, and scenario evaluator |
| `tests/test_benchmark_adapter.py` | History-label isolation, context budgets, dry runs, reader-call accounting, scoring linkage, graph retrieval |

Tests use `assert` to state something expected to be true. A pytest fixture creates
reusable setup. `monkeypatch` temporarily replaces a dependency for a controlled
test. `tmp_path` provides temporary files. A skipped test was not executed.

Run offline checks with workspace-local temporary files:

```powershell
$env:PYTHONNOUSERSITE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.\.tools\python\python.exe -m pytest -q --basetemp .pytest_cache/my-learning-run
```

Use a dedicated disposable `--basetemp` directory: pytest clears it when reused.
To include real database contracts, first start Docker and set:

```powershell
$env:CONTINUITY_DB_TESTS = '1'
.\.tools\python\python.exe -m pytest -q --basetemp .pytest_cache/my-db-learning-run
```

Live tests are a separate opt-in through `CONTINUITY_LIVE_TESTS=1` and `-m live`.

### Experimental benchmark files

These explore general conversation retrieval separately from task decision memory.

`benchmarks/longmemeval.py`:

- `terms()` extracts lowercase nontrivial words and drops common stop words.
- `Session` stores a history session's ID, date, and turns; `text()` joins its text.
- `history_only()` imports allowed history fields, sorts by timestamp, and strips
  evaluator-only answer labels so they cannot leak into model evidence.
- `bm25()` ranks sessions with a lexical word-based scoring baseline.
- `GraphHistory.__init__()` stores sessions connected to terms and adjacent sessions
  in a temporary graph; `retrieve()` finds word hits and neighbors; `close()` deletes it.
- `fit_context()` includes whole sessions within a character budget. Full-history
  mode errors if everything cannot fit; it does not silently truncate that baseline.
- `Answer` validates answer text and cited session IDs.
- `Reader.answer()` asks Gemini to answer using supplied evidence, checks its schema,
  and rejects citations outside the supplied context.
- `run()` loads cases, freezes run metadata, retrieves using graph/BM25/full/none,
  optionally calls the reader under a budget, and writes traces/predictions/manifest.
- `main()` parses the benchmark's command-line options.

`benchmarks/score.py`: `summarize()` loads a completed answer run and judge labels,
checks exact question/answer correspondence, counts execution errors as incorrect,
and writes `score.json`. It aggregates judge results; it does not independently
judge answers or prove the supplied judge log's origin.

`benchmarks/fixtures/synthetic.json` contains three invented conversation questions.
`benchmarks/__init__.py` describes the package.

Try retrieval alone, with zero Gemini calls, using a fresh output directory:

```powershell
.\.tools\python\python.exe -m benchmarks.longmemeval --dataset benchmarks/fixtures/synthetic.json --out benchmark-runs/my-first-memory-lab --method graph --limit 3 --dry-run
```

Read `manifest.json` and `traces.jsonl` in that output folder. Each trace shows the
question ID and retrieved conversation evidence. A dry run produces no model
answer predictions and no answer-quality score. For comparisons and external
datasets, follow `BENCHMARKS.md`; no public benchmark score is claimed here.

## 7. A useful reading order

Read `fixtures.py` -> `demo.py` -> `models.py` -> `workflow.py` -> `service.py` ->
`domain.py` -> `repository.py` -> `actions.py` -> `streamlit_app.py` -> `cli.py`.
Then study one test at a time. Start with the basic workflow test and ask, "What
state existed before this operation, and what should be different afterward?"

The essential boundary is: generated suggestion -> Python validation -> saved
memory -> your actual work -> your sourced outcome -> later review if inputs change.
