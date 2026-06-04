# Health Checks

PSM Ops Bot needs deterministic cloud health checks because prompt correctness does not prove Slack, Jira, C360, cron, or gateway wiring.

`psmopsbot` is cloud-only. Run these checks on `hermes-psm-ops-bot-poc`, not from a Mac-local Hermes profile.

## Expected Checks

- Hermes gateway service `hermes-gateway-psmopsbot.service` is active on the GCE host.
- Hermes gateway service `hermes-gateway-psmopsbot.service` is enabled on the GCE host.
- Secret redaction remains enabled.
- Model route is pinned to `anthropic` / `claude-sonnet-4-6`.
- Slack quiet settings are enforced: `display.interim_assistant_messages=false`, Slack `tool_progress=off`, Slack `streaming=false`, and `slack.reactions=false`.
- Non-critical `auxiliary.title_generation` is pinned to `anthropic` / `claude-haiku-4-5` with a short timeout so title-generation overloads are less likely to leak into Slack as visible auxiliary warnings.
- Slack gateway is mention-required, strict-mention gated for every reactive channel message, and not restricted to a single public/open channel.
- Slack bot token can call `users.list` with profile emails for `PS Team` identity matching.
- Slack bot token can call `conversations.join` on the public join-smoke channel, proving the app has `channels:join` for public/open-channel membership repair.
- If `PSM_OPS_CENTRAL_SLACK_CHANNEL_ID` is configured, the Slack bot token can inspect that channel and the bot is a member.
- Reviewed customer-channel map path is configured when customer-specific Slack channel auto-tagging is enabled.
- `psm_jira` MCP lists exactly the expected tools.
- `psm_c360` MCP lists exactly the expected tools.
- `psm_google_calendar` MCP lists exactly `read_customer_calendar_context` when Google Calendar is enabled.
- `psm_google_geocode` MCP lists exactly `check_google_geocode_access`, `geocode_slack_addresses`, and `geocode_slack_address_file`.
- `psm_store_reviews` MCP lists exactly `list_store_review_apps`, `list_store_reviews`, `get_store_review`, `draft_store_review_reply`, `suggest_store_review_identity_candidates`, and `confirm_store_review_identity`.
- Google Calendar OAuth is configured for `team@staffany.com` with `calendar.readonly`, returns bounded event metadata, and exposes no mutation or attendee-export tools.
- Google Geocoding credentials are available through `GOOGLE_GEOCODING_API_KEY`, `PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE`, or `~/.staffany/google-geocode/credentials.json`; the health check never prints the key.
- AppFollow review credentials are available through `APPFOLLOW_API_TOKEN`, `PSM_OPS_APPFOLLOW_CREDENTIALS_FILE`, `APPFOLLOW_CREDENTIALS_FILE`, or `~/.staffany/appfollow/credentials.json`; the health check never prints the token.
- Slack bot token has `files:read` and `files:write` before geocode CSV/TSV file input and TSV upload are used in production; missing scope blocks geocode output instead of asking users to paste file rows or pasting raw coordinates.
- `validate_jira_configuration` reports thin POC defaults or full configured fields and request types, including `PS Team`.
- `validate_roi_jira_configuration` reports exactly one ROI project key, service desk ID, request type ID, and mapped required request fields before ROI-direct creation is enabled.
- C360 internal API token is configured.
- Rock Productions C360 lookup smoke passes for `proj-cs-rockproductions`, including normalized variants, HubSpot company `8051493928`, and StaffAny org `Rock Productions`.
- Cron concurrency is capped with `cron.max_parallel_jobs: 1`.
- Morning reminder cron is enabled in cloud as a weekday no-agent script and uses Jira `duedate` only.
- Assignment hygiene cron is enabled in cloud as a weekday no-agent script and uses safe Jira PCO assignee, `PS Team`, and `duedate` fields only.
- EOD reminder catch-up cron is enabled in cloud as a weekday no-agent script and uses Jira `duedate` only.
- Reminder Slack mentions use `PSM_OPS_REMINDER_MENTION_MAP_PATH` when configured; unmapped PS Team values remain visible as `Mention gaps` and are not guessed.
- Reminder customer-team tags use reviewed `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH` source-link matches only and never cross-post to customer channels.
- ROI tracker sync cron is enabled in cloud as a no-agent script every 30 minutes during Singapore workdays and watches only linked `ps-wee-roi-tracker` PCO issues.
- Churn reporting chase cron is enabled in cloud as a Monday 09:00 SGT no-agent script, reads BigQuery renewal/churn marts only, and delivers to `slack:#team-rev-account-management`.
- Store review poll cron is enabled in cloud as an hourly no-agent script, reads AppFollow Reviews API, persists duplicate-suppression state by default, and delivers `PSM Ops automation: Store review triage` to `slack:#ps-weeman-bot-test`.
- VM-local cloud heartbeat cron is enabled every 15 minutes with local delivery disabled.
- PS WEE adoption digest cron is enabled as a no-agent weekday Slack automation with the `PSM Ops automation:` prefix.
- PS WEE adoption telemetry hook is installed under the profile hooks directory.
- Healthy no-agent checks print nothing and exit 0.

