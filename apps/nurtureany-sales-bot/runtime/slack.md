# Slack Runtime

NurtureAny's first runtime surface is Slack mention usage in sales pilot channels.

## Required Behavior

- Mention-only in configured channels for V1.
- First tool-backed requests are plan-first.
- The bot asks for `run` before the first confirmed execution.
- Clear same-thread corrections, fixes, and reruns after a delivered result are continuation work when scope is bounded.
- Materially expanded scope, source-class changes, write intent, or expensive/ambiguous follow-ups require a revised plan and `run`.
- Exa People Search requests must show the estimated dollar-cost scope before execution and include `cost_report` after execution.
- Luma guest or attendance requests must check HubSpot scope first, then return bounded RSVP/attendance context without raw attendee exports.
- Luma event requests should pass exact Luma event tags when the prompt implies them, for example `event_tags=["Jakarta", "Appreciation Afternoon"]` for `StaffAny Appreciation Afternoon (JKT)` or `event_tags=["Singapore", "Sports"]` for a Singapore Sports event. Use country as broad account scope, not as the event filter when exact tags are known.
- When Slack output says a Luma event was found or selected, include the clickable event link as `<event.url|event.name>` whenever `event.url` is present, followed by date and event ID.

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
- `@NurtureAny which target accounts attended yesterday's Luma event`
- `@NurtureAny which target accounts attended StaffAny Appreciation Afternoon (JKT)?`

## Scope Routing

Use Slack user email as the caller identity.

- AE calls require an explicit `sales_reps` policy entry that maps Slack email to HubSpot owner email, then restrict to owned HubSpot target accounts.
- Manager calls require explicit email allowlist and are team read-only.
- Unclassified HubSpot owners are blocked even if Slack email matches a HubSpot owner record.
- Country filters come from the manager scope, not from channel name.

If Slack cannot provide the user email, return `Confidence: blocked` and ask for the missing identity mapping. If the Slack email is not classified, ask for runtime access policy classification.

## Output Contract

Preflight plain Slack text:

Interpreted question: <question>
Plan: I will check <sources>, using <owner/team/country filters>.
Estimate: <1-2 min | 3-5 min | may exceed 5 min>
Caveat: <material limitation>
Reply "run" to start, or tell me what to change.

Final plain Slack text:

Answer: <result or blocked reason>
Source: <HubSpot/C360/Google Calendar/Luma/tool used>
Scope: <owner/team/country/time filters>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>

## Slack Scopes

The Slack app needs enough access to receive mentions, identify users, and reply in configured channels. Do not request broad private-channel enumeration for V1 unless a concrete pilot channel requires it and the security owner approves.
