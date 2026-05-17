#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$PROFILE_DIR" ]; then
  export HERMES_HOME="$PROFILE_DIR"
fi
EXPECT_MODEL_PROVIDER="${EXPECT_MODEL_PROVIDER:-anthropic}"
EXPECT_MODEL_DEFAULT="${EXPECT_MODEL_DEFAULT:-claude-sonnet-4-6}"
EXPECT_HOME_CHANNEL="${EXPECT_HOME_CHANNEL:-C0B32M34J3W}"
EXPECT_ALLOWED_CHANNELS="${EXPECT_ALLOWED_CHANNELS:-C0B32M34J3W,C0AJAUNCEL8,C01RZ7SHC8K,CF8PK6V4J}"
EXPECT_KER_ALLOWED_CHANNELS="${EXPECT_KER_ALLOWED_CHANNELS:-C0B32M34J3W,C0AJAUNCEL8,C01RZ7SHC8K}"
EXPECT_PRODUCT_COMMITMENT_ALLOWED_CHANNELS="${EXPECT_PRODUCT_COMMITMENT_ALLOWED_CHANNELS:-C0B32M34J3W,C01RZ7SHC8K}"
EXPECT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME="${EXPECT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME:-all-bugs-production}"
GATEWAY_LAUNCHD_LABEL="${LAUNCHBOT_GATEWAY_LAUNCHD_LABEL:-ai.hermes.gateway-$PROFILE}"
GATEWAY_SERVICE_NAME="${LAUNCHBOT_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

if [ -r "$PROFILE_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$PROFILE_DIR/.env"
  set +a
fi

EXPECT_PANTHEON_REPO_URL="${EXPECT_PANTHEON_REPO_URL:-git@github.com:staffany-eng/pantheon.git}"
EXPECT_PANTHEON_BRANCH="${EXPECT_PANTHEON_BRANCH:-develop}"
PANTHEON_REPO_DIR="${LAUNCHBOT_PANTHEON_REPO_DIR:-$PROFILE_DIR/source/pantheon}"
PANTHEON_STATUS_PATH="${LAUNCHBOT_PANTHEON_STATUS_PATH:-$PROFILE_DIR/runtime/pantheon-repo-status.json}"
PANTHEON_STATUS_MAX_AGE_SECONDS="${LAUNCHBOT_PANTHEON_STATUS_MAX_AGE_SECONDS:-172800}"
HELP_ARTICLE_VIDEO_REGISTRY_PATH="${LAUNCHBOT_VIDEO_PLACEMENT_REGISTRY:-$PROFILE_DIR/source/launchbot/skills/help-article-generator/references/video-placement-registry.json}"
FEATURE_INTAKE_MONITOR_SCRIPT="${LAUNCHBOT_FEATURE_INTAKE_MONITOR_SCRIPT:-$PROFILE_DIR/scripts/launchbot-monitor-feature-intake.py}"
SUPPORT_WATCH_MONITOR_SCRIPT="${LAUNCHBOT_SUPPORT_WATCH_MONITOR_SCRIPT:-$PROFILE_DIR/scripts/launchbot-monitor-support-watch.py}"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

check_mcp_server() {
  server_name="$1"
  expected_count="$2"
  server_file="$3"
  mcp_out="$(hermes -p "$PROFILE" mcp test "$server_name" 2>&1)" && {
    count="$(printf '%s\n' "$mcp_out" | sed -nE 's/.*Tools discovered: ([0-9]+).*/\1/p' | tail -1)"
    [ "$count" = "$expected_count" ] || fail "mcp:$server_name:tools=${count:-unavailable}:expected=$expected_count"
    return 0
  }
  if printf '%s\n' "$mcp_out" | grep -Fq "StdioServerParameters"; then
    "$hermes_python" -m py_compile "$PROFILE_DIR/source/launchbot/runtime/mcp/$server_file" || fail "mcp:$server_name:py-compile-failed"
    return 0
  fi
  fail "mcp:$server_name:test-failed"
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

need_command hermes
need_command git
config_path="$(hermes -p "$PROFILE" config path 2>/dev/null)" || fail "hermes:config-path-failed"
[ -r "$config_path" ] || fail "hermes:config-unreadable"
hermes -p "$PROFILE" config check >/dev/null 2>&1 || fail "hermes:config-check-failed"
hermes_python="$HERMES_AGENT_DIR/venv/bin/python"
[ -x "$hermes_python" ] || fail "hermes:python-not-found"

case "$(uname -s)" in
  Darwin)
    need_command launchctl
    launchctl print "gui/$(id -u)/$GATEWAY_LAUNCHD_LABEL" >/dev/null 2>&1 || fail "gateway:not-running"
    ;;
  Linux)
    need_command systemctl
    systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME" || fail "gateway:not-running"
    ;;
  *)
    hermes -p "$PROFILE" gateway status >/dev/null 2>&1 || fail "gateway:status-failed"
    ;;
