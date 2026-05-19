#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-staffanydatabot}"
HONCHO_HEALTH_URL="${HONCHO_HEALTH_URL:-http://localhost:8000/health}"
EXPECT_HONCHO="${EXPECT_HONCHO:-1}"
EXPECT_GATEWAY="${EXPECT_GATEWAY:-1}"
EXPECT_MCP_TOOLS="${EXPECT_MCP_TOOLS:-4}"
EXPECT_SLACK_CONTEXT_MCP_TOOLS="${EXPECT_SLACK_CONTEXT_MCP_TOOLS:-2}"
EXPECT_C360_MCP_TOOLS="${EXPECT_C360_MCP_TOOLS:-1}"
EXPECT_DATA_LEARNING_MCP_TOOLS="${EXPECT_DATA_LEARNING_MCP_TOOLS:-4}"
EXPECT_GOOGLE_SHEETS_MCP_TOOLS="${EXPECT_GOOGLE_SHEETS_MCP_TOOLS:-2}"
EXPECT_MODEL_AUTH="${EXPECT_MODEL_AUTH:-1}"
EXPECT_MODEL_PROVIDER="${EXPECT_MODEL_PROVIDER:-anthropic}"
EXPECT_MODEL_DEFAULT="${EXPECT_MODEL_DEFAULT:-claude-sonnet-4-6}"
CHECK_GATEWAY_AUTH_LOGS="${CHECK_GATEWAY_AUTH_LOGS:-1}"

PATH="$HOME/.local/bin:$HOME/.hermes/hermes-agent:$PATH"
export PATH

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

need_command hermes

config_path="$(hermes -p "$PROFILE" config path 2>/dev/null)" || fail "hermes:config-path-failed"
[ -r "$config_path" ] || fail "hermes:config-unreadable"
hermes_agent_dir="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
hermes_python="$hermes_agent_dir/venv/bin/python"
[ -x "$hermes_python" ] || fail "hermes:python-not-found"

grep -Eq 'redact_secrets:[[:space:]]*true' "$config_path" || fail "security:redact_secrets-not-enabled"

config_check_out="$tmp_dir/config-check.out"
if ! "$hermes_python" - "$config_path" "$hermes_agent_dir" >"$config_check_out" 2>&1 <<'PY'
import sys

config_path, hermes_agent_dir = sys.argv[1], sys.argv[2]
sys.path.insert(0, hermes_agent_dir)

try:
    import yaml
    from gateway.display_config import resolve_display_setting
except Exception as exc:
    print(f"dependency:hermes-config-parser-failed:{exc.__class__.__name__}")
    raise SystemExit(1)

with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

if resolve_display_setting(config, "slack", "tool_progress") != "off":
    print("slack-display:tool-progress-not-off")
    raise SystemExit(1)

if resolve_display_setting(config, "slack", "streaming") is not False:
    print("slack-display:streaming-not-disabled")
    raise SystemExit(1)

if (config.get("display") or {}).get("interim_assistant_messages") is not False:
    print("slack-display:interim-assistant-messages-not-disabled")
    raise SystemExit(1)

if ((config.get("slack") or {}).get("reactions")) is not False:
    print("slack:reactions-not-disabled")
    raise SystemExit(1)

if ((config.get("kanban") or {}).get("dispatch_in_gateway")) is not False:
    print("kanban:dispatch-in-gateway-not-disabled")
    raise SystemExit(1)

cron = config.get("cron") or {}
if cron.get("max_parallel_jobs") != 1:
    print("cron:max-parallel-jobs-not-one")
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
if access_policy.get("slack_posting") is not False or access_policy.get("workspace_search") is not False:
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

model_check_out="$tmp_dir/model-check.out"
if ! "$hermes_python" - "$config_path" "$EXPECT_MODEL_PROVIDER" "$EXPECT_MODEL_DEFAULT" >"$model_check_out" 2>&1 <<'PY'
import sys
import yaml

config_path, expected_provider, expected_model = sys.argv[1:4]
with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

model = config.get("model") or {}
if model.get("provider") != expected_provider:
    print("model:provider-unexpected")
    raise SystemExit(1)
if model.get("default") != expected_model:
    print("model:default-unexpected")
    raise SystemExit(1)
PY
then
  fail "$(cat "$model_check_out")"
fi

if [ "$EXPECT_GATEWAY" = "1" ]; then
  gateway_out="$tmp_dir/gateway.out"
  hermes -p "$PROFILE" gateway status >"$gateway_out" 2>&1 || fail "gateway:status-failed"
  if grep -Eq '✗|not loaded|not running|failed' "$gateway_out"; then
    fail "gateway:not-running"
  fi
fi

