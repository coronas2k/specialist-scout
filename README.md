# agency skill

A Claude Code skill that loads specialists from [The Agency](https://github.com/msitarzewski/agency-agents) roster on demand, so they don't all sit in context at once.

## Install

1. Clone the roster (any location; the default is `~/.agency-agents`):

   ```bash
   git clone https://github.com/msitarzewski/agency-agents.git ~/.agency-agents
   ```

2. Copy the skill into your Claude Code skills folder:

   ```bash
   mkdir -p ~/.claude/skills/agency
   cp SKILL.md roster.py ~/.claude/skills/agency/
   ```

3. Run `/reload-skills` or start a new session.

Set `AGENCY_AGENTS_DIR` if your roster lives somewhere other than `~/.agency-agents`.

## Use

Ask for a specialist by role or name, for example "use an SEO specialist on this page". The skill searches the roster with `roster.py` and runs the best match as a subagent.

Search from the command line:

```bash
python3 ~/.claude/skills/agency/roster.py divisions
python3 ~/.claude/skills/agency/roster.py search seo --division marketing
python3 ~/.claude/skills/agency/roster.py show "Reality Checker"
```

`roster.py` uses only the Python standard library and reads the roster's `divisions.json` and agent frontmatter. It doesn't modify the roster.
