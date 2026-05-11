# Slack Runtime

Hermes Data Bot's first runtime surface is Slack POC usage in `#kaiyi-bot-testing`.

## Required Behavior

- Mention-only in the POC channel.
- First tool-backed data requests are plan-first.
- The bot should ask for `run` before the first confirmed plan.
- Same-thread approval nudges such as bot mention only, `^`, `+1`, `yes`, `ok`, `go`, or `please proceed` count as approval when there is a pending preflight and no substantive plan change.
- Clear same-thread corrections, fixes, and reruns after a delivered result are continuation work when scope is bounded.
- Materially expanded scope, source class changes, or expensive/ambiguous follow-ups require a revised plan and `run`.
- Final answers are terminal unless the user asks a follow-up. Do not ask for yes/ok/done acceptance after a final answer.
- Do not add `:question:` action-needed markers or send reminder loops asking the user to mark a data answer done.
- Plain acknowledgements after a final answer, such as `ok`, `done`, `yes`, or `thanks`, close the thread silently unless they include a new request.
- The mark-as-done pattern belongs only to explicit task workflows with an assignee and completion state. It is not part of StaffAny data Q&A.
- Do not expose streaming drafts, tool progress, or interim assistant messages in Slack. Set `display.interim_assistant_messages=false`, `display.platforms.slack.tool_progress="off"`, and `display.platforms.slack.streaming=false`; otherwise partial answers, internal tool calls, or draft text can leak into Slack threads.
- Disable Slack status reactions for this POC with `slack.reactions=false`; the answer message itself is the status signal.

## Slack Scopes

Runtime evidence shows the bot needs effective Slack scopes beyond prompt changes:

- `files:read` for Slack file attachment hydration.

Do not add or request `groups:read` for this POC. Private-channel enumeration is intentionally out of scope. Hermes should fall back to public-channel/session-based directory discovery when `groups:read` is absent; on older runtimes, a missing-scope warning for private-channel directory enumeration is non-blocking when app mentions and configured-channel behavior work.

If Slack private file URLs return login HTML or gateway logs show missing file access, update the Slack app scopes, reinstall/save the app, and restart the gateway.

## User Allowlist Updates

Slack POC access is controlled by `SLACK_ALLOWED_USERS` in the live profile `.env` or the matching Secret Manager value. Do not commit the live `.env` file.

To add approved StaffAny teammates to the live local profile:

```bash
apps/hermes-data-bot/runtime/update-slack-allowlist.sh --restart U02RQTX3U0H
```

The helper creates a timestamped profile `.env` backup, dedupes IDs, updates only `SLACK_ALLOWED_USERS`, and can restart the gateway when `--restart` is passed.

## Output Contract

Final Slack answers should use:

```text
Answer: <result or blocked reason>
Source: <table/file/tool used>
Scope: <time range, filters, grain>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```

For live Slack replies, emit the labelled lines as normal Slack text. Do not wrap the whole answer or preflight in a code fence.