## Commands

Run source-packet verification from the repo root:

```bash
pnpm psm-ops-bot:verify
```

Run live health check on the cloud host:

```bash
apps/psm-ops-bot/runtime/check-health.sh
```

Run VM-local cloud heartbeat on the cloud host:

```bash
apps/psm-ops-bot/runtime/check-cloud-heartbeat.sh
```

It checks local systemd user service state and Hermes cron metadata only. It does not call Jira, C360, Slack, or model paths.

Run live profile drift audit after syncing packet files:

```bash
apps/psm-ops-bot/runtime/audit-live-profile.sh
```

Run the live Rock Productions C360 lookup smoke after deploy:

```bash
apps/psm-ops-bot/runtime/smoke-rock-productions-c360.sh
```

Expected success output:

```text
c360:rock-productions:ok:hubspot=8051493928:org=Rock Productions
```

## Cron Pattern

Install automatic due-date reminders and assignment hygiene under the cloud profile:

```bash
cp apps/psm-ops-bot/runtime/scripts/psm_ops_due_date_reminders.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_due_date_reminders.py
cp apps/psm-ops-bot/runtime/scripts/psm_ops_due_date_reminders.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_due_date_reminders_eod.py
cp apps/psm-ops-bot/runtime/scripts/psm_ops_pco_assignment_hygiene.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_pco_assignment_hygiene.py
cp apps/psm-ops-bot/runtime/scripts/psm_ops_roi_tracker_sync.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_roi_tracker_sync.py
cp apps/psm-ops-bot/runtime/scripts/psm_ops_churn_reporting_chase.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_churn_reporting_chase.py
cp apps/psm-ops-bot/runtime/scripts/psm_ops_store_review_poll.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_store_review_poll.py
mkdir -p ~/.hermes/profiles/psmopsbot/runtime/sql
cp apps/psm-ops-bot/runtime/sql/psm_ops_churn_projection_dashboard_292.sql \
  ~/.hermes/profiles/psmopsbot/runtime/sql/psm_ops_churn_projection_dashboard_292.sql
cp apps/psm-ops-bot/runtime/scripts/psm_ops_join_public_channels.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_join_public_channels.py
chmod 755 ~/.hermes/profiles/psmopsbot/scripts/psm_ops_due_date_reminders.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_due_date_reminders_eod.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_pco_assignment_hygiene.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_roi_tracker_sync.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_churn_reporting_chase.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_store_review_poll.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_join_public_channels.py

hermes -p psmopsbot cron create "0 1 * * 1-5" \
  --name "psmopsbot due-date reminders" \
  --script psm_ops_due_date_reminders.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"

hermes -p psmopsbot cron create "15 1 * * 1-5" \
  --name "psmopsbot assignment hygiene" \
  --script psm_ops_pco_assignment_hygiene.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"

hermes -p psmopsbot cron create "0 9 * * 1-5" \
  --name "psmopsbot due-date eod catch-up" \
  --script psm_ops_due_date_reminders_eod.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"

hermes -p psmopsbot cron create "*/30 1-10 * * 1-5" \
  --name "psmopsbot roi tracker sync" \
  --script psm_ops_roi_tracker_sync.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"

hermes -p psmopsbot cron create "0 1 * * 1" \
  --name "psmopsbot churn reporting chase" \
  --script psm_ops_churn_reporting_chase.py \
  --no-agent \
  --deliver "slack:#team-rev-account-management"

hermes -p psmopsbot cron create "0 * * * *" \
  --name "psmopsbot store review poll" \
  --script psm_ops_store_review_poll.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"

cp apps/psm-ops-bot/runtime/check-cloud-heartbeat.sh ~/.hermes/profiles/psmopsbot/scripts/psmopsbot-check-cloud-heartbeat.sh
hermes -p psmopsbot cron create "*/15 * * * *" \
  --name "psmopsbot local cloud heartbeat" \
  --script psmopsbot-check-cloud-heartbeat.sh \
  --no-agent

cp apps/psm-ops-bot/runtime/psm_ops_adoption_digest.py ~/.hermes/profiles/psmopsbot/scripts/psm_ops_adoption_digest.py
hermes -p psmopsbot cron create "0 2 * * 1-5" \
  --name "psmopsbot adoption digest" \
  --script psm_ops_adoption_digest.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"
```

