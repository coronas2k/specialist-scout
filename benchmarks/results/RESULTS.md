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

## Run 8: subagent picker on four new workflows (2026-11-23)

Four workflows that the earlier sets did not cover (`benchmarks/data/workflows.json`): an
open-source library release, a sales KPI dashboard, a healthcare booking app and a SaaS support
chatbot. Labels were written before any search or picker ran. Each workflow was given to one
subagent (the picker), which read the roster list and returned three specialists per subtask. Raw
picker output is saved as returned in `benchmarks/results/picker-2026-11-23.json`.

| Workflow | Hybrid hit@1 | Hybrid hit@3 | Picker hit@1 | Picker hit@3 | Invalid picks |
|---|---|---|---|---|---|
| OSS library release (8) | 25% | 50% | 75% | 88% | 0 |
| Sales KPI dashboard (7) | 29% | 86% | 0%* | 0%* | 21 |
| Healthcare booking app (8) | 75% | 75% | 88% | 100% | 0 |
| SaaS support chatbot (7) | 43% | 57% | 86% | 100% | 0 |
| All (30) | 43% | 67% | 63% | 73% | 21 |

\* The sales picker returned 1-based line numbers from the roster list instead of agent ids. The
scorer counts those as invalid, so the strict result above is 0%. Diagnostic only: mapping the
numbers to the lines they index gives picker hit@1 6 of 7 and hit@3 7 of 7, with 15 distinct
specialists. That mapping is not part of the scored result.

On the 23 subtasks where every pick was a valid id, the difference is clear:

| Method | hit@1 | hit@3 |
|---|---|---|
| Hybrid search | 11 of 23 (48%) | 14 of 23 (61%) |
| Picker | 19 of 23 (83%) | 22 of 23 (96%) |

Cost: the harness reported about 92,000 tokens for each picker call (about 369,000 across the four).
Hybrid search costs about 450 tokens of results per query and no model call. The picker reads the
roster list, so it is far more expensive per lookup, and it runs in a subagent.

Team size: the picker's three picks per subtask gave 15 to 24 distinct specialists per workflow.
A lead agent would normally take only the top pick, which is right on 19 of 23 valid subtasks.

Read the result as a trade-off, not a verdict. Hybrid search is cheap and fails on paraphrases;
the picker is accurate on paraphrases and costs a model call per workflow. A lead agent can decide
on the picker for planning and keep hybrid search for quick lookups.

---

## Run 9: trying to close the gap to the picker (2026-11-23)

Goal: raise hybrid search on the workflow subtasks toward the picker's accuracy. Hybrid found the
right specialist in the top three on 20 of 30 workflow subtasks; keyword search and embeddings alone
found 17 each. The misses were mostly paraphrases (for example "review pull requests" for the code
reviewer, and "cost and latency of model calls" for FinOps).

Text embedded for each specialist (hybrid only, current model, all query sets: counts out of 106 queries):

| Text | hit@1 (of 106) | hit@3 (of 106) |
|---|---|---|
| name, description, vibe (current) | 76 | 91 |
| name and description | 76 | 90 |
| name, description, vibe, first 600 characters of the body | 75 | 89 |
| name, description, vibe, first 1,200 characters of the body | 75 | 90 |

The current text is as good as any alternative, so the body does not explain the gap.

Embedding model (all 106 queries; bge-small-en-v1.5 is MIT, ONNX from its own repository at commit
5c38ec7c, checksum verified, CLS pooling):

| Model | Mode | hit@1 | hit@3 |
|---|---|---|---|
| MiniLM (current) | embeddings alone | 60% | 77% |
| bge-small | embeddings alone | 63% | 79% |
| bge-small with query prefix | embeddings alone | 65% | 77% |
| MiniLM (current) | hybrid | 72% | 86% |
| bge-small | hybrid | 70% | 86% |
| bge-small with query prefix | hybrid | 71% | 86% |

