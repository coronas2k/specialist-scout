# Search evaluation

How `roster.py` ranks agents, how well it does, and what was tried. Numbers come
from `eval.py` on three labelled query sets.

## Query sets

| File | Queries | Used for | Notes |
|---|---|---|---|
| `eval.json` | 31 | Tuning | Synonyms and weights were chosen against these. Scores are optimistic. |
| `holdout.json` | 25 | Partly tuning | Written before any change. Four misses were then fixed with general synonyms and the name bonus, so scores are optimistic. |
| `holdout2.json` | 20 | Clean check | Written before any change. Only its label was corrected (a nonexistent id was removed). Use this set for the honest number. |

Each query lists the agents that would be a good answer. A hit at rank *k* means
one of them is in the top *k*. MRR is the mean of 1/rank, with 0 for a miss.
Every mode is scored with a result limit of 8.

## Results

| Set | Mode | hit@1 | hit@3 | MRR | Avg output |
|---|---|---|---|---|---|
| eval (31) | keyword (BM25) | 87% | 100% | 0.92 | 1,809 chars |
| eval (31) | embeddings only | 77% | 90% | 0.85 | 1,817 chars |
| eval (31) | **hybrid** | 87% | 100% | 0.93 | 1,816 chars |
| holdout (25) | keyword (BM25) | 72% | 88% | 0.80 | 1,783 chars |
| holdout (25) | embeddings only | 64% | 80% | 0.73 | 1,811 chars |
| holdout (25) | **hybrid** | 80% | 88% | 0.85 | 1,786 chars |
| holdout2 (20) | keyword (BM25) | 80% | 90% | 0.85 | 1,829 chars |
| holdout2 (20) | embeddings only | 65% | 85% | 0.72 | 1,833 chars |
| holdout2 (20) | **hybrid** | 80% | 90% | 0.85 | 1,833 chars |

On the clean set, hybrid and keyword search tie. The gain on the holdout set is
partly from fixes made after seeing its misses. The honest conclusion: hybrid is
no worse than keyword search, and the embeddings add value mainly for
paraphrased requests.

## Fusion methods tried

All on the three sets combined (76 queries), hit@3 and hit@1 shown.

| Method | hit@1 | hit@3 | MRR |
|---|---|---|---|
| Keyword only | 80% | 93% | 0.86 |
| Reciprocal rank fusion, embedding weight 1.0 | 75% | 91% | 0.83 |
| Reciprocal rank fusion, embedding weight 0.5 | 78% | 91% | 0.84 |
| Linear, embedding weight 0.5 | 83% | 93% | 0.88 |
| **Linear, embedding weight 1.0 (chosen)** | 83% | 93% | 0.88 |
| Linear, embedding weight 2.0 | 82% | 93% | 0.88 |

Reciprocal rank fusion discards how far apart the scores are, and it was worse
than keyword search alone. The linear blend keeps those gaps, and it was flat
across the 0.5 to 2.0 range.

## Changes that helped, and ones that didn't

- **Body weight 0.5 (not 1.0).** Long bodies that repeat common words ("pull request", "review") were beating agents whose name matched. This was the main fix for the code-review query.
- **Name bonus.** An agent whose full name appears in the query gets +5.
- **Synonyms.** Added for paraphrases seen in the holdout sets (for example "faster" and "slow" to performance, "projections" to forecasting, "OKR" to planning). All are general terms, not query-specific.
- **A "PR" synonym was removed.** It made the code-review query worse.

## Known misses (hybrid, current)

Hybrid misses 5 of the 76 queries (hit@3 about 93%):

- "make my landing page load faster" (holdout): not in the top 8. Drupal and WordPress performance specialists rank first.
- "container image vulnerability scan" (holdout): the right agent is 6th.
- "quarterly roadmap and OKR planning" (holdout): the right agent is 6th.
- "reduce bounce rate on our checkout page" (holdout2): not in the top 8. Needs marketing and conversion meaning, not keywords.
- "check my code for memory leaks" (holdout2): not in the top 8. Security agents rank first.

The tuning set has no hybrid misses.

Several misses need the request's meaning, not its words. This is where a
subagent-based picker, which reads the roster itself, would do better than either
search method.

## Reproducing

```bash
cd ~/.claude/skills/agency
.venv/bin/python eval.py --all          # every set, every mode
.venv/bin/python eval.py holdout2.json --mode hybrid --misses
```

Use the skill's venv: embedding modes need it.
