# Testing and comparing Continuity

For the new public-conversation pilot, read [LOCOMO.md](LOCOMO.md). It explains
the real LoCoMo dataset, with-memory/no-memory comparison, score dashboard,
source failures, and the frozen-memory resume command. Results are local subset
measurements, not official leaderboard submissions.

Start with [the short working-demo guide](DEMO_SCRIPT.md). Historical 3/3 synthetic scores were unverified because an earlier judge ignored model verdicts. Fresh runs use a corrected local judge; they are not official evaluator results.

Three different results must stay separate:

| Result | What it establishes |
|---|---|
| Streamlit/pytest tests | Application behavior: handoff, guards, replay and UI actions |
| 14 synthetic contract checks | A repeatable project scenario pass rate, with zero model calls |
| LongMemEval-format QA evaluation | How well an experimental conversation-memory adapter supports answering questions |

No public benchmark score or leaderboard placement is claimed.

## 1. Live workspace

Start `.\ui.ps1` and open `http://localhost:8501`. Enter your own task and use live
Gemini. The interface does not preload tasks, chats, or benchmark conversations.

## 2. Isolated application checks

`python -m benchmarks.contracts` runs fixed automated contract tests in a separate
graph. Fixtures and model doubles are kept under `tests/`, outside the live app.
The 14-check pass rate is not model accuracy or a leaderboard score.

## 3. External benchmark adapter: current scope

Our task memory uses explicit typed decisions and task dependencies. Public
chat-memory benchmarks require broader conversational retrieval. The new
`benchmarks/longmemeval.py` module is an **experimental extension**:

- Imports complete timestamped user/assistant history sessions.
- Whitelists role/content/date; removes gold answers and evaluator-only labels
  from ingestion/retrieval/model inputs.
- Stores raw sessions in a separate temporary FalkorDB graph connected by terms
  and chronological adjacency. It does not assert all assistant text as user facts.
- Retrieves lexical graph hits plus adjacent sessions. This is a simple baseline,
  not a new memory algorithm or the production task controller.
- Supports BM25, full-history and no-memory comparisons with the same reader.
- Produces `question_id`/`hypothesis` JSONL for the original LongMemEval evaluator.
- Records the dataset checksum, selected IDs, errors, actual calls, latency,
  retrieved context, citations and provider token metadata.

All history is imported; retrieved context uses complete sessions within an
explicit character ceiling. A full-history baseline that exceeds the ceiling
is recorded as an error, not silently truncated. If one required session cannot
fit, retrieval may omit it and quality can fall; report the actual budget.

## 4. Choose your own dataset

No benchmark conversations are preloaded in the app. Supply the permitted
original LongMemEval-format JSON file you intend to evaluate. Automated adapter
fixtures exist only under `tests/data/` and are not public benchmark results.

## 5. Use the official original LongMemEval data

Use the cleaned S release linked from the
[official repository](https://github.com/xiaowu0162/LongMemEval). Review the
dataset's terms and hackathon data rules before using it; the corpus is stored locally under the ignored `benchmark-data/` directory. Put your permitted JSON file under
`benchmark-data/` (ignored by Git).

First inspect retrieval without any model calls:

```powershell
.\.tools\python\python.exe -m benchmarks.longmemeval --dataset benchmark-data/longmemeval_s_cleaned.json --out benchmark-runs/lme-retrieval --method graph --limit 3 --dry-run
```

Then start with a small fixed live pilot and inspect errors/cost before a full run:

```powershell
.\.tools\python\python.exe -m benchmarks.longmemeval --dataset benchmark-data/longmemeval_s_cleaned.json --out benchmark-runs/lme-graph-pilot --method graph --limit 3 --max-calls 3
```

The manifest freezes the first N selected IDs and dataset SHA-256 before
answering. A 3-instance result must be labeled a subset. A standard complete S
run requires all 500 questions and an explicitly increased call budget. It can
consume substantial time/API quota; **we have not run it**.

The runner supports text histories only. It is for original LongMemEval,
not LongMemEval-V2's multimodal trajectories. No oracle evidence, question type,
answer-session labels or `has_answer` hints enter retrieval or the reader.

## 6. Get a QA score

Run the original project's official `evaluate_qa.py` on our `predictions.jsonl`
and the exact matching reference dataset. Follow that repository's environment
and judge instructions in a **separate environment**; its dependencies differ
from our app. The reference script's GPT-4o judge needs separate API access and
can incur cost. Do not paste a judge key into project source or reports.

The reference script writes an `.eval-results-<judge>` JSONL file. Aggregate it:

```powershell
.\.tools\python\python.exe -m benchmarks.score --run benchmark-runs/lme-graph-pilot --judge-log benchmark-runs/lme-graph-pilot/predictions.jsonl.eval-results-gpt-4o
```

Our aggregator checks that every selected question appears once and that judged
answers match this run's predictions. It records the judge identity and counts
execution errors as incorrect rather than dropping them. It cannot verify that
someone genuinely used the official judge merely from a log's format: publish
the actual scorer version, command and provenance along with the result.

## 7. Compare fairly

Run `--method graph`, `--method bm25`, `--method full` and `--method none` in
different output folders. Keep the exact dataset/selected IDs, reader model,
prompt, settings, context ceiling and judge fixed. Report errors alongside accuracy.

To compare reader models, pass `--model` with a model available to your Gemini
account, while holding the retrieval method and other settings fixed. The adapter
currently supports Gemini readers only; it does not compare all model providers.
For a memory-system comparison, keep the reader fixed.

After scoring each run, compare two local result folders:

```powershell
.\.tools\python\python.exe -m benchmarks.compare benchmark-runs/lme-graph-pilot benchmark-runs/lme-bm25-pilot --vary memory
```

For model comparisons use `--vary reader` with a fixed retrieval method. The
comparison command rejects mismatched dataset checksums, selected instances,
judge, required fixed reader/method and context/settings. It compares local
scored runs; it does not upload results to a leaderboard.

Publish measured ingestion time, retrieval time, total latency and tokens in
addition to accuracy. Candidate methods are baselines, not measured improvements.
This simple lexical adapter may perform poorly on paraphrases and large histories.

## 8. Public leaderboards

Original LongMemEval evaluation does not automatically submit anything globally.
LongMemEval-V2 has a different adapter, fixed-reader protocol, accuracy/latency
metric and submission packaging. This project has **not implemented or submitted
that V2 integration**. Follow the
[V2 submission protocol](https://github.com/xiaowu0162/LongMemEval-V2#submitting-to-leaderboard)
for that separate work; do not compare an original-S percentage to V2's LAFS gain.
