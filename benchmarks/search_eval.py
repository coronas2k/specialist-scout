"""Score roster search against labelled query sets.

Usage (run from the skill folder with its venv so embedding modes work):
  .venv/bin/python benchmarks/search_eval.py                      # tuning set, hybrid
  .venv/bin/python benchmarks/search_eval.py holdout2.json --mode bm25
  .venv/bin/python benchmarks/search_eval.py --all                # every set, every mode
Reports hit@1, hit@3, MRR and the average output size per search (a proxy for context cost).
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent          # benchmarks/
SKILL = HERE.parent                                       # the skill folder
DATA = HERE / "data"
sys.path.insert(0, str(SKILL / 'scripts'))
import roster  # noqa: E402

SETS = ["eval.json", "holdout.json", "holdout2.json"]


def run(path, mode, searcher):
    cases = json.loads((DATA / path).read_text(encoding="utf-8"))
    hit1 = hit3 = 0
    mrr = 0.0
    chars = 0
    misses = []
    for case in cases:
        results = searcher.rank(case["query"], limit=8)
        out = roster.format_results(results)
        chars += len(out)
        ids = [a["id"] for a in results]
        rank = next((i + 1 for i, x in enumerate(ids) if x in case["expect"]), None)
        hit1 += rank == 1
        hit3 += bool(rank and rank <= 3)
        mrr += 1 / rank if rank else 0
        if not rank or rank > 3:
            misses.append((case["query"], rank, ids[:3]))
    n = len(cases)
    print(f"{path:16} {mode:7} n={n:<3} hit@1 {hit1/n:4.0%}  hit@3 {hit3/n:4.0%}  "
          f"MRR {mrr/n:.2f}  avg output {chars//n} chars")
    return misses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default="eval.json")
    ap.add_argument("--mode", default="hybrid", choices=["hybrid", "bm25", "embed"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--misses", action="store_true", help="print the misses")
    args = ap.parse_args()
    sets = SETS if args.all else [args.file]
    modes = ["bm25", "embed", "hybrid"] if args.all else [args.mode]
    for mode in modes:
        searcher = roster.Searcher(mode)
        for path in sets:
            misses = run(path, searcher.mode, searcher)
            if args.misses or not args.all:
                for query, rank, top in misses:
                    print(f"    MISS rank={rank} {query!r} top3={top}")


if __name__ == "__main__":
    main()
