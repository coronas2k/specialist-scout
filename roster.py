#!/usr/bin/env python3
"""Search the agency-agents roster without loading it into context.

Usage:
  roster.py search <words...> [--division d] [--limit n]
  roster.py divisions
  roster.py show <id>          # print the full path of one agent file

Roster root: $AGENCY_AGENTS_DIR, else ~/.agency-agents.
An agent is any .md file inside a division directory (listed in divisions.json)
whose YAML frontmatter has a `name:` key.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AGENCY_AGENTS_DIR", Path.home() / ".agency-agents"))


def divisions():
    data = json.loads((ROOT / "divisions.json").read_text())
    return list(data["divisions"].keys())


def frontmatter(path):
    """Minimal parser for flat `key: value` frontmatter, incl. folded/literal blocks."""
    lines = path.read_text(errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta, key, block = {}, None, None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key, val = m.group(1), m.group(2).strip()
            if val in (">", ">-", "|", "|-", ">+", "|+"):
                block, meta[key] = [], ""
            else:
                block = None
                meta[key] = val.strip("\"'")
        elif block is not None and key:
            block.append(line.strip())
            meta[key] = " ".join(x for x in block if x)
    return meta


def agents(only_division=None):
    for div in divisions():
        if only_division and div != only_division:
            continue
        for path in sorted((ROOT / div).rglob("*.md")):
            meta = frontmatter(path)
            if meta.get("name"):
                yield {
                    "id": path.stem,
                    "division": div,
                    "name": meta["name"],
                    "description": meta.get("description", ""),
                    "path": str(path),
                }


def score(agent, words):
    name = agent["name"].lower()
    ident = agent["id"].lower()
    desc = agent["description"].lower()
    total = 0
    for w in words:
        if w in name:
            total += 5
        if w in ident:
            total += 3
        if w in desc:
            total += 2
        if w in agent["division"]:
            total += 1
    return total


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if not (ROOT / "divisions.json").exists():
        print(f"agency-agents repo not found at {ROOT}", file=sys.stderr)
        return 1
    cmd, rest = argv[0], argv[1:]

    if cmd == "divisions":
        for div in divisions():
            print(f"{div}\t{sum(1 for _ in agents(div))}")
        return 0

    if cmd == "show":
        if not rest:
            print("show needs an agent id", file=sys.stderr)
            return 2
        want = rest[0].lower()
        for a in agents():
            if want in (a["id"].lower(), a["name"].lower()):
                print(a["path"])
                return 0
        print(f"no agent with id or name '{rest[0]}'", file=sys.stderr)
        return 1

    if cmd == "search":
        division, limit, words = None, 8, []
        i = 0
        while i < len(rest):
            if rest[i] == "--division" and i + 1 < len(rest):
                division, i = rest[i + 1], i + 2
            elif rest[i] == "--limit" and i + 1 < len(rest):
                limit, i = int(rest[i + 1]), i + 2
            else:
                words.extend(w for w in re.split(r"\W+", rest[i].lower()) if len(w) > 2)
                i += 1
        pool = list(agents(division))
        if words:
            ranked = sorted(((score(a, words), a) for a in pool), key=lambda t: -t[0])
            pool = [a for s, a in ranked if s > 0]
        for a in pool[:limit]:
            desc = a["description"]
            desc = desc if len(desc) <= 160 else desc[:157] + "..."
            print(f"{a['id']}  [{a['division']}]  {a['name']}\n    {desc}")
        if not pool:
            print("no matches; try broader words or `divisions`")
        return 0

    print(f"unknown command '{cmd}'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
