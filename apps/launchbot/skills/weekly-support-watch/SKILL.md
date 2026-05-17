# Launchbot Weekly Support Watch

Use this skill when Launchbot needs the weekly report-only scan for production-bug signals from support conversations and support ticket logs.

## Contract

- Run weekly every Thursday 09:00 SGT from the UTC VM cron `0 1 * * 4`.
- Source support signals from BigQuery-backed Intercom conversations and conversation parts for the previous report window.
- Include WhatsApp support ticket logs from `gsheets.cs_tickets_logs_all_view` when `LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP=true`.
- Count the full source window first, then fetch bounded candidate rows using problem-keyword scoring instead of sampling only the latest rows.
- Cluster likely production bugs by repeated topic, shared error phrase, or one high-severity blocker.
- Trace likely product/code causes with the Pantheon checkout and recent Git evidence.
- Dedupe before posting against:
  - recent `#team-cs-eng-duty` Slack posts from `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS`
  - EDT Jira query from `LAUNCHBOT_SUPPORT_WATCH_EDT_JQL`
  - prior support-watch state at `LAUNCHBOT_SUPPORT_WATCH_STATE_PATH`
- Post only new, untracked findings to `#all-bugs-production`.
- Every posted report must start with `Launchbot automation:`.
- V1 is report-only. Do not create Linear/Jira tickets, tag individual engineers, assign owners, transition issues, or store raw support transcripts.

## Tools

Use the read-only MCP tool for previews:

```text
launchbot_support_watch.preview_weekly_support_watch_report
```

Use the no-agent monitor for scheduled runs:

```bash
python runtime/monitor-support-watch.py --dry-run
```

The monitor owns Slack posting. The MCP preview tool must not post Slack messages.

## Runtime Config

Required or deploy-resolved:

- `LAUNCHBOT_SUPPORT_WATCH_SOURCE=bigquery`
- `LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT=staffany-warehouse`
- `LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET=intercom`
- `LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET=analytics`
- `LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP=true`
- `LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW=gsheets.cs_tickets_logs_all_view`
- `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME=all-bugs-production`
- `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID=<optional pre-resolved output channel id>`
- `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES=team-cs-eng-duty`
- `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS=<optional pre-resolved dedupe channel ids>`
- `LAUNCHBOT_SUPPORT_WATCH_EDT_JQL='project = PCO AND "PS Team" = "Eng Duty" AND statusCategory != Done ORDER BY updated DESC'`

Optional:

- `LAUNCHBOT_SUPPORT_WATCH_STATE_PATH`
- `LAUNCHBOT_SUPPORT_WATCH_LOOKBACK_DAYS`
- `LAUNCHBOT_SUPPORT_WATCH_MAX_TICKETS`
- `LAUNCHBOT_PANTHEON_REPO_DIR`

## Output Shape

Keep Slack compact:

```text
Launchbot automation: Weekly support watch found new production-bug signals.
Window: ...
New: N | Already tracked: M
1. [severity] summary (support signal count)
   Evidence: source IDs only
   Code trace: file:line or needs-check
Action: review in this channel before forwarding or creating an engineering ticket.
Caveat: Report-only. Launchbot did not create tickets, assign owners, or tag engineers.
```

No new findings means no Slack post. The monitor may still advance state with safe counters and window timestamps.

## Live Smoke

Before enabling the cron in production:

1. Resolve `#all-bugs-production` with the Launchbot bot token using public-channel lookup; set `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID` only if name resolution cannot be used.
2. Confirm Launchbot is a member of `#all-bugs-production`.
3. Keep `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES=team-cs-eng-duty`, or set `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS` only when the dedupe channel must be referenced by ID.
4. Run a dry-run against a small BigQuery report window and confirm full source counts, fetched candidate counts, and `hit_limit` flags are shown.
5. Post exactly one test report from Launchbot identity, prefixed `Launchbot automation:`.
