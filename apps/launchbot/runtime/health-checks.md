# Health Checks

Launchbot needs a small no-agent health check before it can be treated as reliable.

Expected checks:

- Hermes gateway service for `launchbot` is active.
- Secret redaction remains enabled.
- Model route is `model.provider=anthropic`, `model.default=claude-sonnet-4-6`.
- Slack quiet settings are enabled: no streaming, no tool progress, no interim assistant messages, no reactions, and no gateway restart notifications.
- `SLACK_HOME_CHANNEL` is `C0B32M34J3W`.
- Slack `allowed_channels` is empty so normal replies work in any channel where Launchbot is invited and mentioned; lane-specific tools still keep their own channel/env gates.
- `LAUNCHBOT_KER_ALLOWED_CHANNEL_IDS` includes `C0B32M34J3W`, `C0AJAUNCEL8`, and `C01RZ7SHC8K`; `#all-product-questions` is read-only KER lookup only.
- Normal Slack gateway replies keep `slack.require_mention=true`; `#input-features-ux` monitoring is handled by the no-agent feature-intake monitor cron.
- Feature-intake monitor channel IDs default to `CF8PK6V4J`, state path defaults to `~/.hermes/profiles/launchbot/runtime/feature-intake-monitor-state.json`, max messages per run defaults to `100`, and overlap defaults to `600` seconds.
- Feature-intake monitor script is readable and compiles at `~/.hermes/profiles/launchbot/scripts/launchbot-monitor-feature-intake.py`.
- Support-watch output channel defaults to `#all-bugs-production`, source defaults to BigQuery Intercom conversations with WhatsApp support logs enabled, BigQuery query timeout defaults to `240` seconds, dry-runs report full window counts plus fetched candidate counts, state path defaults to `~/.hermes/profiles/launchbot/runtime/support-watch-state.json`, lookback defaults to `7` days, max support rows defaults to `100`, and cron is `0 1 * * 4` UTC / Thursday 09:00 SGT.
- WhatsApp support logs are refreshed into native table `staffany-warehouse.analytics.support_watch_whatsapp_ticket_logs` by BigQuery scheduled query `Launchbot support watch WhatsApp native mirror refresh` on `every day 00:30` UTC. The Launchbot VM must not query the Drive-backed `gsheets` source during weekly scans.
- Support-watch monitor script is readable and compiles at `~/.hermes/profiles/launchbot/scripts/launchbot-monitor-support-watch.py`.
- `launchbot_ker` MCP exposes only `find_ker_ticket_from_slack_thread` and `lookup_ker_ticket_by_key`.
- `launchbot_ifi` MCP exposes only `preview_ifi_feature_request_tracking`, `create_or_update_ifi_feature_request_tracking`, `preview_ifi_feature_request_from_bd_note`, and `create_or_update_ifi_feature_request_from_bd_note`.
- `launchbot_product_commitment` MCP exposes only `check_product_commitment_from_slack_thread`.
- `launchbot_feature_intake` MCP exposes only `preview_feature_intake_from_slack_thread` and `create_feature_intake_from_slack_thread`.
- `launchbot_support_watch` MCP exposes only `preview_weekly_support_watch_report`.
- `launchbot_help_article` MCP exposes only `preview_help_article_video_update` and `create_help_article_video_update_draft`.
- KER lookup, product commitment checks, and feature intake have `SLACK_BOT_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` in the live profile env.
- IFI tracking has `HUBSPOT_ACCESS_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and `JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID=customfield_10881` in the live profile env.
- Product commitment checks have `LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS` in config or the live profile env. `LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS` is optional and must contain only reviewed Jira commitment field IDs.
- The feature-intake monitor uses the same `SLACK_BOT_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`, and uses Slack `chat.postMessage` only for Launchbot-owned `Launchbot automation:` previews/results.
- The support-watch MCP uses service-account or ADC BigQuery access to `staffany-warehouse.intercom.conversations`, `staffany-warehouse.intercom.conversation_parts`, and optionally the native `staffany-warehouse.analytics.support_watch_whatsapp_ticket_logs` mirror; it uses Slack/Jira read-only for dedupe and never posts Slack or creates tickets.
- The support-watch health check verifies the native WhatsApp mirror metadata through BigQuery and fails if `lastModifiedTime` is older than `LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_MAX_STALENESS_HOURS`, default `36`.
- The support-watch monitor uses BigQuery access, `SLACK_BOT_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `LAUNCHBOT_SUPPORT_WATCH_SOURCE=bigquery`, `LAUNCHBOT_SUPPORT_WATCH_BQ_TIMEOUT_SECONDS=240`, `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME=all-bugs-production`, optional `LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID`, `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES=team-cs-eng-duty` or explicit `LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS`, and `LAUNCHBOT_SUPPORT_WATCH_EDT_JQL`.
- The support-watch health check verifies the Launchbot bot token has `channels:read`, `channels:history`, `channels:join`, and `chat:write`, resolves public support-watch channels without requesting private-channel scope, joins configured public support-watch channels with bot-owned auth when needed, and confirms Launchbot is a member of the output channel before cron is considered healthy.
- Video-only help article updates have `LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN` in the live profile env.
- Help article video placement registry is readable at `~/.hermes/profiles/launchbot/source/launchbot/skills/help-article-generator/references/video-placement-registry.json`.
- Pantheon is cloned at `~/.hermes/profiles/launchbot/source/pantheon`, with remote `git@github.com:staffany-eng/pantheon.git`, branch `develop`, clean worktree, and a fresh update status JSON.
- If the VM does not already have GitHub repo access, use a read-only GitHub deploy key at `~/.hermes/profiles/launchbot/ssh/pantheon_deploy_key`.
- Healthy checks print nothing and exit 0.