esac

"$hermes_python" - "$config_path" "$EXPECT_MODEL_PROVIDER" "$EXPECT_MODEL_DEFAULT" "$EXPECT_HOME_CHANNEL" "$EXPECT_ALLOWED_CHANNELS" "$EXPECT_KER_ALLOWED_CHANNELS" "$EXPECT_PRODUCT_COMMITMENT_ALLOWED_CHANNELS" "$EXPECT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME" <<'PY' || exit 1
import os
import sys
from pathlib import Path

import yaml

config_path, expected_provider, expected_model, expected_home_channel, expected_allowed_channels, expected_ker_channels, expected_commitment_channels, expected_support_watch_output = sys.argv[1:9]
config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

model = config.get("model") or {}
if model.get("provider") != expected_provider:
    fail("model:provider-unexpected")
if model.get("default") != expected_model:
    fail("model:default-unexpected")

security = config.get("security") or {}
if security.get("redact_secrets") is not True:
    fail("security:redact-secrets-not-enabled")

display = config.get("display") or {}
if display.get("interim_assistant_messages") is not False:
    fail("display:interim-assistant-messages-not-disabled")
if display.get("streaming") is not False:
    fail("display:streaming-not-disabled")
if display.get("tool_progress") != "off":
    fail("display:tool-progress-not-off")

platforms = config.get("platforms") or {}
slack_platform = platforms.get("slack") or {}
if slack_platform.get("gateway_restart_notification") is not False:
    fail("platforms:slack:gateway-restart-notification-not-disabled")

slack = config.get("slack") or {}
if slack.get("require_mention") is not True:
    fail("slack:require-mention-not-enabled")
if slack.get("reactions") is not False:
    fail("slack:reactions-not-disabled")
if str(config.get("SLACK_HOME_CHANNEL") or "").strip('"') != expected_home_channel:
    fail("slack:home-channel-unexpected")
allowed = str(slack.get("allowed_channels") or "")
for channel_id in [item.strip() for item in expected_allowed_channels.split(",") if item.strip()]:
    if channel_id not in allowed:
        fail(f"slack:allowed-channel-missing:{channel_id}")

monitor = config.get("feature_intake_monitor") or {}
if monitor.get("mode") != "no_agent_slack_poll":
    fail("feature-intake-monitor:mode-unexpected")
if monitor.get("configured_channel_ids_env") != "LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS":
    fail("feature-intake-monitor:channel-env-unexpected")
if monitor.get("state_path_env") != "LAUNCHBOT_FEATURE_INTAKE_MONITOR_STATE_PATH":
    fail("feature-intake-monitor:state-path-env-unexpected")
if monitor.get("required_confirmation") != "create intake":
    fail("feature-intake-monitor:confirmation-unexpected")
if monitor.get("no_raw_transcript_persistence") is not True:
    fail("feature-intake-monitor:raw-transcript-persistence-not-disabled")
if monitor.get("normal_gateway_require_mention") is not True:
    fail("feature-intake-monitor:normal-gateway-require-mention-not-enabled")
