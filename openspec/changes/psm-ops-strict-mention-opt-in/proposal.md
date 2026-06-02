# OpenSpec: PSM Ops Strict Mention Opt-In

## Summary

Stop PSM Ops Bot from continuing to participate in Slack threads unless the current message directly @-mentions PS WEE / the bot.

## Evidence Used

- Jira story: `SCHE-19906`.
- Obsidian note: `PS Wee Manager Bot/03 P0 — Stop the Bleeding.md`, P0.3.
- Slack feedback: `https://staffany.slack.com/archives/C08SDJR03N1/p1780113986479539`.
- Source thread evidence: Beatrice Clothing thread where PS WEE replied to untagged follow-up messages after the first tagged ticket request.
- Hermes runtime docs on `slack.strict_mention`.

## Problem

`slack.require_mention=true` is not enough for busy public channels because Hermes can continue a thread after a prior mention, a bot-message reply, or an active thread session. That made PS WEE reply to untagged human discussion and sync follow-up context that was not directed at the bot.

## Goals

- Require a fresh direct @-mention for every reactive public/open-channel Slack message.
- Keep bot-owned automation starts such as AA push flow, cron, and central audit delivery unaffected.
- Document "stay quiet" / "stop commenting" as a silent-until-retagged signal.
- Add regression and verifier coverage so the strict mention config cannot drift.

## Non-Goals

- Do not change AA ticket creation semantics.
- Do not change DM behavior.
- Do not add a custom Slack gateway fork.
- Do not post as a human Slack user.
