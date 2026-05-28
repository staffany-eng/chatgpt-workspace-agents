# Product Ops Bot — Topology & Workflow Reference
_Captured: 2026-05-28_

## Profile & Source

- **Live profile:** `/home/leekaiyi/.hermes/profiles/productopsbot/`
- **Source packet:** `/home/leekaiyi/chatgpt-workspace-agents/apps/product-ops-bot/`
- **Gateway service:** `hermes-gateway-productopsbot.service` (systemd --user, assumed same pattern as launchbot)
- **Source subdir in live profile:** `source/product-ops-bot/`

## Skill Routing

| Trigger | Skill |
|---|---|
| New intake / feature-linking request | `product-ops-intake-linking` |
| Jira grooming, PRD generation, delivery workflow execution | `staffany-product-delivery-workflow` |
| Backlog triage | KER-* search by default; EDT-* only if explicitly requested |

## Key Behavioral Rules (from SOUL.md + runtime/slack.md)

- **Mention-required** in Slack.
- **Read-first**: no Jira writes without explicit `run` in the same thread.
- **Plan-first** for non-trivial asks; propose smallest next step when data is missing.
- For backlog triage, default to `KER-*`; never switch to `EDT-*` unless user asks.
- Automation-authored statuses must self-identify.
- Do not post tool-progress or partial draft content.

## Output Contract

```
Answer: <result or blocked reason>
Source: <tool/file/system used>
Scope: <time range, team, project, or filter>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```

## Health Check

```bash
npm run product-ops-bot:verify
apps/product-ops-bot/runtime/check-health.sh
apps/product-ops-bot/runtime/audit-live-profile.sh
```

## Expected Health Checks

- `productopsbot` gateway service is active.
- Secret redaction is enabled.
- Model route: `anthropic` + `claude-sonnet-4-6`.
- Slack is mention-required.
