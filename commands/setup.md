---
description: Check the specialist scout plugin and, with your approval, install the roster and optional embedding search
argument-hint: [status|roster|embeddings|all]
allowed-tools: Bash(bash:*)
---

Current state:

!`bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh" status`

Requested action: $ARGUMENTS (treat an empty request as `status`)

Rules:
- Report the current state above in a few lines. If the request is empty or `status`, stop there.
- Before any download, say exactly what will be fetched and where, and wait for the user to say yes:
  - `roster`: a shallow git clone of https://github.com/msitarzewski/agency-agents (about 11 MB) into the plugin data folder. Skipped if a roster is already installed.
  - `embeddings`: Python packages (about 175 MB) into a virtualenv in the plugin data folder, plus a 90 MB model from huggingface.co. Each file is checked against a pinned SHA-256 hash.
- Only after an explicit yes, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh" <roster|embeddings|all>` for the approved step.
- Report the result. If a step fails, show the error and stop.
- Never run a download the user has not approved, and never change files outside the plugin data folder.
