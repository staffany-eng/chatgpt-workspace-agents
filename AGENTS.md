# Agent Builder Agent Guide

This repo is now app-first for StaffAny Hermes Data Bot, with the earlier ChatGPT workspace-agent research retained as evidence.

## Before Decisions

Read these first:

- `README.md`
- `docs/product-compass.md`
- `docs/documentation-guide.md`
- `research/wiki/index.md`
- `research/wiki/weights.md`

For Hermes Data Bot app work, also read:

- `apps/hermes-data-bot/README.md`
- `apps/hermes-data-bot/AGENTS.md`
- `apps/hermes-data-bot/app.manifest.json`
- `apps/hermes-data-bot/deploy/gcp-vm-topology.md`

For any Hermes runtime bot work on Da Ta Hermz, NurtureAny, or Launchbot, also read:

- `research/wiki/sources/hermes-agent-docs.md`
- `research/wiki/syntheses/hermes-runtime-bot-operating-model.md`

## Research Workflow

- Preserve source evidence under `research/raw/`.
- Maintain readable source notes under `research/wiki/sources/`.
- Put cross-source learning under `research/wiki/syntheses/`.
- Promote stable guidance to `research/wiki/decisions.md` before treating it as product truth.
- Official OpenClaw docs are primary for OpenClaw design intent.
- `openclaw-kaiyi` is secondary implementation evidence for what Kai Yi already set up.

## Verification

For Hermes Data Bot packet changes:

```bash
npm run hermes-data-bot:verify
```

Run the audit before calling an ingest done:

```bash
bun research/tools/audit-agent-ingest.ts --wiki <source-note.md> --fail-under 10
```

For source inventories:

```bash
bun research/tools/build-source-inventories.ts
```

## Slack Posting Identity

- Do not send visible Slack automation replies using Kai Yi's user token or the Slack connector if it posts as a human user.
- When asked to check Slack for bot/runtime work, use the relevant Slack bot token from the deployed bot profile or approved secret store for read/check operations whenever available.
- Do not use the Slack connector or Kai Yi's user token for Slack inspection when a relevant bot token exists.
- Use Kai Yi's user token or the Slack UI only for explicit human-authored smoke tests where a bot token cannot trigger the Slack gateway; label that evidence as a human-authored smoke, not a bot-token check.
- User-scoped Slack credentials must not be used for `chat.postMessage`/thread replies that look like Kai Yi wrote them.
- Visible operational Slack replies must come from the relevant bot/app identity. If no bot-owned posting path is available, report the blocked action in Codex with the safe Slack thread link and the exact message that would have been sent.
- Every automation-authored Slack status must identify itself as automation, for example by starting with `Customer 360 automation:` or `Hermes repair automation:`. It must not read as if Kai Yi personally wrote it.
- After any automation bug fix, repair, deploy, or blocked repair, always emit a completion report. Prefer the bot-owned Slack path; if unavailable, report in Codex with the safe Slack thread link and exact intended Slack message.
- Never ask a human user to become the fallback sender for bot or automation status messages.
- After changing Slack automation instructions or identity rules, run `npm run slack-automation-identity:verify`.
