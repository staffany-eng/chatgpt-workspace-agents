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
- User-scoped Slack credentials may be used for read-only monitoring or diagnostics, but not for `chat.postMessage`/thread replies that look like Kai Yi wrote them.
- Visible operational Slack replies must come from the relevant bot/app identity. If no bot-owned posting path is available, report the blocked action in Codex with the safe Slack thread link and the exact message that would have been sent.
- Every automation-authored Slack status must identify itself as automation, for example by starting with `Customer 360 automation:` or `Hermes repair automation:`. It must not read as if Kai Yi personally wrote it.
- After any automation bug fix, repair, deploy, or blocked repair, always emit a completion report. Prefer the bot-owned Slack path; if unavailable, report in Codex with the safe Slack thread link and exact intended Slack message.
- Never ask a human user to become the fallback sender for bot or automation status messages.
- After changing Slack automation instructions or identity rules, run `npm run slack-automation-identity:verify`.
