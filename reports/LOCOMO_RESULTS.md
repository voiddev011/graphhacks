# Continuity: actual LoCoMo pilot results

18 October 2026. Eight fixed questions from one original LoCoMo conversation. Both methods answered all eight questions.

| Method | Token F1 | Local AI judge | Answer/judge API errors |
|---|---:|---:|---:|
| FalkorDB memory | 18.75% | 37.5% (3/8) | 0/0 |
| Same reader, no memory | 0.0% | 0% (0/8) | 0/0 |

**Important limitation:** the frozen import accepted 16 of 19 chunks and retained 52 current memories; 190 proposed memories were rejected by the source checks. This is an incomplete-import pilot, not a full-corpus quality score. The judge was lenient on paraphrases: it accepted the answer about a transition without the exact identity words; token F1 gave that answer zero. Treat AI judging as a disclosed automatic assessment, not independently verified correctness.

The observed graph memory helped on two single-fact questions. Date questions and questions requiring multiple details were weak. Missing or rejected extraction and limited retrieval may both contribute; this run does not isolate their individual effects. Do not tune on these eight questions and call a retest an unseen benchmark.

Reader: `gemini-3.5-flash-lite`. Extractor: `cohere/north-mini-code:free`. Judge: `gemini-3.5-flash`. The resumed run used 20 provider requests. No answering fallback or automatic retries. Memory stayed unchanged; the temporary graph was removed. Existing user project graphs were not modified.

Token F1 is normalized, stemmed word overlap using the original category rules. Local judge percent is a separate semantic judgment. The official-style scorer matched 24 comparisons against the original scorer. These eight questions are not directly comparable to Mem0's published 1,540-question evaluation.

## Open the results

- Website: **Benchmark**, then select **locomo-gemini35lite-resumed-20261018**.
- [Browser dashboard](../benchmark-runs/locomo-gemini35lite-resumed-20261018/dashboard.html)
- [Detailed report](../benchmark-runs/locomo-gemini35lite-resumed-20261018/REPORT.md)
- [Each question and answer](../benchmark-runs/locomo-gemini35lite-resumed-20261018/answers.csv)
- [Setup, architecture and repeat commands](../docs/LOCOMO.md)

Sources: [original LoCoMo](https://github.com/snap-research/locomo), [Mem0 research](https://mem0.ai/research).
