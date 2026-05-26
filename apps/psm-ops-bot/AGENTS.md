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

## Anti-Example Lifecycle

Anti-examples in `skills/psm-ops-bot/SKILL.md` (and any future workflow files under `skills/psm-ops-bot/workflows/`) are debt, not documentation. They cost tokens and attention on every invocation.

**What an eval does and does not do.** `apps/psm-ops-bot/tests/prompt-evals.json` is a static test artifact — the bot never reads it at runtime. An eval is a **regression tripwire** that fires during `npm run psm-ops-bot:verify`, not a substitute prompt. Deleting an anti-example without something else holding the line means the agent gets no runtime signal at all; the eval will only catch the regression at verify-time.

**Deletion rule.** An anti-example may be deleted from markdown only when at least one of the following carries the runtime guarantee:

1. **MCP-side enforcement** — the strongest. The wrong behavior is structurally impossible to express because the tool response itself instructs the LLM toward the correct path (e.g. `aa_channel_redirect: true`, server-side `due_date` strip, `_classify_no_follow_up_intent` skip). Prefer this whenever the rule is deterministic.
2. **A positive rule in the same workflow file** that states the correct behavior. The anti-example is the photographic negative of a rule; the positive form is what the LLM actually needs.

If neither holds, the anti-example stays. A green eval alone is not enough — it is the regression net, not the runtime context.

**Lifecycle:**
- New defect → add the regression eval entry first.
- Then add the MCP guard if the rule is deterministic; otherwise add a positive rule in SKILL.md.
- Add a prose anti-example only when (1) and (2) are both insufficient on their own and the model needs the negative form to disambiguate. Treat it as temporary debt.
- Once an MCP guard or positive rule covers the case, delete the anti-example bullet outright. Do not leave a `(covered by eval <name>)` stub — the eval is the durable record; the markdown bullet is the temporary one.

## Verification

Run from the repo root:

```bash
npm run psm-ops-bot:verify
```
