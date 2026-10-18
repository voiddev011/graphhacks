# Workspace review and test results

No commits or pushes were made. User projects were not reset or seeded.

## Fixes

- Each real fallback dispatch now reserves its own persistent request-budget slot; a request still permits at most three attempts, including failed attempts and retries.
- Router error history records exception types, not raw provider payloads. UI errors do not expose raw exception bodies.
- Local judging now requests and consumes a real correctness verdict. Removed substring-based success and heuristic success after judge failure. Judge calls are explicitly capped, fixed to the named model, and logged separately.
- Score files flag invalid evaluation when judging fails; comparisons reject these runs.
- The contract button uses its own temporary FalkorDB graph rather than the open project.
- Removed hardcoded benchmark scores and the quick button's hardcoded task.
- Chat now saves the receipt before rerunning, so plan/helper action buttons appear. Completion confirmation starts unchecked and is enforced.
- Prior synthetic score artifacts were preserved with review notices.

## Verification

The full regression run initially had 74 passed, 2 failed, 2 skipped. The two failures were a newly added test's emoji-dependent button lookup. After correcting it, the focused run passed 27 tests with 1 skipped. Across the latest results per test: 76 passed, 0 failed, 2 skipped (reports/review-summary.json). A later follow-up passed 11 tests with 1 skipped (and one non-failing pytest cache permission warning), including a new check rejecting failed judging. Across all latest results: 77 passed, 0 failed, 2 skipped.

Contract checks: 14/14 against actual FalkorDB, zero model calls, temporary graph removed afterwards. Streamlit HTTP health: 200 on localhost:8501. UI behavior was checked with AppTest; no visual browser inspection is claimed.

## Live benchmark pilot (not a leaderboard result)

Downloaded the official original LongMemEval oracle dataset from the cleaned release: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json
SHA-256: 821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c

Oracle contains evidence sessions only. Both runs selected the first three IDs before answering, out of 500. No gold answers or has_answer labels entered reader context. The histories are imported into temporary benchmark graphs, separate from app data.

| Run | Reader calls | Answer errors | Judge calls/errors | Context ceiling |
|---|---:|---:|---:|---:|
| review-oracle-nemotron | 3 | 1 | 2 / 2 | 24,000 chars |
| review-oracle-gemini-wide | 3 | 2 | 1 / 1 | 60,000 chars |

The Nemotron run omitted needed complete evidence sessions under the small budget. Two returned answers missed the reference facts; the third response had no expected choices field. OpenRouter judge requests produced HTTP errors. Gemini answered the first wide-context case, then hit GoogleRateLimitError on the next two reader calls and the judge call.

Both score files conservatively count errors incorrect, producing zero, but evaluation_valid is false because judging failed. Do not interpret these numbers as model accuracy. No global comparison is supported. The runs differ in context ceilings and are not a fair model comparison. Preserve them as failure diagnostics. No further API calls are necessary until quota/availability improves.

See docs/TESTING_GUIDE.md for manual app testing, isolated checks, fresh benchmark runs, scoring, and fair comparisons. docs/BENCHMARKS.md describes the adapter's separate scope.