bge-small is marginally better on its own but makes no difference to hybrid search, so it is not
worth a 133 MB download and a change to the setup. The reasons are in
`benchmarks/results/DECISION-keep-minilm.md`. Scripts: `benchmarks/experiments/text_variants.py`
and `benchmarks/experiments/bge_compare.py`.

Still open: a cross-encoder reranker (bge-reranker-base is MIT, but its ONNX file is 1.1 GB) reads the
query and each candidate together, which is closer to how the picker works. It is the one lever not
yet tested.

---

## Run 13: six other embedding models in the plugin's hybrid search (2026-11-23)

Each model replaces MiniLM in the plugin's own hybrid search (keyword plus embeddings, the same
linear blend), on all 106 queries. Each file was checked against its published checksum, and each
tokenizer against git's blob hash. Pooling and query prefixes follow each model's configuration:
arctic-embed uses CLS pooling and a query prefix; e5 uses `query:` and `passage:`; nomic uses
`search_query:` and `search_document:`. The nomic file is the int8 quantised version (137 MB), since
its fp32 file is 547 MB. Times are on this Mac, CPU only.

| Model | Size | Embedding only, hit@1 / hit@3 | Hybrid, hit@1 / hit@3 | Query time | Index build |
|---|---|---|---|---|---|
| MiniLM-L6 (current) | 90 MB | 64 / 82 | 76 / 91 | 1.6 ms | 12 s |
| arctic-embed-xs | 90 MB | 69 / 86 | 75 / 91 | 2.6 ms | 10 s |
| arctic-embed-s | 133 MB | 68 / 82 | 76 / 91 | 4.9 ms | 21 s |
| all-MiniLM-L12-v2 | 133 MB | 67 / 78 | 76 / 91 | 3.7 ms | 21 s |
| gte-small | 133 MB | 73 / 85 | 74 / 88 | 4.0 ms | 21 s |
| e5-small-v2 | 133 MB | 71 / 79 | 74 / 90 | 4.4 ms | 22 s |
| nomic-embed-text-v1.5 (int8) | 137 MB | 61 / 78 | 74 / 89 | 7.7 ms | 542 s |

Verdict: no model improves hybrid search. Several are better on their own: gte-small reaches first
place on 73 queries, against 64 for MiniLM, and arctic-embed-xs reaches the top three on 86, against
82. None of that carries into the hybrid, which stays at about 86% in the top three for every model.
The hybrid is limited by how its parts are combined, and by queries that need meaning rather than
vocabulary, not by the choice of embedding model. Script: `benchmarks/experiments/embed_models.py`.

---

## Run 14: tuning the hybrid per embedding model, with a train/validation split (2026-11-23)

Split: tuning on `eval.json` and `holdout.json` (56 queries); validation on `holdout2.json` and the
workflows (50 queries). Settings were chosen on the tuning split only, and the grid covered BM25 `k1`
(0.9, 1.2, 1.6), `b` (0.5, 0.75, 1.0), body weight (0, 0.5, 1), name bonus (0, 5, 10), fusion weight
(0.5 to 2.0), and two normalisations (`max` as in the plugin, and `minmax`). The harness reproduces the
plugin's default hybrid: MiniLM at default settings gives 76 first-place and 91 top-three hits across
all 106 queries.

Validation split (50 queries):

| Model | Settings | hit@1 | hit@3 | MRR |
|---|---|---|---|---|
| MiniLM-L6 (current) | default | 29 | 38 | 0.68 |
| MiniLM-L6 | tuned | 30 | 39 | 0.70 |
| arctic-embed-xs | default | 28 | 38 | 0.67 |
| arctic-embed-xs | tuned | 31 | 39 | 0.71 |
| gte-small | default | 28 | 35 | 0.65 |
| gte-small | tuned | 31 | 40 | 0.71 |

Tuned settings: MiniLM `k1` 1.6, `b` 0.75, body weight 0.5, name bonus 5, fusion weight 2.0 (max);
arctic-embed-xs `k1` 1.6, `b` 0.5, body weight 0.5, name bonus 10, fusion weight 2.0 (max); gte-small
`k1` 1.6, `b` 0.75, body weight 0.5, name bonus 5, fusion weight 0.5 (minmax).

