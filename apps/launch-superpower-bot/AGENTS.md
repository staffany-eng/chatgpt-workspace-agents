# Launch Superpower Bot App Guide

This directory is the canonical Agent Builder packet for Launch Superpower Bot handoff learnings.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `runtime/workflow.md`
- `skills/help-article-generator/SKILL.md`
- `tests/regression-cases.md`

For repo-wide evidence or research claims, also follow the root `AGENTS.md`.

## Source Boundaries

- Repo source packet: durable workflow contract, reusable help-article skill, safety rules, known gaps, and regression cases.
- Handoff evidence: `research/raw/launch-superpower-bot/2026-05-11-handoff/`.
- Runtime source code: external `vk-super-productivity/launch-superpower-bot`; not present in this repo.
- Secrets and live service credentials: password manager, Secret Manager, or local runtime environment only; never this repo.

## Workflow Safety

- Draft and review first; Intercom output is draft creation, not public publishing.
- Slack review and reaction handling must use a bot-owned token. Do not post visible automation replies using Kai Yi's user token or a Slack connector identity that posts as a human user.
- Launchbot tests must use Slack `#launch-bot-testing` (`C0B32M34J3W`) unless the user explicitly names another channel.
- Visible Launchbot Slack automation messages must start with `Launchbot automation:` and use a light cowboy voice, for example `Howdy, partner`, without changing the factual help article body into parody.
- Google Docs and Intercom credentials must stay runtime-only.
- Preserve implementation evidence and assumptions outside the publishable article body.

## Promotion Rule

Promote only reviewed skill, workflow-contract, regression-case, or source-note changes into this packet. Do not copy `.env` files, service-account JSON, OAuth tokens, raw Slack transcripts, or private customer data.

## Verification

Run from the repo root:

```bash
npm run launch-superpower-bot:verify
```
