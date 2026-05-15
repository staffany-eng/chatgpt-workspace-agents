# Product Ops Bot App Guide

This directory is the canonical source packet for Product Ops Bot.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `profile/SOUL.md`
- `skills/product-ops-bot/SKILL.md`
- `runtime/slack.md`
- `runtime/health-checks.md`

For repo-wide source claims, also follow the root `AGENTS.md`.

## Source Boundaries

- Repo source packet: durable behavior, profile templates, skills, references, runbooks, and tests.
- Runtime profile: live config, `.env`, sessions, logs, cron state, and temporary runtime learning.
- Production secrets: Secret Manager or live profile `.env`; never this repo.

## Slack Posting Identity

- Visible operational Slack replies must come from the Product Ops bot/app identity.
- Do not use user-scoped tokens for visible bot replies.
- Every automation-authored status should identify itself as automation.

## Promotion Rule

Runtime learning is not durable until reviewed and copied into this app packet. Promote only specific skill, reference, config-template, or runbook changes.

## Verification

Run from the repo root:

```bash
npm run product-ops-bot:verify
```
