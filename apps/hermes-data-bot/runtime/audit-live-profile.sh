#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-staffanydatabot}"
EXPECTED_MODEL_PROVIDER="${EXPECTED_MODEL_PROVIDER:-anthropic}"
EXPECTED_MODEL_DEFAULT="${EXPECTED_MODEL_DEFAULT:-claude-sonnet-4-6}"
EXPECTED_PERSONALITY="${EXPECTED_PERSONALITY:-concise}"
EXPECTED_HEALTH_CRON_NAME="${EXPECTED_HEALTH_CRON_NAME:-staffanydatabot health check}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-staffanydatabot local cloud heartbeat}"
EXPECTED_DIGEST_CRON_NAME="${EXPECTED_DIGEST_CRON_NAME:-staffanydatabot high-priority release feature usage digest}"
EXPECT_DIGEST_CRON="${EXPECT_DIGEST_CRON:-0}"
EXPECTED_MCP_TOOLS="${EXPECTED_MCP_TOOLS:-4}"
EXPECTED_SLACK_CONTEXT_MCP_TOOLS="${EXPECTED_SLACK_CONTEXT_MCP_TOOLS:-2}"
EXPECTED_C360_MCP_TOOLS="${EXPECTED_C360_MCP_TOOLS:-1}"
EXPECTED_DATA_LEARNING_MCP_TOOLS="${EXPECTED_DATA_LEARNING_MCP_TOOLS:-4}"
EXPECTED_GOOGLE_SHEETS_MCP_TOOLS="${EXPECTED_GOOGLE_SHEETS_MCP_TOOLS:-2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
if [ -n "${HERMES_DATA_BOT_APP_ROOT:-}" ]; then
  APP_ROOT="$HERMES_DATA_BOT_APP_ROOT"
elif [ "$(basename "$SCRIPT_DIR")" = "runtime" ] && [ -f "$SCRIPT_DIR/../app.manifest.json" ]; then
  APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_ROOT="$PROFILE_DIR/source/hermes-data-bot"
fi
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"

PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

need_command hermes
need_command diff
need_command cmp

config_path="$(hermes -p "$PROFILE" config path 2>/dev/null)" || fail "hermes:config-path-failed"
[ -r "$config_path" ] || fail "hermes:config-unreadable"

cmp -s "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile-drift:soul"
diff -qr "$APP_ROOT/skills/staffany-data-bot" "$PROFILE_DIR/skills/staffany-data-bot" >/dev/null || fail "profile-drift:staffany-data-bot-skill"
diff -qr "$APP_ROOT/../hermes-shared/google-sheets-output/skills/staffany-google-sheets-output" "$PROFILE_DIR/skills/staffany-google-sheets-output" >/dev/null || fail "profile-drift:staffany-google-sheets-output-skill"
cmp -s "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/staffanydatabot-check-health.sh" || fail "profile-drift:health-script"
cmp -s "$APP_ROOT/runtime/check-cloud-heartbeat.sh" "$PROFILE_DIR/scripts/staffanydatabot-check-cloud-heartbeat.sh" || fail "profile-drift:cloud-heartbeat-script"
cmp -s "$APP_ROOT/runtime/staffanydatabot-cloud-doctor.sh" "$PROFILE_DIR/scripts/staffanydatabot-cloud-doctor.sh" || fail "profile-drift:cloud-doctor-script"
cmp -s "$APP_ROOT/runtime/mcp/staffany_slack_context_server.py" "$PROFILE_DIR/runtime/mcp/staffany_slack_context_server.py" || fail "profile-drift:staffany-slack-context-mcp"
cmp -s "$APP_ROOT/runtime/mcp/staffany_c360_server.py" "$PROFILE_DIR/runtime/mcp/staffany_c360_server.py" || fail "profile-drift:staffany-c360-mcp"
cmp -s "$APP_ROOT/runtime/mcp/staffany_data_learning_server.py" "$PROFILE_DIR/runtime/mcp/staffany_data_learning_server.py" || fail "profile-drift:staffany-data-learning-mcp"
cmp -s "$APP_ROOT/runtime/mcp/profile_env.py" "$PROFILE_DIR/runtime/mcp/profile_env.py" || fail "profile-drift:staffany-slack-context-profile-env"
cmp -s "$APP_ROOT/../hermes-shared/google-sheets-output/runtime/mcp/staffany_google_sheets_server.py" "$PROFILE_DIR/source/hermes-shared/google-sheets-output/runtime/mcp/staffany_google_sheets_server.py" || fail "profile-drift:staffany-google-sheets-mcp"
cmp -s "$APP_ROOT/../hermes-shared/google-sheets-output/runtime/mcp/google_oauth.py" "$PROFILE_DIR/source/hermes-shared/google-sheets-output/runtime/mcp/google_oauth.py" || fail "profile-drift:staffany-google-sheets-oauth-helper"

