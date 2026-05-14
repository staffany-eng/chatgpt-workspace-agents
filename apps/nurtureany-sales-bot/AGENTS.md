# NurtureAny Sales Bot App Guide

This directory is the canonical source packet for the NurtureAny Hermes sales bot.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `profile/SOUL.md`
- `skills/nurtureany-sales-bot/SKILL.md`
- `skills/nurtureany-sales-bot/references/hubspot-fields.md`
- `skills/nurtureany-sales-bot/references/sales-best-practices.md`
- `skills/nurtureany-sales-bot/references/sop-tool-coverage.md`
- `skills/nurtureany-sales-bot/references/reviewed-lessons.md`
- `runtime/slack.md`
- `runtime/hubspot.md`
- `runtime/bigquery.md`
- `runtime/health-checks.md`
- `../../research/wiki/sources/hermes-agent-docs.md`
- `../../research/wiki/syntheses/hermes-runtime-bot-operating-model.md`

For source evidence or repo-wide claims, also read the root `AGENTS.md` files listed there.

Before changing NurtureAny sales behavior, drafting behavior, Friday review behavior, pre-demo plans, event follow-ups, coaching summaries, QO/QO Met logic, inbound/routing logic, AI/data-readiness guidance, or operating-rhythm guidance, read `skills/nurtureany-sales-bot/references/sales-best-practices.md` and `skills/nurtureany-sales-bot/references/sop-tool-coverage.md`.

## Source Boundaries

- Repo source packet: durable behavior, profile templates, skills, references, runtime contracts, and tests.
- Hermes runtime profile: live config, `.env`, sessions, memory, logs, cron state, gateway state, and temporary self-improvements.
- Business data source of truth: HubSpot for target accounts, owners, contacts, tasks, notes, and nurture fields.
- Production secrets: Secret Manager or the live profile `.env`; never this repo.

Before changing NurtureAny sales behavior, drafting behavior, Friday review behavior, pre-demo plans, event follow-ups, coaching summaries, QO/QO Met logic, inbound/routing logic, AI/data-readiness guidance, or operating-rhythm guidance, read `skills/nurtureany-sales-bot/references/sales-best-practices.md` and `skills/nurtureany-sales-bot/references/sop-tool-coverage.md`.

## Profile Boundary

NurtureAny runs as the separate Hermes profile `nurtureanysalesbot`. Da Ta Hermz runs as `staffanydatabot`.

The profiles may share model auth during pilot setup, but Slack app tokens, HubSpot tool policy, SOUL prompts, sales skills, safety rules, and business state must remain separate.

## Safety Rules

- V1 is review-first with a narrow quick-autorun exception. The first Slack request may execute immediately only when bounded recent Slack context makes the intent obvious, the work is read-only or preview/draft-only, expected under 60 seconds, exact in scope, and uses at most a small number of bounded tool calls.
- Ambiguous, expanded, expensive, paid, write/send, photo/deck, broad audit, or multi-source first requests still plan first and require `run`.
- HubSpot writes require explicit approval of a preview.
- External messages are never auto-sent in V1.
- Do not store or expose API keys, OAuth tokens, raw Slack transcripts, raw HubSpot rows, phone-number exports, or unnecessary PII. Slack context reads for quick intent must use the bot token, configured channels only, and safe summaries/permalinks only.
- Do not use Honcho for V1 business truth, permissions, account state, or contact data.

## Verification

Run from the repo root:

```bash
npm run nurtureany-sales-bot:verify
```
