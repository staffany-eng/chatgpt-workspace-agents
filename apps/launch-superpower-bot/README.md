# Launch Superpower Bot

Durable app packet for the Launch Superpower workflow described in the 2026-05-11 handoff.

## Runtime Shape

- Runtime: local workflow scripts plus Slack review/reaction flow
- Source workflow: `vk-super-productivity/launch-superpower-bot`
- Current source status in this repo: source code is not present; this packet preserves the app contract and reusable skill behavior from the handoff
- Jira test feature: `KER-1742` / Club Blue / ClubAny brands, perks, and redemptions
- Latest clean handoff version: `v005`
- Review surfaces: Google Docs and Slack
- Default Slack test channel: `#launch-bot-testing` (`C0B32M34J3W`)
- Slack automation voice: bot-owned, `Launchbot automation:` prefix, light cowboy tone
- Publish surface: Intercom draft articles only

## Workflow

1. Step 1 drafts help article content from code-grounded evidence.
2. Step 2 uploads draft articles to Google Docs, routes them for review, and posts Slack review messages.
3. Step 3 listens for approved Slack reactions and creates Intercom draft articles.
4. Step 4 remains planned for launch derivatives such as Released posts, WhatsApp drafts, and newsletter drafts.

## Packet Contents

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | App-level operating rules and source boundaries. |
| `app.manifest.json` | Machine-readable packet contract. |
| `skills/help-article-generator/` | Reusable help-article drafting skill upgraded from the handoff. |
| `runtime/workflow.md` | Step contracts, configuration names, review gates, and known gaps. |
| `runtime/launchbot_e2e.py` | Minimal VM-safe runner for the handoff flow when the original runtime source is absent. |
| `tests/regression-cases.md` | Manual/eval regression scenarios for the workflow. |

## Evidence

The source handoff and extracted skill package are stored under `research/raw/launch-superpower-bot/2026-05-11-handoff/`. The maintained source note is `research/wiki/sources/launch-superpower-bot-handoff.md`.

## Verification

Run from the repo root:

```bash
npm run launch-superpower-bot:verify
```

Run the VM-safe handoff path from the repo root after the required runtime secrets are available:

```bash
python3 apps/launch-superpower-bot/runtime/launchbot_e2e.py --issue KER-1742 --version v006
```

By default, the runner posts review messages to `#launch-bot-testing`.

Run the full repo check before merging:

```bash
npm run verify
```

## Source Code Gap

This packet does not include the actual Step 1, Step 2, or Step 3 runtime source code. Implementing code changes such as DOCX numbering or screenshot insertion requires the real `vk-super-productivity/launch-superpower-bot` source checkout.
