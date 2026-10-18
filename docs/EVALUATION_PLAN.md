# Check the actual Track 2 features

The final suite and live reports, not an invented leaderboard number, are the
release evidence. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

| Feature | Check |
|---|---|
| Persistent conversation | Reload the UI and read a saved turn |
| Cross-session memory | A fresh Python process and new thread recall facts |
| Correction | Change restaurant count; current value changes, history remains |
| Three memory types | Store a fact, an event and an explicit reusable routine |
| Graph connections | Two named businesses coexist; follow ownership to location |
| Agent coordination | Planner handoff and Helper share current sourced facts |
| Tenant/project scope | Other profiles/projects cannot retrieve those records |
| Concurrent access | Unrelated writes merge; conflicting corrections reject |
| Replay and budget | Same accepted request has one effect; failures consume budget |
| Stale work | Changed relevant evidence cannot silently validate a draft |

## Repeat checks from this workspace

```powershell
$env:PYTHONNOUSERSITE='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:CONTINUITY_DB_TESTS='1'
.\.tools\python\python.exe -m pytest -q
.\.tools\python\python.exe -m benchmarks.contracts
```

Automated model doubles live only in tests. Each database test owns a temporary
graph. Contract fixtures never populate your open project.

Optional REAL model checks (consume quota, use temporary profiles):

```powershell
.\.tools\python\python.exe -m benchmarks.live_memory --model nvidia/nemotron-3.5-super-vl:free --out reports/my-live-memory.json
.\.tools\python\python.exe -m benchmarks.live_ui
```

The first checks remember, process restart, cross-role recall, correction and
handoff. The second runs one real chat through Streamlit AppTest and reloads
memory. AppTest is not a visual browser screenshot test. Both remove their own
test graph and leave your project data unchanged.

These are synthetic end-to-end scenarios with actual model calls, not public
benchmark scores. One passing scenario does not prove broad conversational
accuracy or production load capacity. Benchmark datasets, fixed-model comparison
and the experimental LongMemEval adapter are covered in [BENCHMARKS.md](BENCHMARKS.md).
Historical 3/3 fixture scores are unverified and must not be presented as public
LongMemEval accuracy. The corrected local judge uses an actual model verdict;
judge errors invalidate an accuracy comparison. No leaderboard submission exists.