if str(config.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS") or "").strip('"') != "CF8PK6V4J":
    fail("feature-intake-monitor:channels-unexpected")
if str(config.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_STATE_PATH") or "").strip('"') != "~/.hermes/profiles/launchbot/runtime/feature-intake-monitor-state.json":
    fail("feature-intake-monitor:state-path-unexpected")
if str(config.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_MAX_MESSAGES_PER_RUN") or "").strip('"') != "100":
    fail("feature-intake-monitor:max-messages-unexpected")
if str(config.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_OVERLAP_SECONDS") or "").strip('"') != "600":
    fail("feature-intake-monitor:overlap-unexpected")

support_watch_monitor = config.get("support_watch_monitor") or {}
if support_watch_monitor.get("mode") != "no_agent_weekly_report":
    fail("support-watch-monitor:mode-unexpected")
if support_watch_monitor.get("source") != "bigquery":
    fail("support-watch-monitor:source-unexpected")
if support_watch_monitor.get("source_env") != "LAUNCHBOT_SUPPORT_WATCH_SOURCE":
    fail("support-watch-monitor:source-env-unexpected")
if support_watch_monitor.get("intercom_project_env") != "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT":
    fail("support-watch-monitor:intercom-project-env-unexpected")
if support_watch_monitor.get("intercom_dataset_env") != "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET":
    fail("support-watch-monitor:intercom-dataset-env-unexpected")
if support_watch_monitor.get("analytics_dataset_env") != "LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET":
    fail("support-watch-monitor:analytics-dataset-env-unexpected")
if support_watch_monitor.get("include_whatsapp_env") != "LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP":
    fail("support-watch-monitor:include-whatsapp-env-unexpected")
if support_watch_monitor.get("whatsapp_view_env") != "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW":
    fail("support-watch-monitor:whatsapp-view-env-unexpected")
if support_watch_monitor.get("output_channel_name_env") != "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME":
    fail("support-watch-monitor:output-channel-name-env-unexpected")
if support_watch_monitor.get("output_channel_id_env") != "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID":
    fail("support-watch-monitor:output-channel-id-env-unexpected")
if support_watch_monitor.get("dedupe_channel_ids_env") != "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS":
    fail("support-watch-monitor:dedupe-channel-env-unexpected")
if support_watch_monitor.get("dedupe_channel_names_env") != "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES":
    fail("support-watch-monitor:dedupe-channel-names-env-unexpected")
if support_watch_monitor.get("edt_jql_env") != "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL":
    fail("support-watch-monitor:edt-jql-env-unexpected")
if support_watch_monitor.get("state_path_env") != "LAUNCHBOT_SUPPORT_WATCH_STATE_PATH":
    fail("support-watch-monitor:state-path-env-unexpected")
if support_watch_monitor.get("schedule_utc") != "0 1 * * 4":
    fail("support-watch-monitor:schedule-unexpected")
if support_watch_monitor.get("no_raw_transcript_persistence") is not True:
    fail("support-watch-monitor:raw-transcript-persistence-not-disabled")
if support_watch_monitor.get("no_ticket_creation") is not True:
    fail("support-watch-monitor:ticket-creation-not-disabled")
if support_watch_monitor.get("no_engineer_tags") is not True:
    fail("support-watch-monitor:engineer-tags-not-disabled")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME") or "").strip('"') != expected_support_watch_output:
    fail("support-watch-monitor:output-channel-name-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_STATE_PATH") or "").strip('"') != "~/.hermes/profiles/launchbot/runtime/support-watch-state.json":
    fail("support-watch-monitor:state-path-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_LOOKBACK_DAYS") or "").strip('"') != "7":
    fail("support-watch-monitor:lookback-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_SOURCE") or "").strip('"') != "bigquery":
    fail("support-watch-monitor:source-config-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT") or "").strip('"') != "staffany-warehouse":
    fail("support-watch-monitor:intercom-project-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET") or "").strip('"') != "intercom":
    fail("support-watch-monitor:intercom-dataset-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET") or "").strip('"') != "analytics":
    fail("support-watch-monitor:analytics-dataset-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP") or "").strip('"') != "true":
    fail("support-watch-monitor:include-whatsapp-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW") or "").strip('"') != "gsheets.cs_tickets_logs_all_view":
    fail("support-watch-monitor:whatsapp-view-unexpected")