if [ "$EXPECT_MODEL_AUTH" = "1" ]; then
  auth_out="$tmp_dir/auth.out"
  if ! hermes -p "$PROFILE" auth status "$EXPECT_MODEL_PROVIDER" >"$auth_out" 2>&1; then
    fail "model-auth:$EXPECT_MODEL_PROVIDER-status-failed"
  fi
  grep -q "$EXPECT_MODEL_PROVIDER: logged in" "$auth_out" || fail "model-auth:$EXPECT_MODEL_PROVIDER-not-logged-in"

  if [ "$EXPECT_MODEL_PROVIDER" = "openai-codex" ]; then
    auth_list_out="$tmp_dir/auth-list.out"
    if ! hermes -p "$PROFILE" auth list >"$auth_list_out" 2>&1; then
      fail "model-auth:credential-list-failed"
    fi
    if awk '
      /^openai-codex[[:space:]]/ { in_provider=1; next }
      /^[^[:space:]].*\([0-9]+ credentials\):/ && in_provider { in_provider=0 }
      in_provider && /auth failed|token_invalidated|invalidated|re-auth/ { bad=1 }
      END { exit bad ? 0 : 1 }
    ' "$auth_list_out"; then
      fail "model-auth:openai-codex-credential-invalidated"
    fi
  fi
fi

if [ "$CHECK_GATEWAY_AUTH_LOGS" = "1" ] && [ "$EXPECT_MODEL_PROVIDER" = "openai-codex" ] && command -v systemctl >/dev/null 2>&1 && command -v journalctl >/dev/null 2>&1; then
  svc="hermes-gateway-$PROFILE.service"
  active_since="$(systemctl --user show "$svc" -p ActiveEnterTimestamp --value 2>/dev/null || true)"
  if [ -n "$active_since" ]; then
    logs_out="$tmp_dir/gateway-auth.log"
    journalctl --user -u "$svc" --since "$active_since" --no-pager >"$logs_out" 2>/dev/null || true
    if grep -Eq 'token_invalidated|No Codex credentials|AuthenticationError|HTTP 401' "$logs_out"; then
      fail "model-auth:recent-gateway-auth-error"
    fi
  fi
fi

mcp_out="$tmp_dir/mcp.out"
if ! hermes -p "$PROFILE" mcp test staffany_bigquery >"$mcp_out" 2>&1; then
  fail "mcp:staffany_bigquery-test-failed"
fi
grep -q "Tools discovered: $EXPECT_MCP_TOOLS" "$mcp_out" || fail "mcp:staffany_bigquery-tool-count-unexpected"

slack_context_mcp_out="$tmp_dir/slack-context-mcp.out"
if ! hermes -p "$PROFILE" mcp test staffany_slack_context >"$slack_context_mcp_out" 2>&1; then
  fail "mcp:staffany_slack_context-test-failed"
fi
grep -q "Tools discovered: $EXPECT_SLACK_CONTEXT_MCP_TOOLS" "$slack_context_mcp_out" || fail "mcp:staffany_slack_context-tool-count-unexpected"

c360_mcp_out="$tmp_dir/c360-mcp.out"
if ! hermes -p "$PROFILE" mcp test staffany_c360 >"$c360_mcp_out" 2>&1; then
  fail "mcp:staffany_c360-test-failed"
fi
grep -q "Tools discovered: $EXPECT_C360_MCP_TOOLS" "$c360_mcp_out" || fail "mcp:staffany_c360-tool-count-unexpected"

google_sheets_mcp_out="$tmp_dir/google-sheets-mcp.out"
if ! hermes -p "$PROFILE" mcp test staffany_google_sheets >"$google_sheets_mcp_out" 2>&1; then
  fail "mcp:staffany_google_sheets-test-failed"
fi
grep -q "Tools discovered: $EXPECT_GOOGLE_SHEETS_MCP_TOOLS" "$google_sheets_mcp_out" || fail "mcp:staffany_google_sheets-tool-count-unexpected"

data_learning_mcp_out="$tmp_dir/data-learning-mcp.out"
if ! hermes -p "$PROFILE" mcp test staffany_data_learning >"$data_learning_mcp_out" 2>&1; then
  fail "mcp:staffany_data_learning-test-failed"
fi
grep -q "Tools discovered: $EXPECT_DATA_LEARNING_MCP_TOOLS" "$data_learning_mcp_out" || fail "mcp:staffany_data_learning-tool-count-unexpected"

profile_dir="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
report_script="$profile_dir/scripts/staffanydatabot-report-data-learning.py"
[ -x "$report_script" ] || fail "reviewed-learning:report-script-missing"
report_out="$tmp_dir/data-learning-report.out"
if ! "$report_script" --stale-days 14 >"$report_out" 2>&1; then
  fail "reviewed-learning:report-failed"
fi
grep -q "staffany_data_learning_review_report:ok" "$report_out" || fail "reviewed-learning:report-missing-ok"
grep -q "lesson_candidates_content:omitted" "$report_out" || fail "reviewed-learning:report-may-print-content"

if [ "$EXPECT_HONCHO" = "1" ]; then
  need_command curl
  curl -fsS "$HONCHO_HEALTH_URL" >/dev/null || fail "honcho:health-failed"

  honcho_config="$profile_dir/honcho.json"
  [ -r "$honcho_config" ] || fail "honcho:config-missing"
  honcho_check_out="$tmp_dir/honcho-config.out"
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

  memory_out="$tmp_dir/memory.out"
  if ! hermes -p "$PROFILE" memory status >"$memory_out" 2>&1; then
    fail "memory:status-failed"
  fi
  grep -Eq 'Provider:[[:space:]]+honcho' "$memory_out" || fail "memory:honcho-not-active"
  grep -Eq 'Status:[[:space:]]+available' "$memory_out" || fail "memory:honcho-not-available"
fi
