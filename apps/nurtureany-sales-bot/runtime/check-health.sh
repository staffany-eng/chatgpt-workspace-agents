#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-nurtureanysalesbot}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$HOME/.hermes/profiles/$PROFILE" ]; then
  export HERMES_HOME="$HOME/.hermes/profiles/$PROFILE"
fi
EXPECT_GATEWAY="${EXPECT_GATEWAY:-1}"
EXPECT_MODEL_AUTH="${EXPECT_MODEL_AUTH:-1}"
EXPECT_MODEL_PROVIDER="${EXPECT_MODEL_PROVIDER:-anthropic}"
EXPECT_MODEL_DEFAULT="${EXPECT_MODEL_DEFAULT:-claude-sonnet-4-6}"
EXPECT_STAFFANY_BIGQUERY_TOOLS="${EXPECT_STAFFANY_BIGQUERY_TOOLS:-4}"
EXPECT_HUBSPOT_TOOLS="${EXPECT_HUBSPOT_TOOLS:-27}"
EXPECT_GOOGLE_CALENDAR_TOOLS="${EXPECT_GOOGLE_CALENDAR_TOOLS:-2}"
EXPECT_GOOGLE_DRIVE_TOOLS="${EXPECT_GOOGLE_DRIVE_TOOLS:-3}"
EXPECT_LUMA_TOOLS="${EXPECT_LUMA_TOOLS:-3}"
EXPECT_LUSHA_TOOLS="${EXPECT_LUSHA_TOOLS:-3}"
EXPECT_EXA_TOOLS="${EXPECT_EXA_TOOLS:-1}"
EXPECT_NEAR_ME_TOOLS="${EXPECT_NEAR_ME_TOOLS:-6}"

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

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

need_command hermes

config_path="$(hermes -p "$PROFILE" config path 2>/dev/null)" || fail "hermes:config-path-failed"
[ -r "$config_path" ] || fail "hermes:config-unreadable"
profile_dir="$(dirname "$config_path")"
hermes_python="$HERMES_AGENT_DIR/venv/bin/python"
[ -x "$hermes_python" ] || fail "hermes:python-not-found"

hermes -p "$PROFILE" config check >/dev/null 2>&1 || fail "hermes:config-check-failed"

config_check_out="$tmp_dir/config-check.out"
if ! "$hermes_python" - "$config_path" "$HERMES_AGENT_DIR" "$EXPECT_MODEL_PROVIDER" "$EXPECT_MODEL_DEFAULT" >"$config_check_out" 2>&1 <<'PY'
import os
import sys

config_path, hermes_agent_dir, expected_provider, expected_model = sys.argv[1:5]
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
    print("model:provider-unexpected")
    raise SystemExit(1)
if model.get("default") != expected_model:
    print("model:default-unexpected")
    raise SystemExit(1)

display = config.get("display") or {}
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
if ((config.get("security") or {}).get("redact_secrets")) is not True:
    print("security:redact-secrets-not-enabled")
    raise SystemExit(1)

cwd = str((config.get("terminal") or {}).get("cwd") or "")
if "/.codex/worktrees/" in cwd:
    print("terminal:cwd-points-at-codex-worktree")
    raise SystemExit(1)

nurtureany = config.get("nurtureany") or {}
if ((nurtureany.get("honcho") or {}).get("enabled")) is not False:
    print("honcho:nurtureany-not-disabled")
    raise SystemExit(1)