hermes_python="$HERMES_AGENT_DIR/venv/bin/python"
[ -x "$hermes_python" ] || fail "hermes:python-not-found"

config_check_out="$(mktemp)"
trap 'rm -f "$config_check_out"' EXIT

if ! "$hermes_python" - "$config_path" "$HERMES_AGENT_DIR" \
  "$EXPECTED_MODEL_PROVIDER" "$EXPECTED_MODEL_DEFAULT" "$EXPECTED_PERSONALITY" \
  >"$config_check_out" 2>&1 <<'PY'
import sys

config_path, hermes_agent_dir, expected_provider, expected_model, expected_personality = sys.argv[1:6]
sys.path.insert(0, hermes_agent_dir)

try:
    import yaml
    from gateway.display_config import resolve_display_setting
except Exception as exc:
    print(f"dependency:hermes-config-parser-failed:{exc.__class__.__name__}")
    raise SystemExit(1)

with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

model = config.get("model") or {}
if model.get("provider") != expected_provider:
    print("model:provider-drift")
    raise SystemExit(1)
if model.get("default") != expected_model:
    print("model:default-drift")
    raise SystemExit(1)

display = config.get("display") or {}
if display.get("personality") != expected_personality:
    print("display:personality-drift")
    raise SystemExit(1)
if display.get("interim_assistant_messages") is not False:
    print("slack-display:interim-assistant-messages-not-disabled")
    raise SystemExit(1)
if resolve_display_setting(config, "slack", "tool_progress") != "off":
    print("slack-display:tool-progress-not-off")
    raise SystemExit(1)
if resolve_display_setting(config, "slack", "streaming") is not False:
    print("slack-display:streaming-not-disabled")
    raise SystemExit(1)

if ((config.get("slack") or {}).get("reactions")) is not False:
    print("slack:reactions-not-disabled")
    raise SystemExit(1)
if ((config.get("kanban") or {}).get("dispatch_in_gateway")) is not False:
    print("kanban:dispatch-in-gateway-not-disabled")
    raise SystemExit(1)
if ((config.get("cron") or {}).get("max_parallel_jobs")) != 1:
    print("cron:max-parallel-jobs-not-one")
    raise SystemExit(1)
if ((config.get("security") or {}).get("redact_secrets")) is not True:
    print("security:redact-secrets-not-enabled")
    raise SystemExit(1)

server = ((config.get("mcp_servers") or {}).get("staffany_bigquery") or {})
tools = server.get("tools") or {}
allowlist = tools.get("include") or server.get("tool_allowlist") or []
expected_tools = [
    "list_dataset_ids",
    "list_table_ids",
    "get_table_info",
    "execute_sql_readonly",
]
if allowlist != expected_tools:
    print("mcp:staffany_bigquery-tool-allowlist-drift")
    raise SystemExit(1)
if tools.get("resources") is not False or tools.get("prompts") is not False:
    print("mcp:staffany_bigquery-resources-prompts-enabled")
    raise SystemExit(1)

slack_context = ((config.get("mcp_servers") or {}).get("staffany_slack_context") or {})
slack_context_tools = slack_context.get("tools") or {}
slack_context_allowlist = slack_context_tools.get("include") or slack_context.get("tool_allowlist") or []
expected_slack_context_tools = [
    "get_current_slack_thread_context",
    "get_selected_slack_thread_context",
]
if slack_context_allowlist != expected_slack_context_tools:
    print("mcp:staffany_slack_context-tool-allowlist-drift")
    raise SystemExit(1)
access_policy = slack_context.get("access_policy") or {}
if (
    access_policy.get("slack_posting") is not False
    or access_policy.get("workspace_search") is not False
    or access_policy.get("user_token_fallback") is not False
    or access_policy.get("slack_connector_fallback") is not False
):
    print("mcp:staffany_slack_context-unsafe-access-policy")
    raise SystemExit(1)

