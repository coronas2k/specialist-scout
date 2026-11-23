"""Score a subagent picker against hybrid search on the workflow benchmark.

The picker is a subagent that reads the roster list and returns three ids per subtask. Its saved
output lives in benchmarks/results/picker-<date>.json, shaped as:
  {"<workflow>": {"<subtask number>": ["id", "id", "id"], ...}, ...}
Hybrid search is run live on the same subtasks, so both methods are scored on identical queries.

Usage (from the plugin folder, with the venv used for embeddings):
  $CLAUDE_PLUGIN_DATA/.venv/bin/python benchmarks/picker_eval.py benchmarks/results/picker-2026-11-23.json
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import roster  # noqa: E402


def main():
    picks_path = pathlib.Path(sys.argv[1])
    workflows = json.loads((HERE / "data" / "workflows.json").read_text(encoding="utf-8"))
    picks = json.loads(picks_path.read_text(encoding="utf-8"))
    known = {a["id"] for a in roster.agents()}
    searcher = roster.Searcher("hybrid")
    tot = {"n": 0, "h1": 0, "h3": 0, "p1": 0, "p3": 0, "invalid": 0}
    print(f"{'workflow':22} {'hybrid@1':>9} {'hybrid@3':>9} {'picker@1':>9} {'picker@3':>9} {'invalid':>8} {'team':>5}")
    for w in workflows:
        wp = picks.get(w["workflow"], {})
        wn = wh1 = wh3 = wp1 = wp3 = winv = 0
        team = set()
        for i, sub in enumerate(w["subtasks"], 1):
            expect = set(sub["expect"])
            hyb = [a["id"] for a in searcher.rank(sub["query"], limit=8)]
            hr = next((k + 1 for k, x in enumerate(hyb) if x in expect), None)
            pick = wp.get(str(i), [])
            valid = [x for x in pick if x in known]
            winv += len(pick) - len(valid)
            team.update(valid[:3])
            pr = next((k + 1 for k, x in enumerate(valid[:3]) if x in expect), None)
            wn += 1
            wh1 += hr == 1
            wh3 += bool(hr and hr <= 3)
            wp1 += pr == 1
            wp3 += bool(pr and pr <= 3)
        for k, v in zip(["n", "h1", "h3", "p1", "p3", "invalid"], [wn, wh1, wh3, wp1, wp3, winv]):
            tot[k] += v
        print(f"{w['workflow']:22} {wh1/wn:>9.0%} {wh3/wn:>9.0%} {wp1/wn:>9.0%} {wp3/wn:>9.0%} {winv:>8} {len(team):>5}")
    n = tot["n"]
    print(f"{'ALL':22} {tot['h1']/n:>9.0%} {tot['h3']/n:>9.0%} {tot['p1']/n:>9.0%} {tot['p3']/n:>9.0%} {tot['invalid']:>8}  (n={n})")


if __name__ == "__main__":
    main()
