# Benchmark history

Every measured run, in order, with the numbers as they were printed at the time.
Dated raw output from `run_all.sh` is in this folder too (`*-run.txt`).

Metrics: **hit@1** is the share of queries whose right specialist ranks first;
**hit@3** is the share in the top three; **MRR** is the mean of 1/rank (0 for a
miss); **avg output** is characters per search result list, a proxy for the
context a search adds.

Tuning and holdout sets are not independent. See the caveat at the end.

---

## Run 0: original scoring (token overlap, first `roster.py`)

Query set: `eval.json` (31 queries).

| Set | hit@1 | hit@3 | MRR | avg output |
|---|---|---|---|---|
| eval (31) | 68% | 81% | 0.75 | 1,732 chars |

Misses at this stage: "is our app really production ready", "improve google rankings for my site",
"run a Google Ads pay-per-click campaign" (rank 5), "CI/CD pipeline and deployment automation" (rank 8),
"UI mockup for a dashboard screen", "cold outreach emails to prospects".

## Run 1: BM25 with stemming, stopwords, synonyms, body weight 1.0

| Set | hit@1 | hit@3 | MRR | avg output |
|---|---|---|---|---|
| eval (31) | 77% | 87% | 0.83 | 1,815 chars |

Regressions: "code review of a pull request" (no longer in the top 3) and
"accessibility audit of my website" (rank 4).

## Run 2: body weight 0.5 and a "ready/readiness" synonym

Body-weight grid on `eval.json` (before the "ready" synonym):

| Body weight | Name weight | hit@1 | hit@3 | MRR |
|---|---|---|---|---|
| 1.0 | 3 | 77% | 87% | 0.83 |
| 1.0 | 4 | 77% | 87% | 0.83 |
| 0.5 | 3 | 81% | 90% | 0.86 |
| 0.5 | 4 | 81% | 90% | 0.86 |
| 0.25 | 3 | 81% | 90% | 0.86 |
| 0.25 | 4 | 81% | 90% | 0.87 |

Chosen: body weight 0.5, name weight 3. Result on `eval.json`:

| Set | hit@1 | hit@3 | MRR | avg output |
|---|---|---|---|---|
| eval (31) | 81% | 94% | 0.87 | 1,813 chars |

A "PR / pull request" synonym was tried here. It moved "code review of a pull request"
from not found to rank 5, left the hit counts unchanged, and pulled in PR-communications
agents for unrelated queries. It was removed.

## Run 3: holdout sets, scored before any fix

Written before any change. `holdout2.json` had one label for a nonexistent agent
(`marketing-conversion-rate-optimizer`). It was removed after this run. That id never
matched, so the scores below are unaffected.

| Set | hit@1 | hit@3 | MRR | avg output |
|---|---|---|---|---|
| holdout (25) | 68% | 84% | 0.76 | 1,792 chars |
| holdout2 (20) | 80% | 90% | 0.85 | 1,830 chars |

Misses on `holdout.json` at this stage: "make my landing page load faster", "investor pitch
financial projections" (rank 5), "container image vulnerability scan", "quarterly roadmap and OKR planning".
Misses on `holdout2.json`: "reduce bounce rate on our checkout page", "check my code for memory leaks".

## Run 4: general fixes (synonyms and a name-match bonus)

Added: "faster / slow / speed / load" to performance; "projections / forecasts" to forecasting;
"docker / containers / kubernetes" to container and cloud; "OKR" to planning; "roadmap";
"mockup" to design. Added a bonus of 5.0 when every word of an agent's name is in the query.

| Set | hit@1 | hit@3 | MRR | avg output |
|---|---|---|---|---|
| eval (31) | 87% | 100% | 0.92 | 1,810 chars |
| holdout (25) | 72% | 88% | 0.80 | 1,783 chars |
| holdout2 (20) | 80% | 90% | 0.85 | 1,829 chars |

The fixes were chosen after seeing the holdout misses, so the holdout number is optimistic.
`holdout2.json` was not used to choose them.

## Run 5: embeddings (`all-MiniLM-L6-v2`, ONNX, CPU) and hybrid

Embedding only (before any fusion work):

| Set | hit@1 | hit@3 | MRR | avg output |
|---|---|---|---|---|
| eval (31) | 77% | 90% | 0.85 | 1,817 chars |
| holdout (25) | 64% | 80% | 0.73 | 1,811 chars |
| holdout2 (20) | 65% | 85% | 0.72 | 1,833 chars |

First hybrid version, reciprocal rank fusion (k = 60, embedding weight 1.0):

| Set | hit@1 | hit@3 | MRR |
|---|---|---|---|
| eval (31) | 87% | 97% | 0.92 |
| holdout (25) | 64% | 88% | 0.76 |
| holdout2 (20) | 70% | 85% | 0.78 |

Fusion comparison on all 76 queries combined:

