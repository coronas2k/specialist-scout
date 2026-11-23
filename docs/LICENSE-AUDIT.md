# Licence audit: Agency skill and plugin

Status: draft for review. Prepared from the licence metadata and file contents available on
this machine and on GitHub / Hugging Face. This is a technical inventory, not legal advice.

Scope: the code and data in `coronas2k/claude-agency-skill`, the skill folder installed at
`~/.claude/skills/agency`, and everything the plugin downloads or installs.

## 1. Summary

| Item | Licence | Shipped in our repo? | Obligation today | Obligation if we redistribute it |
|---|---|---|---|---|
| Our code and benchmark data | **none chosen** | yes | none, but the plugin directory requires a LICENSE file | choose one (see section 5) |
| agency-agents roster | MIT (Copyright 2025 AgentLand Contributors) | no, fetched at runtime | none; attribution is in the README | include the MIT notice with any copy |
| all-MiniLM-L6-v2 (upstream ONNX file and tokenizer) | Apache-2.0 | no, downloaded at runtime | none | Apache-2.0 text, upstream notices, note any modification |
| Python packages (`requirements.lock.txt`) | MIT, BSD-3, Apache-2.0, MPL-2.0, others | no, installed by pip | none | include each licence text |
| Arabic content skill (`content-creator-ar`) | CC0-1.0 | no, separate install | none | none |
| Plugin docs, fast-compact, Hermes code | Apache-2.0, MIT, MIT | no (consulted only) | none; no text copied | none |

Nothing we ship currently copies third-party code or text. The obligations start only if we
redistribute the roster, the model file, or the installed packages.

## 2. Files and sources used to derive the skill

Listed in the order they were used. "Read" means the file was opened; "scanned" means every
line was compared against our files (section 3).

### 2.1 agency-agents roster (`~/.agency-agents`, MIT)

| File | Used for | How |
|---|---|---|
| `LICENSE` | licence | read |
| `divisions.json` | list of divisions for search and for `divisions` command | read; the structure, not text |
| `integrations/claude-code/README.md` | install idea (copy agents into `~/.claude/agents`) | read |
| `integrations/hermes/README.md` | lazy-router idea: keep the roster on disk, load only what is needed | read |
| `scripts/build-hermes-plugin.py` | design of the search scoring (name bonus, body capped at 8,000 characters, slug aliasing) | read; influenced the design, no lines copied (section 3) |
| `scripts/install.sh --help` (output) | install options, for the setup script's wording | run |
| Frontmatter of agent files, e.g. `testing/testing-reality-checker.md` | field names (`name`, `description`, `vibe`) for the parser | read; key names counted across all agents, no content copied |

The agent definitions themselves are not in our repository. The roster is cloned at runtime
into the user's plugin data folder, or read from `~/.agency-agents`.

### 2.2 Embedding model (upstream, Apache-2.0)

