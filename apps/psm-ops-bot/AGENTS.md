# PSM Ops Bot App Guide

This directory is the canonical source packet for StaffAny PSM Ops Hermes Bot.

`PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` all refer to this same PSM Ops Bot packet/profile (`psmopsbot`). Do not create a separate `psweemanager` app or profile for those names.

## Before Decisions

Read these first for app work:

- `README.md`
- `app.manifest.json`
- `profile/SOUL.md`
- `skills/psm-ops-bot/SKILL.md`
- `runtime/jira.md`
- `runtime/c360.md`
- `runtime/slack.md`
- `runtime/health-checks.md`

For repo-wide source claims, also follow the root `AGENTS.md`.

## Source Boundaries

- Jira PCO is the PS/customer-ops task source of truth.
- Jira ROI is the source of truth for RevOps, BD Ops, NYSS, and ROI-board execution; do not create duplicate PCO execution wrappers. A linked PCO customer-loop tracker is allowed when PS needs customer follow-up visibility, and is default for PS Team billing/invoice asks.
- Customer 360 is the customer context source of truth.
- The bot may use all Customer 360 customers in V1.
- "My tasks" and reminder filters are scoped by Jira `PS Team`, not Jira assignee.
- Caller identity must be canonicalized from Slack user data. Fetch Slack users and auto-match profile email/name to the Jira `PS Team` option; do not trust guessed email spelling from the model.
- Runtime config and secrets live in Secret Manager or the live profile `.env`; never this repo.

## Slack Posting Identity

- Visible operational Slack replies must come from the PSM Ops bot/app identity.
- Do not use Kai Yi's user token or the Slack connector for visible bot replies.
- Every automation-authored reminder must start with `PSM Ops automation:`.
- If bot-owned Slack delivery is unavailable, report the blocked action in Codex with the safe Slack thread link and exact intended message.

## Promotion Rule

Runtime learning is not durable until reviewed and copied into this app packet. Promote only specific skill, reference, config-template, MCP, or runbook changes.

## Verification

Run from the repo root:

```bash
npm run psm-ops-bot:verify
```
