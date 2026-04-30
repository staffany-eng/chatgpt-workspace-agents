# Local Workspace Agent Registry

This directory stores source-controlled snapshots of ChatGPT workspace agents.

Use one folder per agent:

- `agents/<agent-slug>/README.md` explains the agent and points to the latest snapshot.
- `agents/<agent-slug>/versions/<timestamp>/` stores one captured version.
- Each version separates instructions, apps/MCPs, skills, files, memory, channels, and safety notes.

Do not store secrets, OAuth tokens, API keys, private keys, raw browser session data, or connector credentials here. Redact account identifiers when they are not needed to rebuild behavior.
