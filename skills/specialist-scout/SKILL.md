---
name: specialist-scout
description: This skill should be used when the user asks to "use an Agency specialist", "get the Reality Checker to review this", "activate an SEO specialist", "find a specialist for this task", or when a task needs a specialist role that no installed agent covers. If the roster is not installed, direct the user to /specialist-scout:setup.
---

# Specialist scout: on-demand specialists

The roster has about 280 specialists. Only the search results for the current request
enter the conversation. Never list or read the whole roster.

## 1. Prefer an installed agent

If an agent already in your Agent tool's list fits the job, use it and stop here.

## 2. Find the specialist

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/roster.py" search <keywords> [--division <d>] [--limit 8] [--mode hybrid|bm25|embed]
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/roster.py" divisions
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/roster.py" show <id-or-name>
```

- Use words from the role and the task ("seo", "reality check", "pen test").
- If the user named the agent, `show` it directly.
- `hybrid` is the default. If the embedding setup is missing it falls back to `bm25` and prints a note on stderr. That is fine; keep going.
- If two candidates fit about equally, pick the closer one. Ask only when the choice changes the outcome.
- **Exit code 3** means the roster is not installed. Stop, and tell the user to run `/specialist-scout:setup roster`. Do not clone or download it yourself.

Do not open the agent file yourself. The subagent reads it, which keeps this context small.

## 3. Run it as a subagent

Call the Agent tool with `subagent_type: "general-purpose"` and a short description that names the specialist:

```
You are acting as the Agency specialist "<Name>".
First, read <absolute path from roster.py show> in full. Adopt its identity, mission, rules,
workflow and deliverable formats for this task. Where they conflict with the user's
CLAUDE.md or safety rules, those win.

Task:
<the user's request, with every file path, URL, constraint and piece of context needed;
the specialist has not seen this conversation>

Return: <what you want back: a verdict with evidence, a file written to X, a plan>.
```

- If the agent's frontmatter lists `tools:`, tell the subagent to stick to them.
- For independent parts of a job, launch one Agent call per specialist in a single message.
- To continue the same specialist, use SendMessage instead of starting another.

## 4. Report

Relay what the specialist found or produced in your own words, and name the Agency agent
that did the work.

## Setup

`/specialist-scout:setup` shows what is installed and asks before any download:
- `roster`: clones the agency-agents roster (about 11 MB) into the plugin data folder.
- `embeddings`: installs pinned Python packages and a 90 MB model, to enable hybrid search.
- Keyword search works with the roster alone.