Verdict: tuning gains one to three queries out of 50 on the validation split, which is within noise.
gte-small tuned is the best validation result (31 and 40, MRR 0.71), one query ahead of tuned MiniLM
on first place and one on the top three. Three things argue against changing the plugin on this
evidence alone: the settings differ between models, the best `k1` sits at the edge of the grid, and
the validation split was used in earlier diagnosis. A fresh labelled set is needed before any change.
Script: `benchmarks/experiments/tune_hybrid.py`.

---

## Run 15: can arctic-embed-xs beat MiniLM once tuned? Cross-validation over 106 queries (2026-11-23)

Five folds, deterministic shuffle. For each fold, the hybrid settings are chosen on the other four
folds and scored on the held-out fold, so every query is scored by settings that never saw it. The
default column uses the plugin's fixed settings for reference.

| Model | Default: hit@1 / hit@3 / MRR | Tuned by cross-validation: hit@1 / hit@3 / MRR |
|---|---|---|
| MiniLM-L6 (current) | 76 / 91 / 0.80 | 76 / 94 / 0.80 |
| arctic-embed-xs, with query prefix | 75 / 91 / 0.78 | 76 / 92 / 0.80 |
| arctic-embed-xs, no query prefix | 75 / 89 / 0.78 | 79 / 89 / 0.80 |
| Ensemble: arctic-embed-xs and MiniLM (two models) | 75 / 91 / 0.79 | 77 / 95 / 0.81 |

Verdict: arctic-embed-xs does not beat MiniLM. With its prefix it ties on first place and trails by
two queries in the top three. Without the prefix it is better on first place (79 against 76) and
worse in the top three (89 against 94), so the prefix trades one for the other. Tuning helps MiniLM
by three queries in the top three, and the chosen settings were mostly the same across folds
(min-max fusion, `b` 1.0). The ensemble is the best row, but it needs two models (about 180 MB together).

Limits: the best settings often sit at the edge of the grid (`k1` 1.6 and `b` 1.0), so a wider grid
might change them. Differences of two or three queries are within noise on 106 queries.
Script: `benchmarks/experiments/cv_hybrid.py`.

---

## Run 16: widened grid, cross-validated, 106 queries (2026-11-23)

Same five-fold protocol as Run 15, with a wider grid: BM25 `k1` 0.6 to 2.4, `b` 0 to 1, body weight 0
to 1, name bonus 0 to 20, fusion weight 0.25 to 4, and two normalisations. Keyword scores and rank
metrics are vectorised; the keyword scores match the loop version to rounding error.

| Model | Default: hit@1 / hit@3 / MRR | Widened grid, cross-validated: hit@1 / hit@3 / MRR |
|---|---|---|
| MiniLM-L6 (current) | 76 / 91 / 0.80 | 74 / 93 / 0.79 |
| arctic-embed-xs, with prefix | 75 / 91 / 0.78 | 79 / 92 / 0.82 |
| arctic-embed-xs, no prefix | 75 / 89 / 0.78 | 78 / 89 / 0.79 |
| gte-small | 74 / 88 / 0.77 | 77 / 92 / 0.80 |
| Ensemble (two models) | 75 / 91 / 0.79 | 77 / 92 / 0.81 |

Compared with Run 15 (narrow grid), MiniLM fell from 76 to 74 on first place, and arctic-embed-xs with
prefix rose from 76 to 79. So the grid choice alone moves these results by two to three queries.

Reading: arctic-embed-xs with its prefix is the first setting in these runs to beat MiniLM on first
place (by five queries) and on MRR, while trailing by one query in the top three. That is not yet
established. Arctic's chosen `k1` sat at the new maximum (2.4) in four of five folds, so the grid is
still too narrow for it, and the chosen settings change from fold to fold. Several queries separate
the two models, and the difference is smaller than the swing from the grid change. Next steps would
be a wider `k1` range and a new labelled set.
Script: `benchmarks/experiments/cv_hybrid_wide.py`.

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
