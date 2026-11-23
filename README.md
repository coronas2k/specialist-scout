<img src=".claude-plugin/icon.png" alt="Specialist scout icon" width="128">

# Specialist scout plugin for Claude Code

Find and run specialists from [The Agency](https://github.com/msitarzewski/agency-agents)
roster (about 280 agents) on demand. Only the specialist you need enters the conversation,
so the roster doesn't overload context. Nothing is downloaded until you ask.

## Requirements

- bash (macOS and Linux). Windows needs WSL or Git Bash, which I have not tested.
- git and curl, for the roster and the model download.
- Python 3.14 for the embedding setup. The pinned `onnxruntime` has no Python 3.15 wheel; the setup picks `python3.14` when it is installed.
- `shasum` or `sha256sum`, for checksums.

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

Claude writes four short phrases in the words a specialist's job description would use, searches with
the request and those phrases together, and picks from the merged shortlist of eight. It then runs the
chosen specialist as a subagent. For a whole project, it splits the work into subtasks and runs one
specialist per subtask.

On 100 new queries, writing the phrases raised the right pick from 41% to 59%. That figure comes from a
subagent test, so treat it as an estimate of the effect, not a guarantee.

You can also search from a terminal:

```bash
# replace <plugin folder> with the folder Claude Code installed the plugin in
python3 -I <plugin folder>/scripts/roster.py search "landing page conversion" --limit 5
python3 -I <plugin folder>/scripts/roster.py show "Reality Checker"
```

## What gets installed where

| Item | Where | Size | When |
|---|---|---|---|
| Roster (agency-agents) | `<data folder>/agency-agents` | about 11 MB | `/specialist-scout:setup roster` |
| Python packages for hybrid search | `<data folder>/.venv` | about 175 MB | `/specialist-scout:setup embeddings` |
| Embedding model (all-MiniLM-L6-v2, ONNX file and tokenizer) | `<data folder>/model` | 90 MB | `/specialist-scout:setup embeddings` |
| Saved search index | `<data folder>/index.npz` | 0.5 MB | built on first hybrid search |

`<data folder>` is `$CLAUDE_PLUGIN_DATA` when the host sets it. When it does not, which we observed for the
setup command in a live session, it is `~/.cache/specialist-scout`. Either way the folder is outside the
plugin's own files, so it survives plugin updates. Uninstalling may leave it behind; check it and delete it by
hand if you want the space back.

Downloads come from these sources only:
- `https://github.com/msitarzewski/agency-agents` (the roster)
- `https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2` (the model file and tokenizer, pinned to one commit, each file checked against a SHA-256 hash)
- the Python package index, for the pinned packages in `scripts/requirements.txt`

## Context cost

- Always loaded: the skill and setup command descriptions, about 110 tokens. Each search adds about 450 tokens (8 results), and the skill's instructions about 640 tokens, once per conversation when the skill is used.
- Not shipped: the 282 agent definitions. They stay on disk until searched.
- Hooks: none. The plugin doesn't run anything at session start.

Measurements, the method and what is still estimated: [docs/CONTEXT-COST.md](docs/CONTEXT-COST.md).

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

The plugin layout: `.claude-plugin/` (manifests and the 1024 px `icon.png`), `skills/specialist-scout/SKILL.md`,
`commands/setup.md`, `scripts/` (roster search, setup, pinned requirements), `benchmarks/`, `docs/`.
`docs/icon/plugin-icon.svg` is the icon's source. `docs/CONTEXT-COST.md` and `docs/search.md` hold the measurements.

## Licence

The plugin is MIT-licensed (see `LICENSE`). The agency-agents roster is MIT-licensed by its
authors. The embedding model is `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0, used as
published in its own repository. Third-party components and their licences are listed in
`THIRD_PARTY_NOTICES.md`.