if str(config.get("LAUNCHBOT_SUPPORT_WATCH_MAX_TICKETS") or "").strip('"') != "100":
    fail("support-watch-monitor:max-tickets-unexpected")

mcp_servers = config.get("mcp_servers") or {}
launchbot_ker = mcp_servers.get("launchbot_ker") or {}
tools = set(launchbot_ker.get("tool_allowlist") or [])
expected_tools = {"find_ker_ticket_from_slack_thread", "lookup_ker_ticket_by_key"}
if tools != expected_tools:
    fail("mcp:launchbot_ker:tool-allowlist-unexpected")
ker_policy = launchbot_ker.get("access_policy") or {}
ker_default_channels = set(ker_policy.get("default_channel_ids") or [])
ker_config_channels = str(config.get("LAUNCHBOT_KER_ALLOWED_CHANNEL_IDS") or "")
ker_process_env_channels = str(os.environ.get("LAUNCHBOT_KER_ALLOWED_CHANNEL_IDS") or "")
for channel_id in [item.strip() for item in expected_ker_channels.split(",") if item.strip()]:
    if channel_id not in ker_default_channels:
        fail(f"mcp:launchbot_ker:default-channel-missing:{channel_id}")
    if channel_id not in ker_config_channels:
        fail(f"mcp:launchbot_ker:env-channel-missing:{channel_id}")
    if channel_id not in ker_process_env_channels:
        fail(f"mcp:launchbot_ker:process-env-channel-missing:{channel_id}")

launchbot_ifi = mcp_servers.get("launchbot_ifi") or {}
ifi_tools = set(launchbot_ifi.get("tool_allowlist") or [])
expected_ifi_tools = {
    "preview_ifi_feature_request_tracking",
    "create_or_update_ifi_feature_request_tracking",
    "preview_ifi_feature_request_from_bd_note",
    "create_or_update_ifi_feature_request_from_bd_note",
}
if ifi_tools != expected_ifi_tools:
    fail("mcp:launchbot_ifi:tool-allowlist-unexpected")
ifi_policy = launchbot_ifi.get("access_policy") or {}
if ifi_policy.get("mode") != "preview_first_confirmed_jira_mutation":
    fail("mcp:launchbot_ifi:mode-unexpected")
if ifi_policy.get("approval_marker") != "confirm IFI":
    fail("mcp:launchbot_ifi:approval-marker-unexpected")
if ifi_policy.get("will_post_message") is not False:
    fail("mcp:launchbot_ifi:will-post-message-must-be-false")
if ifi_policy.get("bd_notes_require_confirmed_hubspot_company_id") is not True:
    fail("mcp:launchbot_ifi:bd-notes-confirmed-company-required")
if ifi_policy.get("ambiguous_company_action") != "ask_for_hubspot_company_link_or_numeric_id":
    fail("mcp:launchbot_ifi:ambiguous-company-action-unexpected")

launchbot_product_commitment = mcp_servers.get("launchbot_product_commitment") or {}
commitment_tools = set(launchbot_product_commitment.get("tool_allowlist") or [])
expected_commitment_tools = {"check_product_commitment_from_slack_thread"}
if commitment_tools != expected_commitment_tools:
    fail("mcp:launchbot_product_commitment:tool-allowlist-unexpected")
commitment_policy = launchbot_product_commitment.get("access_policy") or {}
if commitment_policy.get("mode") != "read_only_commitment_check":
    fail("mcp:launchbot_product_commitment:mode-unexpected")
if commitment_policy.get("configured_channel_ids_env") != "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS":
    fail("mcp:launchbot_product_commitment:configured-channels-env-unexpected")
