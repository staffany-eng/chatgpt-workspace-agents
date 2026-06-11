# RevOps Bot App Guide

This directory is the canonical source packet for StaffAny RevOps Hermes Bot.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `profile/SOUL.md`
- `profile/config.template.yaml`
- `skills/rev-ops-bot/SKILL.md`
- `runtime/windmill.md`
- `runtime/slack.md`
- `runtime/health-checks.md`
- `../../research/wiki/sources/hermes-agent-docs.md`
- `../../research/wiki/syntheses/hermes-runtime-bot-operating-model.md`

## Source Boundaries

- Hermes owns Slack conversation, missing-info collection, and preview presentation.
- Windmill owns workflow validation, audit history, and Billing Engine execution.
- Kraken Billing Engine is the only business-write surface.
- Runtime config and secrets live in Secret Manager or the live profile `.env`; never this repo.

## Safety Rules

- Live writes are approval-gated and must go through the Windmill guarded tools.
- Do not add direct HubSpot, SignNow, Stripe, Xendit, or Kraken admin writes to Hermes.
- Do not execute create-sub-deal, service-agreement, or HubSpot readiness updates unless Windmill preview returns the required confirmation text and the Slack thread contains that exact approval.

## Verification

Run from the repo root:

```bash
npm run rev-ops-bot:verify
```
