---
name: verify-target-environment
description: Use when operating Agent Builder Hermes bots through the release flow "pull main, reconcile, deploy, verify in target environment, if verification passes merge cleanly back to main." Triggers include verify in target environment, target env verification, pull main/reconcile/deploy/merge, linked Slack thread bug fix closeout, and bot/profile names such as staffanydatabot, nurtureanysalesbot, psmopsbot, PS WEE, Launchbot, or Da Ta Hermz.
---

# Verify Target Environment

## Purpose

Use this repo-local Codex operator skill for Agent Builder bot fixes that must be proven in the live target environment before landing or after merging. This is not a Hermes runtime skill; never copy it into `~/.hermes/profiles/*/skills`.

## Source Of Truth

1. Read root `AGENTS.md`, then the target app `AGENTS.md` when one exists.
2. Read `ops/hermes/profiles.yaml` for current profile, VM, service, Slack channel, report prefix, checks, and recovery policy.
3. Use app runbooks and deploy scripts only after routing to the target bot.
4. Treat live profile state as runtime state. Durable behavior belongs in this repo.

## Target Matrix

| Profile | App packet | Local verify | Deploy command | Target VM | Service | Slack smoke channel | Status prefix |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `staffanydatabot` / Da Ta Hermz | `apps/hermes-data-bot` | `npm run hermes-data-bot:verify` | manual packet sync per app runbook | `hermes-data-bot-poc` | `hermes-gateway-staffanydatabot.service` | `#da-ta-hermz-testing` (`C0AU19E6T0C`) | `Hermes repair automation:` |
| `nurtureanysalesbot` / NurtureAny | `apps/nurtureany-sales-bot` | `npm run nurtureany-sales-bot:verify` | `npm run nurtureany-sales-bot:deploy` | `nurtureany-sales-bot-prod` | `hermes-gateway-nurtureanysalesbot.service` | `#nurtureany-testing` (`C0B2UGK4DB6`) | `NurtureAny automation:` |
| `psmopsbot` / PS WEE / PSM Ops Bot | `apps/psm-ops-bot` | `npm run psm-ops-bot:verify` | `npm run psm-ops-bot:deploy` | `hermes-psm-ops-bot-poc` | `hermes-gateway-psmopsbot.service` | `#ps-weeman-bot-test` (`C0B2VT50YT1`) | `PSM Ops automation:` |
| `launchbot` / Launchbot | `apps/launchbot` | `npm run launchbot:verify` | manual packet sync per app runbook | `hermes-data-bot-poc` | `hermes-gateway-launchbot.service` | `#launch-bot-testing` (`C0B32M34J3W`) | `Hermes repair automation:` for repair reports; `Launchbot automation:` for launch workflow replies |

If the prompt says "sales-manager" or "manager chase", route to `nurtureanysalesbot`. If it says `PS WEE`, `PS Wee Manager`, or `PSM Manager Ops Bot`, route to `psmopsbot`.

## Slack Identity Rules

- Your Slack UI or user credential may send only the explicit human-authored trigger for a real smoke test. Label that evidence as `human-authored smoke trigger`.
- Bot-token paths own Slack reads, result checks, and automation status delivery.
- Visible automation status must come from the target bot/app identity and start with the profile's prefix from `ops/hermes/profiles.yaml`.
- Never post automation status as Kai Yi. Never use Slack connector writes for this flow.
- When a bug fix has a linked source Slack thread, close the loop in that original thread with a bot-owned reply after target verification passes.
- If bot-owned posting is unavailable, do not ask a human to be the fallback sender. Report in Codex with the safe Slack thread link and the exact intended bot-owned message.

## Pre-Merge Candidate Flow

1. Confirm the target profile from the prompt, changed paths, app packet, or Slack thread context.
2. Check repo state:

```bash
git status --short
git fetch origin main
```

3. Reconcile against `origin/main` without reverting unrelated user changes. If conflicts or unrelated dirty files affect the target app, stop and report the blocker.
4. Run the target local verifier from the matrix.
5. If Slack identity rules, automation text, profile instructions, or app `AGENTS.md` changed, also run:

```bash
npm run slack-automation-identity:verify
```

6. Deploy the candidate to the target environment. For bots with deploy scripts, use dry-run first, then `--apply` only when the candidate is intended to mutate the live target. For manual-sync bots, follow the app runbook and record the exact SHA and commands.
7. Verify target environment:
   - service is active on the target VM;
   - live-profile audit passes;
   - health check passes;
   - heartbeat, cloud doctor, or app-specific smoke passes when present;
   - live Slack smoke proves the target bot identity answered or the repair path closed the original thread.
8. If target verification fails, do not merge. Summarize the failed command/check, current deployed SHA if known, and rollback or recovery action taken.

## Merge And Main Redeploy Flow

1. Merge cleanly back to `main` only after candidate target verification passes.
2. Push `main`.
3. Redeploy exact `origin/main` to the same target environment.
4. Repeat the minimum target checks needed to prove the merged SHA is live: service active, app health/audit, and one targeted Slack or app smoke.
5. For linked Slack bugs, post the completion report in the original thread using the target bot identity. Use this shape:

```text
<prefix> Fixed and verified in target environment.
Issue: <short bug summary>
Deployed: <profile> on <target VM>, sha <sha>
Verification: <local verifier>; <target health/audit>; <Slack smoke or app smoke>
Outcome: <user-visible result>
```

If bot-owned posting is blocked, return the same text in Codex with `blocked: bot-owned Slack delivery unavailable`.

## Final Summary Contract

End with:

- `Target`: profile, VM, service, Slack channel.
- `Branch/SHA`: candidate SHA and final `origin/main` SHA.
- `Tests`: local verifier and any repo-wide or identity verifier.
- `Deploy`: dry-run/apply commands and outcome.
- `Target verification`: service, audit, health, smoke result.
- `Slack close-loop`: original thread reply posted by bot, or blocked with intended message.
- `Uncertainty`: only material gaps.