commitment_default_channels = set(commitment_policy.get("default_channel_ids") or [])
commitment_config_channels = str(config.get("LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS") or "")
for channel_id in [item.strip() for item in expected_commitment_channels.split(",") if item.strip()]:
    if channel_id not in commitment_default_channels:
        fail(f"mcp:launchbot_product_commitment:default-channel-missing:{channel_id}")
    if channel_id not in commitment_config_channels:
        fail(f"mcp:launchbot_product_commitment:env-channel-missing:{channel_id}")
for key in ["no_slack_post_from_mcp", "no_jira_mutation", "no_jira_comments", "no_jira_transitions", "no_jira_assignment", "no_timeline_inference", "no_intake_creation"]:
    if commitment_policy.get(key) is not True:
        fail(f"mcp:launchbot_product_commitment:{key}:must-be-true")

launchbot_feature_intake = mcp_servers.get("launchbot_feature_intake") or {}
feature_intake_tools = set(launchbot_feature_intake.get("tool_allowlist") or [])
expected_feature_intake_tools = {"preview_feature_intake_from_slack_thread", "create_feature_intake_from_slack_thread"}
if feature_intake_tools != expected_feature_intake_tools:
    fail("mcp:launchbot_feature_intake:tool-allowlist-unexpected")
feature_intake_policy = launchbot_feature_intake.get("access_policy") or {}
if feature_intake_policy.get("mode") != "confirmed_jpd_intake_create":
    fail("mcp:launchbot_feature_intake:mode-unexpected")
if feature_intake_policy.get("required_confirmation") != "create intake":
    fail("mcp:launchbot_feature_intake:confirmation-unexpected")
for key in ["no_slack_post_from_mcp", "no_jira_comments", "no_jira_transitions", "no_jira_assignment"]:
    if feature_intake_policy.get(key) is not True:
        fail(f"mcp:launchbot_feature_intake:{key}:must-be-true")

launchbot_support_watch = mcp_servers.get("launchbot_support_watch") or {}
support_watch_tools = set(launchbot_support_watch.get("tool_allowlist") or [])
expected_support_watch_tools = {"preview_weekly_support_watch_report"}
if support_watch_tools != expected_support_watch_tools:
    fail("mcp:launchbot_support_watch:tool-allowlist-unexpected")
support_watch_policy = launchbot_support_watch.get("access_policy") or {}
if support_watch_policy.get("mode") != "read_only_weekly_support_watch":
    fail("mcp:launchbot_support_watch:mode-unexpected")
if support_watch_policy.get("source") != "bigquery":
    fail("mcp:launchbot_support_watch:source-unexpected")
if support_watch_policy.get("output_channel_name") != expected_support_watch_output:
    fail("mcp:launchbot_support_watch:output-channel-unexpected")
for key in ["no_slack_post_from_mcp", "no_ticket_creation", "no_engineer_tags", "no_owner_assignment", "no_raw_support_transcript_persistence", "no_slack_connector_fallback", "no_user_token_fallback"]:
    if support_watch_policy.get(key) is not True:
        fail(f"mcp:launchbot_support_watch:{key}:must-be-true")

launchbot_help_article = mcp_servers.get("launchbot_help_article") or {}
video_tools = set(launchbot_help_article.get("tool_allowlist") or [])
expected_video_tools = {"preview_help_article_video_update", "create_help_article_video_update_draft"}
if video_tools != expected_video_tools:
    fail("mcp:launchbot_help_article:tool-allowlist-unexpected")
video_policy = launchbot_help_article.get("access_policy") or {}
if video_policy.get("mode") != "draft_only_registered_video_slots":
    fail("mcp:launchbot_help_article:mode-unexpected")
for key in ["allow_publish", "allow_delete", "allow_tag_mutation", "allow_collection_mutation"]:
    if video_policy.get(key) is not False:
        fail(f"mcp:launchbot_help_article:{key}:must-be-false")
PY