| Method | hit@1 | hit@3 | MRR |
|---|---|---|---|
| Keyword only | 80% | 93% | 0.86 |
| Reciprocal rank fusion, embedding weight 1.0 | 75% | 91% | 0.83 |
| Reciprocal rank fusion, embedding weight 0.5 | 78% | 91% | 0.84 |
| Linear, embedding weight 0.5 | 83% | 93% | 0.88 |
| **Linear, embedding weight 1.0 (chosen)** | 83% | 93% | 0.88 |
| Linear, embedding weight 2.0 | 82% | 93% | 0.88 |

Chosen: linear. The keyword score is divided by the best keyword score, then the
embedding similarity (clipped at 0) is added with weight 1.0.

Final hybrid results:

| Set | hit@1 | hit@3 | MRR | avg output |
|---|---|---|---|---|
| eval (31) | 87% | 100% | 0.93 | 1,816 chars |
| holdout (25) | 80% | 88% | 0.85 | 1,786 chars |
| holdout2 (20) | 80% | 90% | 0.85 | 1,833 chars |

Warm search time: about 0.7 s keyword only, about 0.95 s hybrid.

## Run 6: orchestration (three whole projects, 37 subtasks)

Projects: `saas-invoicing` (15 subtasks), `mobile-fitness-app` (11), `unity-multiplayer-racer` (11).
Labels were written before the run. The subtasks were written by hand, so they are cleaner than
what an orchestrator would write.

| Mode | Whole-prompt coverage | Subtask hit@1 | Subtask hit@3 | Unique specialists (top 3 per subtask) | Chars per search |
|---|---|---|---|---|---|
| Keyword (BM25) | 39% | 68% | 86% | 29.3 per project | 669 |
| Embeddings only | 23% | 68% | 81% | 29.3 per project | 675 |
| **Hybrid** | 36% | **70%** | **89%** | 28.0 per project | 673 |

Whole-prompt coverage is the share of subtasks whose needed specialist is in the top 8
results of one search on the full project prompt.

Per project (hybrid): `saas-invoicing` whole-prompt 27%, subtask hit@3 80%;
`mobile-fitness-app` 27%, 100%; `unity-multiplayer-racer` 55%, 91%.

Hybrid subtask misses (4 of 37):
- "gather requirements and write user stories for invoicing": rank 4.
- "wireframes and information architecture for the invoice editor": not in the top 8.
- "user documentation and help center articles": rank 5.
- "game system architecture and code structure": rank 5.

---

## Run 7: switch to the upstream ONNX file (2026-11-23)

The model changed from the `onnx-models` export (no licence stated) to the upstream file
`onnx/model.onnx` in `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0), pinned to commit
`1110a243`. The upstream graph returns token vectors, so the plugin now applies mean pooling
and L2 normalisation itself. Both were checked against the export before the switch:

| Check | Result |
|---|---|
| Per-agent cosine similarity, export vs upstream (282 agents) | min, median and mean all 1.0000 (to four decimals) |
| Query cosine similarity, export vs upstream (76 queries) | min 1.0000, median 1.0000 |
| Top-3 results identical for all 76 queries | 100% overlap, top-1 identical for all 76 |

Accuracy after the switch (hybrid unless stated):

| Set | hit@1 | hit@3 | MRR | Change from Run 6 |
|---|---|---|---|---|
| eval (31) | 87% | 100% | 0.93 | none |
| holdout (25) | 80% | 88% | 0.85 | none |
| holdout2 (20) | 80% | 90% | 0.85 | none |
| Orchestration, subtask hit@3 (37) | 89% | | | none |

Output size changed by at most two characters per search. Tokenizer settings are unchanged:
truncation to 256 tokens, and padding to the longest text in each batch.

Packages: the pinned `onnxruntime` has no wheel for Python 3.15, so the setup now prefers
Python 3.14 and removes a failed virtualenv rather than leaving it behind.

---

## Caveats

- **Tuning versus holdout.** `eval.json` was used to choose the weights and synonyms.
  `holdout.json` was partly used to choose the fixes in Run 4. `holdout2.json` was the only set
  not used for choices, and it is the honest accuracy estimate: about 80% hit@1 and 90% hit@3.
- **Small samples.** One query is 2.5 to 4 points. Differences of one or two queries (for example
  hybrid against keyword search) are within noise.
- **Labels are judgements.** Each query lists the specialists the author judged right. Other agents
  may also fit, so scores understate accuracy. Labels were written before the runs they score,
  but `eval.json` was then used to tune the search, so its scores are optimistic.
- **Orchestration subtasks are hand-written.** An orchestrator's own decomposition is likely to be
  less tidy, so these numbers are probably optimistic.
- **Output size is a proxy.** "Chars per search" measures what a search adds to the conversation,
  not the tokens an orchestrator spends.