expected_servers = {
    "staffany_bigquery": ["list_dataset_ids", "list_table_ids", "get_table_info", "execute_sql_readonly"],
    "hubspot_nurtureany": [
        "list_inbound_threads",
        "get_inbound_thread_context",
        "list_marketing_campaigns",
        "get_campaign_assets",
        "get_marketing_touch_context",
        "list_my_target_accounts",
        "list_team_target_accounts",
        "audit_hubspot_owner_roster",
        "audit_priority_account_coverage",
        "build_sales_metric_actuals_query",
        "build_friday_sales_review",
        "get_account_context",
        "build_pre_demo_game_plans",
        "list_sales_followup_tasks",
        "check_account_followup_status",
        "check_event_followup_status",
        "find_target_accounts_by_luma_match_keys",
        "score_nurture_accounts",
        "find_contact_gaps",
        "find_t90_renewal_gaps",
        "generate_free_search_tasks",
        "review_public_enrichment_evidence",
        "find_target_accounts_by_luma_match_keys",
        "scan_drive_event_photos",
        "propose_photo_people_matches",
        "plan_event_photo_followup",
        "draft_nurture_message",
        "plan_hubspot_writeback",
    ],
    "google_calendar_nurtureany": ["list_google_calendar_events", "audit_google_calendar_meeting_quality"],
    "google_drive_nurtureany": [
        "list_drive_folder_images",
        "extract_drive_image_clues",
        "read_indonesia_event_registration_attendance",
    ],
    "luma_nurtureany": ["list_luma_events", "get_luma_event_match_keys", "get_luma_event_context"],
    "lusha_nurtureany": ["search_lusha_decision_maker_candidates", "reveal_lusha_contact_details", "get_lusha_credit_usage"],
    "exa_nurtureany": ["search_exa_people_candidates"],
    "near_me_nurtureany": [
        "resolve_known_area_for_near_me",
        "build_near_me_outlet_matches_query",
        "refresh_google_places_for_known_area",
        "build_near_me_c360_customer_query",
        "prepare_near_me_seed_review_candidates",
        "merge_near_me_sources",
    ],
}

servers = config.get("mcp_servers") or {}
for name, expected_tools in expected_servers.items():
    server = servers.get(name) or {}
    if server.get("enabled") is not True:
        print(f"mcp:{name}:not-enabled")
        raise SystemExit(1)
    tools = server.get("tools") or {}
    allowlist = tools.get("include") or server.get("tool_allowlist") or []
    if allowlist != expected_tools:
        print(f"mcp:{name}:tool-allowlist-drift")
        raise SystemExit(1)
    if tools and (tools.get("resources") is not False or tools.get("prompts") is not False):
        print(f"mcp:{name}:resources-prompts-enabled")
        raise SystemExit(1)

near_me_env = ((servers.get("near_me_nurtureany") or {}).get("env") or {})
if "GOOGLE_PLACES_API_KEY" not in near_me_env:
    print("mcp:near_me_nurtureany:missing-google-places-env")
    raise SystemExit(1)
PY
then
  fail "$(cat "$config_check_out")"
fi

drive_token="$profile_dir/google-drive-token.json"
if [ -e "$drive_token" ]; then
  perms="$(stat -f '%Lp' "$drive_token" 2>/dev/null || stat -c '%a' "$drive_token" 2>/dev/null || true)"
  [ "$perms" = "600" ] || fail "google-drive:token-permissions-not-600"
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
  hermes -p "$PROFILE" auth status "$EXPECT_MODEL_PROVIDER" >"$auth_out" 2>&1 || fail "model-auth:$EXPECT_MODEL_PROVIDER-status-failed"
  grep -q "$EXPECT_MODEL_PROVIDER: logged in" "$auth_out" || fail "model-auth:$EXPECT_MODEL_PROVIDER-not-logged-in"
fi

memory_out="$tmp_dir/memory.out"
hermes -p "$PROFILE" memory status >"$memory_out" 2>&1 || fail "memory:status-failed"
if grep -Eq 'Provider:[[:space:]]+honcho|Status:[[:space:]]+available.*honcho' "$memory_out"; then
  fail "memory:honcho-active"
fi

mcp_test() {
  local name="$1"
  local count="$2"
  local out="$tmp_dir/mcp-$name.out"
  hermes -p "$PROFILE" mcp test "$name" >"$out" 2>&1 || fail "mcp:$name-test-failed"
  grep -q "Tools discovered: $count" "$out" || fail "mcp:$name-tool-count-unexpected"
}

mcp_test staffany_bigquery "$EXPECT_STAFFANY_BIGQUERY_TOOLS"
mcp_test hubspot_nurtureany "$EXPECT_HUBSPOT_TOOLS"
mcp_test google_calendar_nurtureany "$EXPECT_GOOGLE_CALENDAR_TOOLS"
mcp_test google_drive_nurtureany "$EXPECT_GOOGLE_DRIVE_TOOLS"
mcp_test luma_nurtureany "$EXPECT_LUMA_TOOLS"
mcp_test lusha_nurtureany "$EXPECT_LUSHA_TOOLS"
mcp_test exa_nurtureany "$EXPECT_EXA_TOOLS"
mcp_test near_me_nurtureany "$EXPECT_NEAR_ME_TOOLS"