for key in \
  SLACK_BOT_TOKEN \
  HUBSPOT_ACCESS_TOKEN \
  JIRA_BASE_URL \
  JIRA_EMAIL \
  JIRA_API_TOKEN \
  JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID \
  LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN; do
  value="${!key:-}"
  [ -n "$value" ] || fail "env:$key:missing"
done
[ "${JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID:-}" = "customfield_10881" ] || fail "env:JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID:unexpected"

check_mcp_server launchbot_ker 2 launchbot_ker_server.py
check_mcp_server launchbot_ifi 4 launchbot_ifi_server.py
check_mcp_server launchbot_product_commitment 1 launchbot_product_commitment_server.py
check_mcp_server launchbot_feature_intake 2 launchbot_feature_intake_server.py
check_mcp_server launchbot_support_watch 1 launchbot_support_watch_server.py
check_mcp_server launchbot_help_article 2 launchbot_help_article_server.py

[ -r "$FEATURE_INTAKE_MONITOR_SCRIPT" ] || fail "feature-intake-monitor:script-missing"
"$hermes_python" -m py_compile "$FEATURE_INTAKE_MONITOR_SCRIPT" || fail "feature-intake-monitor:py-compile-failed"
"$hermes_python" -m py_compile "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_feature_intake_core.py" || fail "mcp:launchbot_feature_intake_core:py-compile-failed"
[ -r "$SUPPORT_WATCH_MONITOR_SCRIPT" ] || fail "support-watch-monitor:script-missing"
"$hermes_python" -m py_compile "$SUPPORT_WATCH_MONITOR_SCRIPT" || fail "support-watch-monitor:py-compile-failed"
"$hermes_python" -m py_compile "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_support_watch_core.py" || fail "mcp:launchbot_support_watch_core:py-compile-failed"

[ "${LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME:-all-bugs-production}" = "all-bugs-production" ] || fail "env:LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME:unexpected"
[ -n "${LAUNCHBOT_SUPPORT_WATCH_EDT_JQL:-}" ] || fail "env:LAUNCHBOT_SUPPORT_WATCH_EDT_JQL:missing"
"$hermes_python" - "$PROFILE_DIR" <<'PY' || exit 1
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

profile_dir = Path(sys.argv[1])
mcp_dir = profile_dir / "source" / "launchbot" / "runtime" / "mcp"
sys.path.insert(0, str(mcp_dir))

import launchbot_support_watch_core as support_watch  # noqa: E402


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
if not token:
    fail("env:SLACK_BOT_TOKEN:missing")

request = urllib.request.Request(
    urllib.parse.urljoin(support_watch.SLACK_API_BASE_URL, "auth.test"),
    data=urllib.parse.urlencode({}).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": support_watch.USER_AGENT,
    },
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
        scopes = {item.strip() for item in (response.headers.get("x-oauth-scopes") or "").split(",") if item.strip()}
except Exception as error:
    fail(f"slack:auth-test-failed:{support_watch.safe_error(str(error))}")
if not payload.get("ok"):
    fail(f"slack:auth-test-not-ok:{support_watch.safe_error(str(payload.get('error') or 'unknown_error'))}")
for scope in ("channels:read", "channels:history", "chat:write"):
    if scope not in scopes:
        fail(f"slack:scope-missing:{scope}")

output_name = os.environ.get("LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME", support_watch.OUTPUT_CHANNEL_NAME).strip().lstrip("#")
output_id = os.environ.get("LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID", "").strip() or support_watch.resolve_slack_channel_id(output_name)
if not output_id:
    fail(f"support-watch:output-channel-unresolved:{output_name}")
try:
    output_info = support_watch.slack_api("conversations.info", {"channel": output_id})
except Exception as error:
    fail(f"support-watch:output-channel-info-failed:{support_watch.safe_error(str(error))}")
output_channel = output_info.get("channel") or {}
if output_channel.get("name") != output_name:
    fail(f"support-watch:output-channel-name-mismatch:{output_id}")
if output_channel.get("is_member") is not True:
    fail(f"support-watch:output-channel-not-member:{output_id}")

