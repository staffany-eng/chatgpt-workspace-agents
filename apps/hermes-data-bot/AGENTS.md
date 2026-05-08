# Hermes Data Bot App Guide

This directory is the canonical source packet for StaffAny Hermes Data Bot.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `profile/SOUL.md`
- `skills/staffany-data-bot/SKILL.md`
- `runtime/mcp/staffany-bigquery.md`
- `runtime/slack.md`
- `runtime/health-checks.md`

For source evidence or repo-wide claims, also read the root `AGENTS.md` files listed there.

## Source Boundaries

- Repo source packet: durable behavior, profile templates, skills, references, runbooks, and tests.
- Hermes runtime profile: live config, `.env`, sessions, memory, logs, cron state, gateway state, and temporary self-improvements.
- Production secrets: Secret Manager or the live profile `.env`; never this repo.

## Promotion Rule

Runtime learning is not durable until reviewed and copied into this app packet. Promote only specific skill, reference, config-template, or runbook changes. Do not copy sessions, raw Slack transcripts, memory dumps, logs containing sensitive content, or query rows.

## Verification

Run from the repo root:

```bash
npm run hermes-data-bot:verify
```
