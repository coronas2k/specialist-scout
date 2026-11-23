# Benchmarks

Measures how well `roster.py` finds the right Agency specialists. Two kinds of test:

- **Search accuracy** (`search_eval.py`): single requests such as "make my landing page load faster". Scored per mode (keyword, embeddings, hybrid).
- **Orchestration** (`orchestration_eval.py`): whole projects split into subtasks, the way a lead agent would use search to pick a team.

Plus `fusion_experiment.py`, which compares ways of combining keyword and embedding scores.

Full history, every number and every change is in [results/RESULTS.md](results/RESULTS.md).

## Layout

```
benchmarks/
  README.md                 this file
  run_all.sh                runs everything and saves results/<date>-run.txt
  search_eval.py            search accuracy: hit@1, hit@3, MRR, output size
  orchestration_eval.py     whole-project coverage and per-subtask accuracy
  fusion_experiment.py      keyword/embedding fusion comparison
  data/
    eval.json               31 queries (used for tuning)
    holdout.json            25 queries (partly used for tuning)
    holdout2.json           20 queries (clean; the honest check)
    project_eval.json       3 projects, 37 subtasks, with expected specialists
  results/
    RESULTS.md              history of every run
    <date>-run.txt          raw output of run_all.sh
```

## Running

Run from the skill folder, with its virtualenv (embedding modes need it):

```bash
cd ~/.claude/skills/agency
.venv/bin/python benchmarks/search_eval.py --all            # every set, every mode
.venv/bin/python benchmarks/search_eval.py holdout2.json --mode hybrid --misses
.venv/bin/python benchmarks/orchestration_eval.py           # project-level test
benchmarks/run_all.sh                                       # everything, saved to results/
```

Each run takes a few seconds once the index is built.

## Metrics

| Metric | Meaning |
|---|---|
| hit@1 | share of queries whose right specialist ranks first |
| hit@3 | share whose right specialist is in the top 3 |
| MRR | mean of 1/rank, 0 for a miss; rewards getting it near the top |
| avg output | characters per result list, a proxy for the context a search adds |
| whole-prompt coverage | share of subtasks whose specialist is in the top 8 of one search for the full project prompt |
| unique specialists | distinct agents across the top 3 of every subtask in a project (a proxy for team size) |

## Query data

Each entry lists the specialists a good answer would include. Any one of them in
the top k counts as a hit at k.

```json
{"query": "accessibility audit of my website", "expect": ["testing-accessibility-auditor", "engineering-section-508-specialist"]}
```

Projects in `project_eval.json` have a `prompt` (the whole project) and `subtasks`
(each with its own `query` and `expect`).

To add a case, check that every id exists:

```bash
.venv/bin/python -c "import sys; sys.path.insert(0, '.'); import roster; print(sorted({a['id'] for a in roster.agents()})[:5])"
```

Use a new file for new queries, and don't tune on it. Keep a clean set for the final number.

## Which set to trust

- `eval.json`: used to choose weights and synonyms. Scores are optimistic.
- `holdout.json`: some misses were fixed after seeing them. Optimistic.
- `holdout2.json`: never used for choices. This is the honest estimate.
- `project_eval.json`: written before the runs, but the subtasks are hand-written, so they are cleaner than a lead agent's own.

## Current headline numbers

From the latest run (see [results/RESULTS.md](results/RESULTS.md) for every run):

| | Keyword | Embeddings | Hybrid |
|---|---|---|---|
| holdout2 hit@1 / hit@3 (clean) | 80% / 90% | 65% / 85% | 80% / 90% |
| Subtask hit@3 (orchestration, 37) | 86% | 81% | 89% |

For projects, search one subtask at a time. A single search on the whole project
prompt covers only 23 to 39% of the needed roles, in every mode.

## Caveats

- Labels are judgements. Scores understate accuracy when other agents also fit.
- Samples are small: one query is 2.5 to 4 points. Mode differences of a couple of queries are within noise.
- Speed and size are not benchmarked here. See the main README for timings.