The GCE host runs UTC, so `0 1 * * 1-5` is 09:00 Asia/Singapore on weekdays, `15 1 * * 1-5` is 09:15 Asia/Singapore on weekdays, `0 9 * * 1-5` is 17:00 Asia/Singapore on weekdays, `*/30 1-10 * * 1-5` checks ROI trackers every 30 minutes during Singapore workdays, `0 1 * * 1` sends the Monday 09:00 Asia/Singapore churn reporting chase, and `0 * * * *` polls store reviews hourly. Hermes cron does not pass script arguments, so the EOD cron uses the same source script copied under an `eod` filename; direct dry runs can still use `--mode morning|eod`. Store review no-arg cron runs persist state; manual preview uses `psm_ops_store_review_poll.py --dry-run`.

Install central audit/adoption telemetry after the profile exists:

```bash
mkdir -p ~/.hermes/profiles/psmopsbot/hooks ~/.hermes/profiles/psmopsbot/scripts
rsync -a apps/psm-ops-bot/runtime/hooks/psm-ops-adoption-telemetry/ \
  ~/.hermes/profiles/psmopsbot/hooks/psm-ops-adoption-telemetry/
rsync -a apps/psm-ops-bot/runtime/hooks/psm-ops-mention-guard/ \
  ~/.hermes/profiles/psmopsbot/hooks/psm-ops-mention-guard/
cp apps/psm-ops-bot/runtime/psm_ops_adoption_digest.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_adoption_digest.py

hermes -p psmopsbot cron create "0 2 * * 1-5" \
  --name "psmopsbot adoption digest" \
  --script psm_ops_adoption_digest.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"
```

`psm-ops-mention-guard` is observer-only on `agent:end` and posts a one-line warning to `PSM_OPS_CENTRAL_SLACK_CHANNEL_ID` whenever a Slack reply mentions a non-tagger (SCHE-19904). The hook resolves its own Slack user ID via `auth.test` (cached per process) so the bot's `<@>` self-reference is not flagged. `runtime/check-health.sh` smoke-tests `auth.test` at deploy time and fails with `slack:auth-test:<error>` or `slack:auth-test-missing-user-id` if the token cannot identify the bot. The audit alert itself is bot-authored and self-identifies as `PSM Ops mention-guard automation: ...` per the AGENTS.md Slack identity rule, and reports `psm-ops-mention-guard:alert-failed:<slack_error>` on stderr if Slack returns `ok=false` (missing_scope, not_in_channel, channel_not_found).

Set `PSM_OPS_CENTRAL_SLACK_CHANNEL_ID` to the central ops channel ID in the live profile `.env`; prefer the ID over the name.

After Slack app reinstall or scope changes, repair public/open-channel membership with bot-owned auth:

```bash
~/.hermes/profiles/psmopsbot/scripts/psm_ops_join_public_channels.py --dry-run
~/.hermes/profiles/psmopsbot/scripts/psm_ops_join_public_channels.py --apply
```

If this reports `slack:public-channel-join-failed:...:error=missing_scope`, the Slack app has not been reinstalled with `channels:join` yet.

Optional reminder and assignment hygiene mention map:

```json
{
  "ps_leads": {
    "Josica": [{"type": "user", "id": "U456", "label": "Josica"}]
  },
  "ps_teams": {
    "Kai Yi": [{"type": "user", "id": "U123", "label": "Kai Yi"}],
    "CS Duty": [{"type": "usergroup", "id": "S123", "handle": "cs-duty"}]
  }
}
```

Store this runtime JSON outside git and point `PSM_OPS_REMINDER_MENTION_MAP_PATH` at it.

## Failure Behavior

On failure, print only the failing subsystem and next check. Do not print secrets, env values, raw logs, raw Slack messages, raw Jira comments, raw customer source data, phone numbers, or bulk exports. The Rock Productions C360 smoke may print `searched_variants`, `match_count`, `missing_mapping`, `confidence`, and `caveat` only.