dedupe_ids = support_watch.dedupe_channel_ids()
if not dedupe_ids:
    fail("support-watch:dedupe-channel-unresolved")
for channel_id in dedupe_ids:
    try:
        support_watch.slack_api("conversations.info", {"channel": channel_id})
    except Exception as error:
        fail(f"support-watch:dedupe-channel-info-failed:{support_watch.safe_error(str(error))}")
PY

[ -r "$HELP_ARTICLE_VIDEO_REGISTRY_PATH" ] || fail "help-article-video-registry:missing"
"$hermes_python" - "$HELP_ARTICLE_VIDEO_REGISTRY_PATH" <<'PY' || exit 1
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

try:
    registry = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    fail("help-article-video-registry:invalid-json")

if registry.get("version") != 1:
    fail("help-article-video-registry:version-unexpected")
articles = registry.get("articles")
if not isinstance(articles, list) or len(articles) < 3:
    fail("help-article-video-registry:articles-missing")
for article in articles:
    if article.get("locale") != "en":
        fail("help-article-video-registry:non-en-locale")
    if not article.get("intercom_article_id"):
        fail("help-article-video-registry:article-id-missing")
    slots = article.get("slots")
    if not isinstance(slots, list) or not slots:
        fail("help-article-video-registry:slot-missing")
    for slot in slots:
        if slot.get("provider") != "loom":
            fail("help-article-video-registry:provider-unexpected")
        if slot.get("replace_policy") != "replace_next_video_after_anchor":
            fail("help-article-video-registry:replace-policy-unexpected")
PY

[ -d "$PANTHEON_REPO_DIR/.git" ] || fail "pantheon:checkout-missing"
pantheon_remote="$(git -C "$PANTHEON_REPO_DIR" remote get-url origin 2>/dev/null)" || fail "pantheon:remote-unreadable"
[ "$pantheon_remote" = "$EXPECT_PANTHEON_REPO_URL" ] || fail "pantheon:remote-unexpected"
pantheon_branch="$(git -C "$PANTHEON_REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)" || fail "pantheon:branch-unreadable"
[ "$pantheon_branch" = "$EXPECT_PANTHEON_BRANCH" ] || fail "pantheon:branch-unexpected"
pantheon_status="$(git -C "$PANTHEON_REPO_DIR" status --porcelain=v1 2>/dev/null)" || fail "pantheon:status-unreadable"
[ -z "$pantheon_status" ] || fail "pantheon:dirty-checkout"
[ -r "$PANTHEON_STATUS_PATH" ] || fail "pantheon:status-json-missing"

"$hermes_python" - "$PANTHEON_STATUS_PATH" "$EXPECT_PANTHEON_REPO_URL" "$EXPECT_PANTHEON_BRANCH" "$PANTHEON_REPO_DIR" "$PANTHEON_STATUS_MAX_AGE_SECONDS" <<'PY' || exit 1
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path, expected_remote, expected_branch, expected_path, max_age_seconds = sys.argv[1:6]

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

try:
    status = json.loads(Path(status_path).read_text(encoding="utf-8"))
except Exception:
    fail("pantheon:status-json-invalid")

if status.get("remote") != expected_remote:
    fail("pantheon:status-remote-unexpected")
if status.get("branch") != expected_branch:
    fail("pantheon:status-branch-unexpected")
if status.get("path") != expected_path:
    fail("pantheon:status-path-unexpected")
sha = status.get("sha")
if not isinstance(sha, str) or len(sha) != 40:
    fail("pantheon:status-sha-invalid")
updated_at = status.get("updated_at")
if not isinstance(updated_at, str):
    fail("pantheon:status-updated-at-missing")
try:
    timestamp = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
except ValueError:
    fail("pantheon:status-updated-at-invalid")
age = (datetime.now(timezone.utc) - timestamp).total_seconds()
if age < 0:
    fail("pantheon:status-updated-at-future")
if age > int(max_age_seconds):
    fail("pantheon:status-stale")
PY
