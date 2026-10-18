# Test Continuity yourself

Run these commands from `C:\Users\Jainam\Desktop\Graph-hacks`.
No extra Python packages are required for these steps.

## 1. Test normal chat first

Follow [QUICKSTART.md](QUICKSTART.md): tell it your facts, start a new conversation,
ask Helper to recall them, make a correction, refresh and inspect the graph. This
now uses real model responses and durable conversation history, not phrase matching.
The task board remains available for explicit dependencies and outcome reports.

## 2. Run application checks

```powershell
$env:PYTHONNOUSERSITE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:CONTINUITY_DB_TESTS='1'
.\.tools\python\python.exe -m pytest -q
.\.tools\python\python.exe -m benchmarks.contracts
```

Expected contract result: **14/14**. These are synthetic automated checks in temporary graphs, not your live project's tasks and not a model leaderboard score. Pytest model doubles stay in tests. Live API tests remain gated separately.

## 3. Try the benchmark plumbing first

This uses three synthetic questions solely to check the runner. It does not prove public benchmark accuracy and does not load anything into your workspace.

```powershell
.\.tools\python\python.exe -m benchmarks.longmemeval --dataset tests/data/longmemeval.json --out benchmark-runs/my-smoke-graph --method graph --model nvidia/nemotron-3.5-super-vl:free --limit 3 --max-calls 3
.\.tools\python\python.exe -m benchmarks.judge --dataset tests/data/longmemeval.json --predictions benchmark-runs/my-smoke-graph/predictions.jsonl --model nvidia/nemotron-3.5-super-vl:free --max-calls 3
.\.tools\python\python.exe -m benchmarks.score --run benchmark-runs/my-smoke-graph --judge-log benchmark-runs/my-smoke-graph/predictions.jsonl.local-judge.jsonl
```

Read `manifest.json` for generation errors/calls, `traces.jsonl` for retrieved evidence, `predictions.jsonl` for answers, and `score.json` for accuracy. The judge's companion `.manifest.json` records judge errors and calls. If `evaluation_valid` is false, judging failed: the numeric accuracy is not a usable quality result and comparisons will reject it. Judge failures count incorrect, rather than becoming guesses. This is a local LLM judge, not the official evaluator. Review the individual verdicts yourself.

Each run needs a **new output directory**. To repeat, change `my-smoke-graph` everywhere to `my-smoke-graph-2`. Free models can be unavailable or rate limited. Benchmarks use the named model without fallback so a score never silently mixes providers.

## 4. Measure memory on real benchmark data

Get `longmemeval_s_cleaned.json` from the [official LongMemEval repository](https://github.com/xiaowu0162/LongMemEval) and save it under `benchmark-data/`.

Use the three commands above with the real dataset path and a fresh output directory. Begin with `--limit 3 --max-calls 3`; this is only a pilot subset. Then use a fixed larger subset, such as 20, increasing both limits and the judge budget to 20. Never choose questions after seeing their scores.

Inspect the trace first: if needed sessions exceed the 24,000-character ceiling, raise `--context-chars` (for example, 60000) for every compared run. The pilot exposed this exact issue. Entire sessions are omitted when they do not fit; they are never silently cut in half.

Run the same chosen questions twice: `--method graph` and `--method none`. Keep the reader, judge, top-k, and context budget identical. Score both, then compare:

```powershell
.\.tools\python\python.exe -m benchmarks.compare benchmark-runs/my-real-graph benchmark-runs/my-real-none --vary memory
```

Those directories must be the actual scored run directories you created. This compares whether retrieving memory helped the same model. To compare models, keep `--method graph` fixed, run each model on the same cases and use `--vary reader` with the same judge.

The separate `longmemeval_oracle.json` file includes only evidence sessions. It is useful for a reader smoke test, but does not measure retrieval through distracting history. Label oracle results explicitly.

A full S evaluation has 500 questions. Our conversation adapter is an experimental lexical graph retriever; it is separate from the app's typed task/decision memory. Local judge scores are not directly comparable to published GPT-4o-judged results. Use the original evaluation script and matching published protocol for that comparison; this guide does not submit anything to a global leaderboard.

## Previous results

The old `gemini-live-eval` and `nemotron-live-eval` reports used the three synthetic fixture questions. Their original judge used substring heuristics instead of consuming an actual judge verdict. Treat their 100% scores as unverified historical smoke results. Fresh runs use the corrected judge. The UI no longer hardcodes those scores.
