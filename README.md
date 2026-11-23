# Specialist scout plugin for Claude Code

Find and run specialists from [The Agency](https://github.com/msitarzewski/agency-agents)
roster (about 280 agents) on demand. Only the specialist you need enters the conversation,
so the roster doesn't overload context. Nothing is downloaded until you ask.

## Install

In Claude Code:

```
/plugin marketplace add coronas2k/specialist-scout
/plugin install specialist-scout@agency-tools
```

Then install the roster (asks before downloading):

```
/specialist-scout:setup roster
```

Optional, for better matching of paraphrased requests (about 275 MB: Python packages and
a model):

```
/specialist-scout:setup embeddings
```

Check what is installed at any time with `/specialist-scout:setup` (no argument).

If you already have the roster cloned at `~/.agency-agents`, `/specialist-scout:setup roster` uses it
and downloads nothing.

## Use

Ask for a specialist by role or name:

- "use an SEO specialist to review this landing page"
- "get the Reality Checker to judge whether this is production ready"
- "have a frontend developer build the settings page, and a QA specialist test it"

Claude searches the roster, then runs the best match as a subagent. For a whole project, it
splits the work into subtasks and runs one specialist per subtask.

You can also search from a terminal:

```bash
# replace <plugin folder> with the folder Claude Code installed the plugin in
python3 -I <plugin folder>/scripts/roster.py search "landing page conversion" --limit 5
python3 -I <plugin folder>/scripts/roster.py show "Reality Checker"
```

## What gets installed where

| Item | Where | Size | When |
|---|---|---|---|
| Roster (agency-agents) | `$CLAUDE_PLUGIN_DATA/agency-agents` | about 11 MB | `/specialist-scout:setup roster` |
| Python packages for hybrid search | `$CLAUDE_PLUGIN_DATA/.venv` | about 175 MB | `/specialist-scout:setup embeddings` |
| Embedding model (all-MiniLM-L6-v2, ONNX file and tokenizer) | `$CLAUDE_PLUGIN_DATA/model` | 90 MB | `/specialist-scout:setup embeddings` |
| Saved search index | `$CLAUDE_PLUGIN_DATA/index.npz` | 0.5 MB | built on first hybrid search |

`$CLAUDE_PLUGIN_DATA` is the plugin's own data folder, which survives plugin updates. Uninstalling
may leave it behind; check it and delete it by hand if you want the space back.

Downloads come from these sources only:
- `https://github.com/msitarzewski/agency-agents` (the roster)
- `https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2` (the model file and tokenizer, pinned to one commit, each file checked against a SHA-256 hash)
- the Python package index, for the pinned packages in `scripts/requirements.txt`

## Context cost

- Always loaded: the skill's one-line description. The search results are added only when you ask for a specialist, about 450 tokens.
- Not shipped: the 282 agent definitions. They stay on disk until searched.
- Hooks: none. The plugin doesn't run anything at session start.

## Search modes

- `hybrid` (default when `/specialist-scout:setup embeddings` has been run): keyword and embedding scores combined.
- `bm25`: keyword matching only. Needs nothing beyond the roster.

The first hybrid search after setup builds the index, which takes a few seconds.

## Accuracy

Measured on labelled query sets (see `benchmarks/`). On the clean holdout set, hybrid finds
the right specialist in the top 3 for 90% of requests (80% in first place). For whole
projects, search one subtask at a time; a single search for a full project covers under
40% of the roles needed. Details in `docs/search.md` and `benchmarks/results/RESULTS.md`.

## Troubleshooting

- **"Agency roster not found"** (exit code 3): run `/specialist-scout:setup roster`, or set `AGENCY_AGENTS_DIR`.
- **"keyword search only" note**: the embedding setup is missing. Run `/specialist-scout:setup embeddings`, or ignore it; keyword search still works.
- **Checksum mismatch during setup**: nothing is installed. Run the same setup step again; if it fails twice, the upstream file changed and the pin needs updating.
- **Search seems stale**: the index rebuilds when an agent file changes. Re-run the search.

## Development

```bash
benchmarks/run_all.sh       # every benchmark, saved to benchmarks/results/
```

The plugin layout: `.claude-plugin/` (manifests), `skills/specialist-scout/SKILL.md`, `commands/setup.md`,
`scripts/` (roster search, setup, pinned requirements), `benchmarks/`, `docs/`.

## Licence

The plugin is MIT-licensed (see `LICENSE`). The agency-agents roster is MIT-licensed by its
authors. The embedding model is `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0, used as
published in its own repository. Third-party components and their licences are listed in
`THIRD_PARTY_NOTICES.md`.
