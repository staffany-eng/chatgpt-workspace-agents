# Slack Runtime

Hermes Data Bot's first runtime surface is Slack POC usage in `#kaiyi-bot-testing`.

## Required Behavior

- Mention-only in the POC channel.
- First tool-backed data requests are plan-first.
- The bot should ask for `run` before the first confirmed plan.
- Same-thread approval nudges such as bot mention only, `^`, `+1`, `yes`, `ok`, `go`, or `please proceed` count as approval when there is a pending preflight and no substantive plan change.
- Clear same-thread corrections, fixes, and reruns after a delivered result are continuation work when scope is bounded.
- Materially expanded scope, source class changes, or expensive/ambiguous follow-ups require a revised plan and `run`.

## Slack Scopes

Runtime evidence shows the bot needs effective Slack scopes beyond prompt changes:

- `reactions:write` for status reactions.
- `files:read` for Slack file attachment hydration.

If Slack private file URLs return login HTML or gateway logs show missing file access, update the Slack app scopes, reinstall/save the app, and restart the gateway.

## Output Contract

Final Slack answers should use:

```text
Answer: <result or blocked reason>
Source: <table/file/tool used>
Scope: <time range, filters, grain>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```