| Source | Used for |
|---|---|
| `sentence-transformers/all-MiniLM-L6-v2`, `onnx/model.onnx` and `tokenizer.json`, pinned to commit `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | downloaded, SHA-256 checked (`6fd5d72f…` and `be50c362…`), run with ONNX Runtime |
| The same repository's model card (licence tag `apache-2.0`) | licence: **Apache-2.0** |

Switched on 2026-11-23 from the `onnx-models/all-MiniLM-L6-v2-onnx` export, which states no
licence. Vectors from the two files agree to four decimal places for all 282 agents and all 76
test queries give the same top-3 results (see `benchmarks/results/RESULTS.md`, Run 7).

### 2.3 Libraries and documentation consulted

| Source | Licence | Used for |
|---|---|---|
| ONNX Runtime Python API docs (via Context7) | MIT (onnxruntime) | `InferenceSession` usage |
| Hugging Face tokenizers docs (via Context7) | Apache-2.0 | padding and truncation settings |
| Pinned packages, read from installed metadata | see section 4 | installed by `setup.sh` |

### 2.4 Plugin structure

| Source | Licence | Used for |
|---|---|---|
| `plugin-dev` plugin, `skills/plugin-structure/SKILL.md`, `skills/command-development/SKILL.md`, `skills/plugin-settings/SKILL.md`, `skills/mcp-integration/references/server-types.md` (under `~/.claude/plugins/marketplaces/claude-plugins-official/`) | Apache-2.0 | directory layout, `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` behaviour, command syntax |
| `fast-compact` marketplace manifest (`~/.claude/plugins/marketplaces/fast-compact/.claude-plugin/marketplace.json`) | MIT | shape of our `marketplace.json` |
| `claude plugin --help`, `claude plugin validate --help` (CLI 2.1.322) | n/a | command names and options |

### 2.5 Other content

| Source | Licence | Used for |
|---|---|---|
| `AmjadShakhshir/awesome-claude-arabic`, `skills/arabic-content-creation.md` | **CC0-1.0** | the `content-creator-ar` skill, installed at `~/.claude/skills/content-creator-ar/` (not part of the plugin) |
| Benchmark queries and labels in `benchmarks/data/` | ours | written for this project; expected answers are roster IDs |
| Synonym map, stopword list, BM25 scoring | ours; BM25 is a published algorithm (no licence needed for the method) | `scripts/roster.py` |
| Setup, roster and search code | ours | `scripts/`, `skills/agency/`, `commands/` |

## 3. Copying check

Method: every line of 40 characters or more in our files was compared, after whitespace
normalisation, with every line in the roster's Markdown, Python and shell files and the
`plugin-dev` documentation.

- Our files scanned: 39 (repo and skill folder, excluding the virtualenv, model and caches)
- Distinct lines of 40+ characters: 728
- Reference files scanned: 413
- **Exact matches: 0**

Limits of this check: it catches verbatim copying of whole lines only. It does not catch
short phrases, copied logic that is reworded, or copied structure. It covers the roster and
plugin docs only, not the other sources in section 2.5. The Hermes code was read for design
and not copied, but a reworded copy would not show up here.

## 4. Pinned Python packages (`scripts/requirements.lock.txt`)

Licence fields are from installed package metadata. Where the metadata is blank, the
classifier or upstream project is noted.

| Package | Version | Licence | Note |
|---|---|---|---|
| onnxruntime | 1.32.0 | MIT | |
| tokenizers | 0.23.3 | Apache-2.0 (classifier) | licence field is blank; confirm the upstream LICENSE file |
| numpy | 2.5.5 | BSD-3-Clause, plus 0BSD, MIT, Zlib, CC0-1.0 for bundled parts | |
| huggingface_hub | 2.4.0 | Apache-2.0 | transitive |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | file-level copyleft; we do not modify tqdm |
| protobuf | 7.36.2 | BSD-3-Clause | transitive |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | transitive |
| typing_extensions | 4.16.0 | PSF-2.0 | transitive |
| anyio, filelock, h11, PyYAML, truststore | various | MIT | transitive |
| click, fsspec, httpcore2, httpx2, idna | various | BSD-3-Clause | transitive |
| flatbuffers | 25.12.19 | Apache-2.0 | transitive |
| hf-xet | 1.8.0 | Apache-2.0 | transitive |

We do not redistribute these packages. pip downloads them at install time. If we ever
publish a bundled environment, each licence text must go with it.

## 5. Gaps and decisions

1. **Our licence is not chosen.** The plugin directory refuses submission without a LICENSE
   file. MIT would match the roster and fast-compact, and it is the simplest option.
   Decision needed: licence and copyright holder name.
2. **Resolved.** The model now comes from the upstream repository, which is Apache-2.0. The
   unlicensed export is no longer used.
3. **tokenizers has no licence field in its metadata.** Its classifier says Apache-2.0, and the
   upstream repository (huggingface/tokenizers) is Apache-2.0. Confirmed on 2026-11-23.
4. **tqdm is MPL-2.0.** No action while we use it unmodified. Note it in any notices file.
5. **The Arabic skill is separate.** It is not in the plugin, so its CC0 terms do not affect
   the plugin. If it is ever bundled, CC0 needs no notice.

## 6. Recommended actions

- Add a `LICENSE` file with the licence you choose (recommended: MIT), and a copyright line.
- Add `THIRD_PARTY_NOTICES.md` listing the roster (MIT, AgentLand Contributors), the model
  (upstream Apache-2.0), and the packages in section 4.
- Keep downloading the roster and the model at runtime rather than committing them. This
  avoids redistribution obligations.
- Keep `.venv/`, `model/` and `index.npz` out of Git. They already are, via the plugin data
  folder and `.gitignore`.
- Before any public release: the model and tokenizer are confirmed (section 2.2 and item 3 above). Choose the licence for our code (section 5, item 1) and keep the notices file current.
