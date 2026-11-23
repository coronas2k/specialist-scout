# agency skill

A Claude Code skill that finds a specialist from The Agency roster
(`~/.agency-agents`, about 280 agents) and runs it as a subagent. Only the
skill's one-line description sits in context; the roster is searched from
disk, so unused agents cost nothing.

## Contents

- `SKILL.md`: the instructions Claude follows when you ask for a specialist.
- `roster.py`: searches the roster. Keyword search (BM25) always works; hybrid search adds embeddings when set up.
- `eval.py` and `eval.json`, `holdout.json`, `holdout2.json`: the labelled test queries and scorer. See [docs/search.md](docs/search.md).
- `setup.sh`, `requirements.txt`, `requirements.lock.txt`: optional embedding setup.

## Install

1. Clone the roster:

   ```bash
   git clone https://github.com/msitarzewski/agency-agents.git ~/.agency-agents
   ```

2. Copy the skill into your Claude Code skills folder:

   ```bash
   mkdir -p ~/.claude/skills/agency
   cp SKILL.md README.md roster.py eval.py eval.json holdout.json holdout2.json \
      setup.sh requirements.txt requirements.lock.txt .gitignore ~/.claude/skills/agency/
   mkdir -p ~/.claude/skills/agency/docs && cp docs/search.md ~/.claude/skills/agency/docs/
   ```

3. Keyword search now works. Run `/reload-skills` or start a new session.

4. Optional: enable hybrid search (about 100 MB of packages plus a 90 MB model):

   ```bash
   cd ~/.claude/skills/agency && ./setup.sh
   ```

   `setup.sh` creates `.venv/`, installs the pinned packages, downloads the
   embedding model at a fixed Hugging Face commit, and checks each file's
   SHA-256. Re-running it skips anything already verified.

Set `AGENCY_AGENTS_DIR` if your roster lives somewhere other than `~/.agency-agents`.

## Use

Ask for a specialist by role or name, for example "use an SEO specialist on this
page". Claude searches the roster with `roster.py`, then runs the best match as a
subagent.

From the command line:

```bash
python3 -I ~/.claude/skills/agency/roster.py divisions
python3 -I ~/.claude/skills/agency/roster.py search "landing page conversion" --limit 5
python3 -I ~/.claude/skills/agency/roster.py search seo --division marketing --mode bm25
python3 -I ~/.claude/skills/agency/roster.py show "Reality Checker"
python3 -I ~/.claude/skills/agency/roster.py verify-model
```

`--mode` is `hybrid` (default), `bm25` or `embed`. If `.venv/` exists,
`roster.py` re-runs itself under it, so `python3` always works.

## How search works

1. **Keyword (BM25).** Each agent's name, id, description, division and the first
   8,000 characters of its body form a weighted document. Queries and documents
   go through the same light stemming, stopword removal and synonym map (for
   example "front-end" matches "frontend", and "SEO" matches "search engine
   optimization"). An agent whose full name appears in the query gets a bonus.
2. **Embeddings (optional).** `all-MiniLM-L6-v2` (384 dimensions), run through
   ONNX Runtime on the CPU. The whole roster is embedded once and saved to
   `index.npz`. The index rebuilds only when an agent file changes or the model
   checksum changes.
3. **Hybrid.** Keyword score scaled to 0..1 by the best match, plus the
   embedding similarity. Equal weights were flat between 0.5 and 2.0.

Accuracy and the comparison of modes are in [docs/search.md](docs/search.md).

## Cost and performance

| | Size on disk | Per search (warm) | Context used |
|---|---|---|---|
| Keyword only | 0 | about 0.7 s | about 450 tokens of results |
| Hybrid | about 275 MB (`.venv` 175 MB, model 97 MB, index 0.5 MB) | about 1 s | same |

Search output is capped by `--limit` (default 8). The embedding model runs
only in your shell, so it never enters the conversation.

## Updating

- **Roster:** `git -C ~/.agency-agents pull`. Keyword search picks up changes at once. Hybrid rebuilds the index on the next search.
- **Model:** change the commit in `setup.sh` and the three checksums in `roster.py` together, then run `setup.sh` and `eval.py --all`.
- **Packages:** change `requirements.txt`, regenerate `requirements.lock.txt` with `.venv/bin/python -m pip freeze`, and re-run the eval.

## Troubleshooting

- **"note: keyword search only" on stderr.** The venv, model or checksum isn't in place. Run `./setup.sh`, then `roster.py verify-model`.
- **Checksum mismatch.** Delete `model/`, then run `./setup.sh` again.
- **Search seems stale after an edit.** Agent files are indexed by modification time. Touch the file or re-run the search to rebuild.
- **Results missing one specialist.** Try `--mode bm25 --limit 20` to see what keyword matching returns, or name the specialist directly with `show`.

## Licence and provenance

- The Agency roster is from [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents).
- The embedding model is [onnx-models/all-MiniLM-L6-v2-onnx](https://huggingface.co/onnx-models/all-MiniLM-L6-v2-onnx), an ONNX export of [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). The ONNX repo has no licence tag; confirm the upstream terms before commercial use.
