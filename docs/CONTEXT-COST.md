# Context cost: plugin versus loading the roster

Measured on 2026-11-23. This records how much conversation context the plugin uses compared
with the alternatives, how the numbers were produced, and what is still an estimate.

## Summary

| Approach | Always loaded | One specialist request | Ten requests |
|---|---|---|---|
| Whole roster installed as native agents | about 25,100 tokens | nothing extra | still about 25,100 |
| One agent file loaded by hand | nothing | about 2,700 tokens per agent | about 27,000 if each is loaded |
| This plugin | about 110 tokens | about 900 to 1,200 tokens, once the skill is invoked | about 2,400 to 5,300 |

- Break-even against the native roster listing: about 53 searches at 8 results, or about 144 at 3 results.
- Subagents read their specialist file in their own context, so that cost does not count against the main conversation.

## How the numbers were produced

**Calibration.** `/context` reports the token cost of each custom agent. Nine user agents in
`~/.claude/agents/` were matched to their reported costs: 2,034 characters of name and description
cost 739 tokens. That gives about **2.75 characters per token** for agent listings. This is the only
measured ratio in this document, and it comes from nine agents.

**Assumption.** For prose, such as skill bodies and agent files, this document assumes **4
characters per token**. It is not calibrated. The true figure could be 20% or more different.

**Measurements:**

| Quantity | Measured | Tokens (estimate) |
|---|---|---|
| Roster as agent listings (282 agents, name and full description) | 69,067 chars | about 25,100 (2.75 chars/token) |
| All agent files in full | 4,088,812 chars | about 1,022,000 (4 chars/token) |
| Average agent file | 14,499 chars | about 3,600 |
| Reality Checker file | 10,854 chars | about 2,700 |
| Plugin skill description and command description | 329 + 107 chars | about 110 |
| Skill body (loaded when the skill is invoked) | 2,566 chars | about 640 |
| One search, 8 results (measured output of `roster.py`) | about 1,816 chars | about 450 |
| One search, 3 results (measured in the orchestration test) | about 673 chars | about 170 |

## What this does and does not show

- The plugin's always-loaded cost is small, and it is loaded whether or not you use the plugin.
- Each search costs a few hundred tokens. Those tokens are the only part that scales with use.
- Installing the whole roster as native agents puts about 25,000 tokens into every session, whether or not you search for anything.
- The comparison depends on how often specialists are needed. Above about 50 searches in a session, the plugin is more expensive than the roster listing, though that rarely happens in practice.
- The numbers are estimates. The per-search and per-file figures use the 4 characters per token assumption.

## Getting exact numbers

`/context` shows Claude Code's own accounting. It does not match a bare API count of the same
text, because it includes the system prompt and tool definitions. For exact figures on a piece
of text, use the Messages API token-counting endpoint (`POST /v1/messages/count_tokens`):

```python
from anthropic import Anthropic

client = Anthropic()  # needs ANTHROPIC_API_KEY, or a profile from `ant auth login`
resp = client.messages.count_tokens(
    model="claude-opus-5-5",  # count with the model the session actually uses
    messages=[{"role": "user", "content": open("skills/specialist-scout/SKILL.md").read()}],
)
print(resp.input_tokens)
```

Notes:
- Counts are model-specific, so count with the model the session uses.
- Do not use `tiktoken` for Claude. It is OpenAI's tokenizer and undercounts Claude tokens.
- The example counts a single user message. Whether `count_tokens` also takes `system` and `tools` has not been checked, so check the SDK reference before counting a whole request.
- The measurements above have not been re-done with this endpoint. Doing so would replace the
  estimates in the table with exact counts. The inputs would be the skill description and body,
  the command description, the roster listings, and a sample of agent files.