c360 = ((config.get("mcp_servers") or {}).get("staffany_c360") or {})
c360_allowlist = c360.get("tool_allowlist") or []
if c360_allowlist != ["list_current_customer_orgs"]:
    print("mcp:staffany_c360-tool-allowlist-drift")
    raise SystemExit(1)
c360_policy = c360.get("access_policy") or {}
if (
    c360_policy.get("custom_internal_header_only") is not True
    or c360_policy.get("browser_cookie") is not False
    or c360_policy.get("personal_customer360_session") is not False
    or c360_policy.get("write_operations") is not False
):
    print("mcp:staffany_c360-unsafe-access-policy")
    raise SystemExit(1)

google_sheets = ((config.get("mcp_servers") or {}).get("staffany_google_sheets") or {})
google_sheets_tools = google_sheets.get("tools") or {}
google_sheets_allowlist = google_sheets_tools.get("include") or google_sheets.get("tool_allowlist") or []
expected_google_sheets_tools = [
    "check_google_sheets_output_access",
    "create_spreadsheet_from_rows",
]
if google_sheets_allowlist != expected_google_sheets_tools:
    print("mcp:staffany_google_sheets-tool-allowlist-drift")
    raise SystemExit(1)
google_sheets_policy = google_sheets.get("access_policy") or {}
if (
    google_sheets_policy.get("account_email") != "team@staffany.com"
    or google_sheets_policy.get("service_account") is not False
    or google_sheets_policy.get("requires_output_folder_or_share_target") is not True
    or google_sheets_policy.get("create_spreadsheets") is not True
    or google_sheets_policy.get("edit_existing_spreadsheets") is not False
    or google_sheets_policy.get("read_arbitrary_spreadsheets") is not False
    or google_sheets_policy.get("user_token_fallback") is not False
    or google_sheets_policy.get("slack_connector_fallback") is not False
):
    print("mcp:staffany_google_sheets-unsafe-access-policy")
    raise SystemExit(1)

data_learning = ((config.get("mcp_servers") or {}).get("staffany_data_learning") or {})
data_learning_tools = data_learning.get("tools") or {}
data_learning_allowlist = data_learning_tools.get("include") or data_learning.get("tool_allowlist") or []
expected_data_learning_tools = [
    "record_staffany_data_lesson_candidate",
    "list_staffany_data_lesson_candidates",
    "read_staffany_data_lesson_candidate",
    "update_staffany_data_lesson_candidate_status",
]
if data_learning_allowlist != expected_data_learning_tools:
    print("mcp:staffany_data_learning-tool-allowlist-drift")
    raise SystemExit(1)
data_learning_policy = data_learning.get("access_policy") or {}
expected_learning_statuses = [
    "pending_review",
    "needs_more_evidence",
    "approved_for_repo_promotion",
    "rejected",
    "promoted",
]
if (
    data_learning_policy.get("record_status") != "pending_review"
    or data_learning_policy.get("valid_statuses") != expected_learning_statuses
    or data_learning_policy.get("review_status_tool") != "update_staffany_data_lesson_candidate_status"
    or data_learning_policy.get("review_approval_marker") != "human reviewed lesson"
    or data_learning_policy.get("auto_behavior_change") is not False
    or data_learning_policy.get("self_approval") is not False
    or data_learning_policy.get("honcho_used_as_source_of_truth") is not False
    or data_learning_policy.get("raw_slack_transcript_persistence") is not False
    or data_learning_policy.get("raw_query_row_persistence") is not False
    or data_learning_policy.get("sensitive_data_persistence") is not False
    or data_learning_policy.get("kanban_dispatch") is not False
    or data_learning_policy.get("persistent_goal_continuation") is not False
    or data_learning_policy.get("self_evolution_gepa") is not False
):
    print("mcp:staffany_data_learning-unsafe-access-policy")
    raise SystemExit(1)
PY
then
  fail "$(cat "$config_check_out")"
fi

cmp -s "$APP_ROOT/runtime/report-staffany-data-learning.py" "$PROFILE_DIR/scripts/staffanydatabot-report-data-learning.py" || fail "profile-drift:data-learning-report-script"

