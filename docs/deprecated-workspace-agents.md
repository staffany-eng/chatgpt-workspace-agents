# Deprecated Workspace-Agent Material

This repo started as a ChatGPT workspace-agent research corpus. The primary app is now StaffAny Hermes Data Bot under `apps/hermes-data-bot/`.

## Deprecated Areas

| Path | Status | Replacement |
| --- | --- | --- |
| `agents/data-bot/` | deprecated snapshot | `apps/hermes-data-bot/` |
| `agents/hermes-data-bot/` | deprecated legacy packet | `apps/hermes-data-bot/` |
| `agents/staffany-org-creator/` | deprecated proposal | Keep only as evidence unless revived. |
| `skills/plan-chatgpt-workspace-agent/` | legacy planning skill | Use only for explicit ChatGPT workspace-agent work. |
| `skills/manage-chatgpt-custom-mcps/` | legacy support skill | Use only for explicit ChatGPT custom MCP work. |

## Rules

- Do not make new Hermes Data Bot changes under `agents/`.
- Do not delete historical snapshots during the staged transition.
- When copying durable behavior from old snapshots, copy it into `apps/hermes-data-bot/` and cite the source path.
- Keep old workspace-agent docs as evidence until references are clean and the app packet is stable.
