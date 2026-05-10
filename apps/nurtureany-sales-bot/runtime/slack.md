# Slack Runtime

NurtureAny's first runtime surface is Slack mention usage in sales pilot channels.

## Required Behavior

- Mention-only in configured channels for V1.
- First tool-backed requests are plan-first.
- The bot asks for `run` before the first confirmed execution.
- Clear same-thread corrections, fixes, and reruns after a delivered result are continuation work when scope is bounded.
- Materially expanded scope, source-class changes, write intent, or expensive/ambiguous follow-ups require a revised plan and `run`.
- Exa People Search requests must show the estimated dollar-cost scope before execution and include `cost_report` after execution.

## Commands

AE commands:

- `@NurtureAny my 150`
- `@NurtureAny my target accounts`
- `@NurtureAny my nurture queue`
- `@NurtureAny accounts missing direct contact`

Manager commands:

- `@NurtureAny team queue`
- `@NurtureAny show ID team accounts with no direct contact`
- `@NurtureAny post-demo nurture queue`
- `@NurtureAny renewal risk queue this month`

## Scope Routing

Use Slack user email as the caller identity.

- AE calls map Slack email to HubSpot owner and restrict to owned companies.
- Manager calls require explicit email allowlist.
- Country filters come from the manager scope, not from channel name.

If Slack cannot provide the user email, return `Confidence: blocked` and ask for the missing identity mapping.

## Output Contract

Preflight plain Slack text:

Interpreted question: <question>
Plan: I will check <sources>, using <owner/team/country filters>.
Estimate: <1-2 min | 3-5 min | may exceed 5 min>
Caveat: <material limitation>
Reply "run" to start, or tell me what to change.

Final plain Slack text:

Answer: <result or blocked reason>
Source: <HubSpot/C360/Luma/tool used>
Scope: <owner/team/country/time filters>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

## Slack Scopes

The Slack app needs enough access to receive mentions, identify users, and reply in configured channels. Do not request broad private-channel enumeration for V1 unless a concrete pilot channel requires it and the security owner approves.