Install profile-local health script:

```bash
mkdir -p ~/.hermes/profiles/launchbot/scripts
cp apps/launchbot/runtime/check-health.sh ~/.hermes/profiles/launchbot/scripts/launchbot-check-health.sh
cp apps/launchbot/runtime/monitor-feature-intake.py ~/.hermes/profiles/launchbot/scripts/launchbot-monitor-feature-intake.py
cp apps/launchbot/runtime/monitor-support-watch.py ~/.hermes/profiles/launchbot/scripts/launchbot-monitor-support-watch.py
hermes -p launchbot cron create "*/5 * * * *" \
  --name "launchbot health check" \
  --script launchbot-check-health.sh \
  --no-agent
~/.hermes/profiles/launchbot/scripts/launchbot-monitor-feature-intake.py --dry-run --channel CF8PK6V4J --since-minutes 30
hermes -p launchbot cron create "* * * * *" \
  --name "launchbot feature intake monitor" \
  --script launchbot-monitor-feature-intake.py \
  --no-agent
LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME=all-bugs-production \
LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES=team-cs-eng-duty \
  ~/.hermes/profiles/launchbot/scripts/launchbot-monitor-support-watch.py --dry-run --max-tickets 20
hermes -p launchbot cron create "0 1 * * 4" \
  --name "launchbot support watch" \
  --script launchbot-monitor-support-watch.py \
  --no-agent
```

Install the BigQuery scheduled query that refreshes the native WhatsApp mirror. This must run as a Google identity with Drive access to the backing Google Sheet; do not move this refresh into VM cron unless the VM identity has explicit Drive access:

```bash
bq mk --transfer_config \
  --project_id=staffany-warehouse \
  --location=asia-southeast1 \
  --target_dataset=analytics \
  --display_name="Launchbot support watch WhatsApp native mirror refresh" \
  --data_source=scheduled_query \
  --schedule="every day 00:30" \
  --params="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.dumps({
  "query": Path("apps/launchbot/runtime/support-watch-whatsapp-refresh.sql").read_text(),
  "use_legacy_sql": False,
}))
PY
)"
```

Install the profile-local Pantheon updater only after the VM has GitHub SSH access to `staffany-eng/pantheon`:

```bash
mkdir -p ~/.hermes/profiles/launchbot/scripts
cp apps/launchbot/runtime/update-pantheon-repo.sh ~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh
test -r ~/.hermes/profiles/launchbot/ssh/pantheon_deploy_key.pub || ssh-keygen -t ed25519 -N "" -C "launchbot-pantheon-readonly" -f ~/.hermes/profiles/launchbot/ssh/pantheon_deploy_key
# Add the generated `.pub` file to `staffany-eng/pantheon` as a read-only deploy key before running the updater.
~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh
hermes -p launchbot cron create "0 22 * * *" \
  --name "launchbot pantheon repo update" \
  --script launchbot-update-pantheon-repo.sh \
  --no-agent
```

Without VM GitHub SSH access, seed `~/.hermes/profiles/launchbot/source/pantheon` from a trusted bundle and keep the health check honest: it will fail once `pantheon-repo-status.json` is older than `LAUNCHBOT_PANTHEON_STATUS_MAX_AGE_SECONDS`.

The Pantheon cron uses `0 22 * * *`, which is 06:00 Asia/Singapore on the current UTC GCP VM default. If the deployment host timezone is changed, keep the job daily and document the host timezone in the live repair note.

The support-watch cron uses `0 1 * * 4`, which is Thursday 09:00 Asia/Singapore on the current UTC GCP VM default.

The WhatsApp mirror scheduled query uses `every day 00:30` UTC, which is 08:30 Asia/Singapore, before the Thursday 09:00 SGT support-watch run.

The current Hermes CLI uses the deployment host timezone for cron scheduling and does not expose a `--timezone` flag.
