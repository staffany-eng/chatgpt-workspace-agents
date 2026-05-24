# Hermes Data Bot App Guide

This directory is the canonical source packet for StaffAny Hermes Data Bot.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `profile/SOUL.md`
- `skills/staffany-data-bot/SKILL.md`
- `skills/staffany-data-bot/references/reviewed-lessons.md`
- `runtime/mcp/staffany-bigquery.md`
- `runtime/slack.md`
- `runtime/health-checks.md`
- `../../research/wiki/sources/hermes-agent-docs.md`
- `../../research/wiki/syntheses/hermes-runtime-bot-operating-model.md`

For source evidence or repo-wide claims, also read the root `AGENTS.md` files listed there.

## Source Boundaries

- Repo source packet: durable behavior, profile templates, skills, references, runbooks, and tests.
- Hermes runtime profile: live config, `.env`, sessions, memory, logs, cron state, gateway state, and temporary self-improvements.
- Production secrets: Secret Manager or the live profile `.env`; never this repo.

## Slack Posting Identity

- Do not send visible Slack automation replies using Kai Yi's user token or a connector identity that posts as a human user.
- When asked to check Slack for Hermes bot/runtime work, use the relevant Slack bot token from the deployed Hermes profile or approved secret store for read/check operations whenever available.
- Do not use the Slack connector or Kai Yi's user token for Slack inspection when the Hermes bot token exists.
- Use Kai Yi's user token or the Slack UI only for explicit human-authored smoke tests where a bot token cannot trigger the Slack gateway; label that evidence as a human-authored smoke, not a bot-token check.
- User-scoped Slack credentials must not be used for visible Slack posts.
- Visible operational Slack replies must come from the Hermes bot/app identity. If no bot-owned posting path is available, report the blocked action in Codex with the safe Slack thread link and the exact message that would have been sent.
- Every automation-authored Slack status must identify itself as automation, for example by starting with `Hermes repair automation:`. It must not read as if Kai Yi personally wrote it.
- After any automation bug fix, repair, deploy, or blocked repair, always emit a completion report. Prefer the bot-owned Slack path; if unavailable, report in Codex with the safe Slack thread link and exact intended Slack message.

## Promotion Rule

Runtime learning is not durable until reviewed and copied into this app packet. Promote only specific skill, reference, config-template, or runbook changes. Do not copy sessions, raw Slack transcripts, memory dumps, logs containing sensitive content, or query rows.

## Verification

Run from the repo root:

```bash
npm run hermes-data-bot:verify
```
