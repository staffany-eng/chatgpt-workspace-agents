# Launchbot App Guide

This directory is the canonical source packet for the Launchbot Hermes app.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `profile/SOUL.md`
- `profile/config.template.yaml`
- `runtime/slack.md`
- `runtime/health-checks.md`
- `runtime/launch-workflow.md`
- `skills/help-article-generator/SKILL.md`
- `../../research/wiki/sources/hermes-agent-docs.md`
- `../../research/wiki/syntheses/hermes-runtime-bot-operating-model.md`

For source evidence or repo-wide claims, also read the root `AGENTS.md` files listed there.

## Source Boundaries

- Repo source packet: durable behavior, profile templates, skills, references, runtime contracts, and tests.
- Hermes runtime profile: live config, `.env`, sessions, memory, logs, cron state, gateway state, and temporary self-improvements.
- Launch workflow truth: Pantheon code evidence, Jira/KER source evidence, cached Intercom shape evidence, and live Intercom stale checks.
- Production secrets: Secret Manager or the live profile `.env`; never this repo.

## Safety Rules

- Do not create or run a Mac-local `launchbot` profile for live Slack testing.
- Keep Launchbot cloud-primary on `hermes-data-bot-poc` unless the deploy topology is explicitly changed.
- Public help article publish stays manual in Intercom; Launchbot can draft or stage only according to the workflow contract.
- Do not use runtime learning as durable product truth until it is promoted into this packet and verified.

## Verification

Run from the repo root:

```bash
npm run launchbot:verify
```
