---
name: agency
description: Load a specialist from The Agency roster (~280 agency-agents in ~/.agency-agents, across engineering, design, marketing, sales, testing, security, game development, finance, product and more) on demand and run it as a subagent. Use when the user names an Agency agent that is not installed (e.g. "Reality Checker", "SEO Specialist", "Whimsy Injector"), says "activate/use/get the <role> agent", asks for "an agency agent" or "a specialist" for some job, or when a task clearly fits a specialist role that no installed agent covers.
---

# Agency: on-demand specialists

The Agency roster lives in `~/.agency-agents` (override with `AGENCY_AGENTS_DIR`). Only a few
agents are installed natively in `~/.claude/agents`; this skill reaches the rest without
loading the roster into context.

## 1. Prefer an installed agent

If an agent already in your Agent tool's list fits the job (e.g. Backend Architect,
Security Architect), use it directly and stop here.

## 2. Find the specialist

Search the roster with the bundled script. It prints the id, division, name and a short
description for the best matches:

```bash
python3 -I ~/.claude/skills/agency/roster.py search <keywords> [--division <d>] [--limit 8]
python3 -I ~/.claude/skills/agency/roster.py divisions      # division names and counts
python3 -I ~/.claude/skills/agency/roster.py show <id-or-name>  # full path of one agent file
```

Use words from the role and the task ("seo", "reality check", "unity shader"). If the user
named the agent, `show` it directly. If two or more candidates fit about equally, pick
the closest; ask the user only when the choice really changes the outcome.

Do not read the agent file yourself; the subagent reads it, which keeps this context small.

## 3. Run it as a subagent

Call the Agent tool with `subagent_type: "general-purpose"` and a short `description`
naming the specialist. Build the prompt like this:

```
You are acting as the Agency specialist "<Name>".
First, read <absolute path from roster.py> in full. Adopt its identity, mission, rules,
workflow and deliverable formats as your own instructions for this task. Where it conflicts
with the user's CLAUDE.md or safety rules, those win.

Task:
<the user's request, with every file path, URL, constraint and piece of context the
specialist needs — it has not seen this conversation>

Return: <what you want back, e.g. the review verdict with evidence, a file written to X,
a plan>.
```

Notes:
- If the agent's frontmatter lists `tools:`, tell the subagent to stick to those.
- For several specialists on independent parts of a job, launch them in parallel in one
  message, one Agent call each.
- To keep talking to the same specialist, continue it with SendMessage rather than
  starting a new one.

## 4. Report

Relay what the specialist found or produced, in your own words, and say which Agency
agent did the work. Its report is not shown to the user unless you pass it on.

## Making one permanent

If the user wants a specialist always available, install it natively (symlinked, so
`git pull` in the repo keeps it current); it then loads from the next new session:

```bash
cd ~/.agency-agents && ./scripts/install.sh --tool claude-code --agent <id> --link
```