honcho_config="$PROFILE_DIR/honcho.json"
[ -r "$honcho_config" ] || fail "honcho:config-missing"
honcho_check_out="$(mktemp)"
trap 'rm -f "$config_check_out" "$honcho_check_out"' EXIT
if ! "$hermes_python" - "$honcho_config" >"$honcho_check_out" 2>&1 <<'PY'
import json
import sys

path = sys.argv[1]
try:
    config = json.load(open(path, "r", encoding="utf-8"))
except Exception as exc:
    print(f"honcho:config-unreadable:{exc.__class__.__name__}")
    raise SystemExit(1)
hosts = (config.get("hosts") or {}) if isinstance(config, dict) else {}
enabled_hosts = [host for host in hosts.values() if isinstance(host, dict) and host.get("enabled") is True]
if not enabled_hosts:
    print("honcho:config-no-enabled-host")
    raise SystemExit(1)
for host in enabled_hosts:
    if host.get("recallMode") != "tools":
        print("honcho:recall-mode-not-tools")
        raise SystemExit(1)
    if host.get("saveMessages") is not False:
        print("honcho:save-messages-not-false")
        raise SystemExit(1)
    if host.get("sessionStrategy") != "per-session":
        print("honcho:session-strategy-not-per-session")
        raise SystemExit(1)
    context_tokens = host.get("contextTokens")
    if context_tokens is not None and int(context_tokens) > 4000:
        print("honcho:context-tokens-unbounded")
        raise SystemExit(1)
PY
then
  fail "$(cat "$honcho_check_out")"
fi

cron_out="$(hermes -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_HEALTH_CRON_NAME" || fail "cron:health-check-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" || fail "cron:cloud-heartbeat-missing"
if [ "$EXPECT_DIGEST_CRON" = "1" ]; then
  printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_DIGEST_CRON_NAME" || fail "cron:feature-usage-digest-missing"
fi

mcp_out="$(hermes -p "$PROFILE" mcp test staffany_bigquery 2>&1)" || fail "mcp:staffany_bigquery-test-failed"
printf '%s\n' "$mcp_out" | grep -q "Tools discovered: $EXPECTED_MCP_TOOLS" || fail "mcp:staffany_bigquery-tool-count-unexpected"
slack_context_mcp_out="$(hermes -p "$PROFILE" mcp test staffany_slack_context 2>&1)" || fail "mcp:staffany_slack_context-test-failed"
printf '%s\n' "$slack_context_mcp_out" | grep -q "Tools discovered: $EXPECTED_SLACK_CONTEXT_MCP_TOOLS" || fail "mcp:staffany_slack_context-tool-count-unexpected"
c360_mcp_out="$(hermes -p "$PROFILE" mcp test staffany_c360 2>&1)" || fail "mcp:staffany_c360-test-failed"
printf '%s\n' "$c360_mcp_out" | grep -q "Tools discovered: $EXPECTED_C360_MCP_TOOLS" || fail "mcp:staffany_c360-tool-count-unexpected"
google_sheets_mcp_out="$(hermes -p "$PROFILE" mcp test staffany_google_sheets 2>&1)" || fail "mcp:staffany_google_sheets-test-failed"
printf '%s\n' "$google_sheets_mcp_out" | grep -q "Tools discovered: $EXPECTED_GOOGLE_SHEETS_MCP_TOOLS" || fail "mcp:staffany_google_sheets-tool-count-unexpected"
data_learning_mcp_out="$(hermes -p "$PROFILE" mcp test staffany_data_learning 2>&1)" || fail "mcp:staffany_data_learning-test-failed"
printf '%s\n' "$data_learning_mcp_out" | grep -q "Tools discovered: $EXPECTED_DATA_LEARNING_MCP_TOOLS" || fail "mcp:staffany_data_learning-tool-count-unexpected"

report_out="$("$PROFILE_DIR/scripts/staffanydatabot-report-data-learning.py" --stale-days 14 2>&1)" || fail "reviewed-learning:report-failed"
printf '%s\n' "$report_out" | grep -q "staffany_data_learning_review_report:ok" || fail "reviewed-learning:report-missing-ok"
printf '%s\n' "$report_out" | grep -q "lesson_candidates_content:omitted" || fail "reviewed-learning:report-may-print-content"

printf 'live-profile:audit-ok\n'
