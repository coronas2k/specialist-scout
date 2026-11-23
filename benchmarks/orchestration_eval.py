"""Score search for orchestrating a whole project (subagent team selection).

Two tests per mode:
  whole  : the full project prompt as one search (top 8). Coverage = share of
           subtasks whose needed specialist appears in that list.
  sub    : each subtask searched on its own (top 3 used). Reports hit@1, hit@3,
           unique specialists per project, and output size per search.
Run from the skill folder with its venv:  .venv/bin/python benchmarks/orchestration_eval.py [--mode hybrid]
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent          # benchmarks/
SKILL = HERE.parent
DATA = HERE / "data"
sys.path.insert(0, str(SKILL / 'scripts'))
import roster  # noqa: E402


def score(projects, searcher):
    whole_cov = []
    sub_hit1 = sub_hit3 = sub_n = 0
    team_sizes = []
    chars = 0
    per_project = {}
    for p in projects:
        covered = 0
        whole_ids = {a["id"] for a in searcher.rank(p["prompt"], limit=8)}
        team = set()
        for s in p["subtasks"]:
            if whole_ids & set(s["expect"]):
                covered += 1
        whole_cov.append(covered / len(p["subtasks"]))

        p_hit3 = 0
        for s in p["subtasks"]:
            ranked = searcher.rank(s["query"], limit=8)
            ids = [a["id"] for a in ranked]
            rank = next((k + 1 for k, x in enumerate(ids) if x in s["expect"]), None)
            sub_n += 1
            sub_hit1 += rank == 1
            sub_hit3 += bool(rank and rank <= 3)
            p_hit3 += bool(rank and rank <= 3)
            top3 = ranked[:3]
            chars += len(roster.format_results(top3))
            team.update(a["id"] for a in top3)
        team_sizes.append(len(team))
        per_project[p["project"]] = (round(covered / len(p["subtasks"]), 2), round(p_hit3 / len(p["subtasks"]), 2), len(team))
    return {
        "whole_cov": sum(whole_cov) / len(whole_cov),
        "whole_per_project": [round(x, 2) for x in whole_cov],
        "sub_hit1": sub_hit1 / sub_n,
        "sub_hit3": sub_hit3 / sub_n,
        "avg_team": sum(team_sizes) / len(team_sizes),
        "avg_chars": chars / sub_n,
        "per_project": per_project,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=None, choices=["hybrid", "bm25", "embed"])
    args = ap.parse_args()
    projects = json.loads((DATA / "project_eval.json").read_text(encoding="utf-8"))
    modes = [args.mode] if args.mode else ["bm25", "embed", "hybrid"]
    for mode in modes:
        s = roster.Searcher(mode)
        r = score(projects, s)
        print(f"{s.mode:7} whole-prompt coverage {r['whole_cov']:.0%} {r['whole_per_project']}  "
              f"subtask hit@1 {r['sub_hit1']:.0%} hit@3 {r['sub_hit3']:.0%}  "
              f"team size {r['avg_team']:.1f}  chars/search {r['avg_chars']:.0f}")
        for name, (cov, h3, team) in r["per_project"].items():
            print(f"        {name:22} whole-prompt cov {cov:.0%}   subtask hit@3 {h3:.0%}   team {team}")


if __name__ == "__main__":
    main()
