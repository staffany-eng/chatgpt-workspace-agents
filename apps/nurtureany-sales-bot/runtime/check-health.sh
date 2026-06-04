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
EXPECT_SLACK_INTENT_TOOLS="${EXPECT_SLACK_INTENT_TOOLS:-5}"
EXPECT_STAFFANY_BIGQUERY_TOOLS="${EXPECT_STAFFANY_BIGQUERY_TOOLS:-4}"
EXPECT_HUBSPOT_TOOLS="${EXPECT_HUBSPOT_TOOLS:-65}"
EXPECT_AIRCALL_TOOLS="${EXPECT_AIRCALL_TOOLS:-4}"
EXPECT_DEMO_SOURCES_TOOLS="${EXPECT_DEMO_SOURCES_TOOLS:-1}"
EXPECT_GOOGLE_CALENDAR_TOOLS="${EXPECT_GOOGLE_CALENDAR_TOOLS:-2}"
EXPECT_GOOGLE_DRIVE_TOOLS="${EXPECT_GOOGLE_DRIVE_TOOLS:-5}"
EXPECT_GOOGLE_SHEETS_TOOLS="${EXPECT_GOOGLE_SHEETS_TOOLS:-2}"
EXPECT_EAZYBE_TOOLS="${EXPECT_EAZYBE_TOOLS:-4}"
EXPECT_LUMA_TOOLS="${EXPECT_LUMA_TOOLS:-3}"
EXPECT_LUSHA_TOOLS="${EXPECT_LUSHA_TOOLS:-5}"
EXPECT_PROSPEO_TOOLS="${EXPECT_PROSPEO_TOOLS:-4}"
EXPECT_EXA_TOOLS="${EXPECT_EXA_TOOLS:-1}"
EXPECT_APIFY_TOOLS="${EXPECT_APIFY_TOOLS:-7}"
EXPECT_PUBLIC_RESEARCH_TOOLS="${EXPECT_PUBLIC_RESEARCH_TOOLS:-2}"
EXPECT_NEAR_ME_TOOLS="${EXPECT_NEAR_ME_TOOLS:-6}"
EXPECT_C360_SALES_PACKET="${EXPECT_C360_SALES_PACKET:-1}"
MCP_TEST_TIMEOUT_SECONDS="${MCP_TEST_TIMEOUT_SECONDS:-45}"
C360_SALES_PACKET_SMOKE_COMPANY_ID="${C360_SALES_PACKET_SMOKE_COMPANY_ID:-9003704457}"
C360_SALES_PACKET_SMOKE_COMPANY_NAME="${C360_SALES_PACKET_SMOKE_COMPANY_NAME:-Stripes Australia}"
GATEWAY_SERVICE_NAME="${NURTUREANY_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
GATEWAY_LAUNCHD_LABEL="${NURTUREANY_GATEWAY_LAUNCHD_LABEL:-ai.hermes.gateway-$PROFILE}"
EXPECT_SOLE_NURTUREANY_GATEWAY="${EXPECT_SOLE_NURTUREANY_GATEWAY:-1}"
if [ -z "${NURTUREANY_DUPLICATE_PROFILE:-}" ]; then
  if [ "$PROFILE" = "nae2e" ]; then
    NURTUREANY_DUPLICATE_PROFILE="nurtureanysalesbot"
  else
    NURTUREANY_DUPLICATE_PROFILE="nae2e"
  fi
fi
NURTUREANY_DUPLICATE_LAUNCHD_LABEL="${NURTUREANY_DUPLICATE_LAUNCHD_LABEL:-ai.hermes.gateway-$NURTUREANY_DUPLICATE_PROFILE}"

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

check_gateway_service() {
  local gateway_out="$tmp_dir/gateway.out"
  case "$(uname -s)" in
    Linux)
      need_command systemctl
      if systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME"; then
        return 0
      fi
      systemctl --user show "$GATEWAY_SERVICE_NAME" --property=ActiveState --property=SubState --no-pager >"$gateway_out" 2>&1 || true
      fail "gateway:not-running"
      ;;
    Darwin)
      need_command launchctl
      if launchctl print "gui/$(id -u)/$GATEWAY_LAUNCHD_LABEL" >"$gateway_out" 2>&1; then
        grep -Eq 'state = running|state = active' "$gateway_out" || fail "gateway:not-running"
        return 0
      fi
      hermes -p "$PROFILE" gateway status >"$gateway_out" 2>&1 || fail "gateway:status-failed"
      if grep -Eq '✗|not loaded|not running' "$gateway_out"; then
        fail "gateway:not-running"
      fi
      ;;
    *)
      hermes -p "$PROFILE" gateway status >"$gateway_out" 2>&1 || fail "gateway:status-failed"
      if grep -Eq '✗|not loaded|not running' "$gateway_out"; then
        fail "gateway:not-running"
      fi
      ;;
  esac
}

process_commands() {
  if [ "$(uname -s)" = "Darwin" ]; then
    ps -axo command= 2>/dev/null || true
  else
    ps -eo command= 2>/dev/null || true
  fi
}

count_gateway_processes() {
  local profile="$1"
  process_commands | awk -v profile="$profile" '
    index($0, "hermes_cli.main") &&
    index($0, "--profile " profile " gateway run") {
      count += 1
    }
    END { print count + 0 }
  '
}

check_single_nurtureany_gateway() {
  [ "$EXPECT_SOLE_NURTUREANY_GATEWAY" = "1" ] || return 0

  local duplicate_count
  duplicate_count="$(count_gateway_processes "$NURTUREANY_DUPLICATE_PROFILE")"
  if [ "$duplicate_count" -gt 0 ]; then
    fail "gateway:duplicate-profile-running:$NURTUREANY_DUPLICATE_PROFILE"
  fi

  if [ "$(uname -s)" = "Darwin" ] && command -v launchctl >/dev/null 2>&1; then
    if launchctl print "gui/$(id -u)/$NURTUREANY_DUPLICATE_LAUNCHD_LABEL" >/dev/null 2>&1; then
      fail "gateway:duplicate-launchd-loaded:$NURTUREANY_DUPLICATE_LAUNCHD_LABEL"
    fi
  fi

  if [ "$PROFILE" = "nurtureanysalesbot" ]; then
    local nurtureany_count
    nurtureany_count="$(count_gateway_processes "nurtureanysalesbot")"
    if [ "$nurtureany_count" -gt 1 ]; then
      fail "gateway:multiple-nurtureany-processes:$nurtureany_count"
    fi
  fi
}

file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true
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

if ((config.get("slack") or {}).get("reactions")) is not True:
    print("slack:reactions-not-enabled")
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
reviewed_lessons = nurtureany.get("reviewed_lessons") or {}
if reviewed_lessons.get("enabled") is not True:
    print("reviewed-lessons:not-enabled")
    raise SystemExit(1)
if reviewed_lessons.get("record_status") != "pending_review":
    print("reviewed-lessons:record-status-unexpected")
    raise SystemExit(1)
if reviewed_lessons.get("auto_behavior_change") is not False or reviewed_lessons.get("honcho_used") is not False:
    print("reviewed-lessons:unsafe-runtime-learning-enabled")
    raise SystemExit(1)

quick_autorun = nurtureany.get("quick_autorun") or {}
if quick_autorun.get("enabled") is not True:
    print("quick-autorun:not-enabled")
    raise SystemExit(1)
if int(quick_autorun.get("max_expected_seconds") or 0) != 60:
    print("quick-autorun:max-expected-seconds-unexpected")
    raise SystemExit(1)
if int(quick_autorun.get("max_context_messages") or 0) != 10:
    print("quick-autorun:max-context-messages-unexpected")
    raise SystemExit(1)
if int(quick_autorun.get("max_context_lookback_minutes") or 0) != 30:
    print("quick-autorun:max-context-lookback-unexpected")
    raise SystemExit(1)
if quick_autorun.get("slack_context_tool") != "read_recent_slack_intent_context":
    print("quick-autorun:slack-context-tool-unexpected")
    raise SystemExit(1)
if quick_autorun.get("slack_context_token_env") != "SLACK_BOT_TOKEN":
    print("quick-autorun:slack-context-token-env-unexpected")
    raise SystemExit(1)
if quick_autorun.get("raw_transcript_persistence") is not False:
    print("quick-autorun:raw-transcript-persistence-enabled")
    raise SystemExit(1)
if quick_autorun.get("no_user_token_fallback") is not True or quick_autorun.get("no_slack_connector_fallback") is not True:
    print("quick-autorun:unsafe-fallback-enabled")
    raise SystemExit(1)

expected_servers = {
    "slack_nurtureany": [
        "read_recent_slack_intent_context",
        "get_current_slack_thread_context",
        "get_selected_slack_thread_context",
        "extract_inbound_lead_alerts",
        "audit_standup_down_accountability",
    ],
    "staffany_bigquery": ["list_dataset_ids", "list_table_ids", "get_table_info", "execute_sql_readonly"],
    "hubspot_nurtureany": [
        "list_inbound_threads",
        "get_inbound_thread_context",
        "audit_inbound_sla",
        "resolve_inbound_slack_alerts_to_hubspot",
        "list_marketing_campaigns",
        "get_campaign_assets",
        "get_campaign_social_effectiveness",
        "get_marketing_touch_context",
        "get_marketing_campaign_attribution",
        "list_my_target_accounts",
        "list_team_target_accounts",
        "find_event_sourcing_target_accounts",
        "audit_hubspot_owner_roster",
        "resolve_nurture_scope",
        "resolve_sales_owners",
        "list_sales_call_events",
        "summarize_sales_call_stats",
        "audit_priority_account_coverage",
        "build_sales_metric_actuals_query",
        "build_hubspot_revenue_funnel_metrics",
        "build_ae_coaching_audit",
        "audit_owner_whatsapp_kns_window",
        "prepare_sales_navigator_decision_maker_queue",
        "build_friday_sales_review",
        "build_manager_chase_plan",
        "get_account_context",
        "build_pre_demo_game_plans",
        "find_sales_case_studies",
        "build_singapore_lead_enrichment_plan",
        "resolve_company_enrichment_target",
        "create_company_enrichment_artifact",
        "update_company_enrichment_artifact",
        "read_company_enrichment_artifact",
        "summarize_company_enrichment_artifact",
        "list_active_deals_missing_next_meeting",
        "list_sales_followup_tasks",
        "list_due_hubspot_sales_task_reminders",
        "build_sales_whatsapp_window_report",
        "count_owner_whatsapp_sent_today",
        "save_sales_whatsapp_window_report_schedule",
        "run_sales_whatsapp_window_report_schedule",
        "post_generated_sales_report",
        "check_account_followup_status",
        "check_event_followup_status",
        "score_nurture_accounts",
        "find_contact_gaps",
        "find_t90_renewal_gaps",
        "generate_free_search_tasks",
        "review_public_enrichment_evidence",
        "find_target_accounts_by_luma_match_keys",
        "scan_drive_event_photos",
        "propose_photo_people_matches",
        "plan_event_photo_followup",
        "preview_hubspot_sales_task",
        "create_approved_hubspot_sales_task",
        "preview_hubspot_task_update",
        "apply_approved_hubspot_task_update",
        "record_nurtureany_operation_checkpoint",
        "read_nurtureany_operation_ledger",
        "record_nurtureany_lesson_candidate",
        "list_nurtureany_lesson_candidates",
        "read_nurtureany_lesson_candidate",
        "draft_nurture_message",
        "plan_hubspot_writeback",
    ],
    "aircall_nurtureany": ["find_aircall_calls", "resolve_aircall_call_for_coaching", "transcribe_aircall_recording", "analyze_aircall_call_coaching"],
    "demo_sources_nurtureany": ["extract_demo_transcript_evidence"],
    "google_calendar_nurtureany": ["list_google_calendar_events", "audit_google_calendar_meeting_quality"],
    "google_drive_nurtureany": [
        "list_drive_folder_images",
        "read_google_slides_deck",
        "extract_drive_image_clues",
        "read_nurture_material_registry",
        "read_indonesia_event_registration_attendance",
    ],
    "google_sheets_nurtureany": ["preview_analysis_sheet_export", "apply_analysis_sheet_export"],
    "eazybe_nurtureany": [
        "preview_eazybe_template_messages",
        "send_approved_eazybe_messages",
        "check_eazybe_send_status",
    ],
    "luma_nurtureany": ["list_luma_events", "get_luma_event_match_keys", "get_luma_event_context"],
    "public_research_nurtureany": ["research_public_company_signals", "find_brand_parent_candidates"],
    "lusha_nurtureany": ["search_lusha_decision_maker_candidates", "search_lusha_candidates_by_linkedin_urls", "search_lusha_candidates_by_names", "reveal_lusha_contact_details", "get_lusha_credit_usage"],
    "prospeo_nurtureany": ["search_prospeo_decision_maker_candidates", "search_prospeo_candidates_by_linkedin_urls", "reveal_prospeo_contact_details", "get_prospeo_credit_usage"],
    "exa_nurtureany": ["search_exa_people_candidates"],
    "apify_nurtureany": [
        "search-actors",
        "fetch-actor-details",
        "call-actor",
        "get-actor-run",
        "get-actor-output",
        "search-apify-docs",
        "fetch-apify-docs",
    ],
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
apify_auth = ((servers.get("apify_nurtureany") or {}).get("auth_metadata") or {})
if apify_auth.get("env") != "APIFY_TOKEN":
    print("mcp:apify_nurtureany:missing-apify-token-env")
    raise SystemExit(1)
apify_env = ((servers.get("apify_nurtureany") or {}).get("env") or {})
apify_headers = ((servers.get("apify_nurtureany") or {}).get("headers") or {})
if "APIFY_TOKEN" not in apify_env or "APIFY_TOKEN" not in str(apify_headers.get("Authorization") or ""):
    print("mcp:apify_nurtureany:missing-apify-token-header")
    raise SystemExit(1)
PY
then
  fail "$(cat "$config_check_out")"
fi

drive_token="$profile_dir/google-drive-token.json"
if [ -e "$drive_token" ]; then
  perms="$(file_mode "$drive_token")"
  [ "$perms" = "600" ] || fail "google-drive:token-permissions-not-600"
fi

slack_allowlist_out="$tmp_dir/slack-allowlist.out"
if ! "$hermes_python" - "$config_path" "$profile_dir" "$HERMES_AGENT_DIR" >"$slack_allowlist_out" 2>&1 <<'PY'
import json
import os
import sys
import time
import urllib.parse
import urllib.request

config_path, profile_dir, hermes_agent_dir = sys.argv[1:4]
sys.path.insert(0, hermes_agent_dir)

try:
    import yaml
except Exception:
    print("dependency:yaml-not-available")
    raise SystemExit(1)


def read_profile_env(profile_dir: str) -> dict[str, str]:
    env_path = os.path.join(profile_dir, ".env")
    values: dict[str, str] = {}
    if not os.path.exists(env_path):
        return values
    with open(env_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            values[key] = value
    return values


def entry_email(entry):
    if isinstance(entry, str):
        return entry.strip().lower()
    if isinstance(entry, dict):
        return str(entry.get("email") or entry.get("slack_email") or "").strip().lower()
    return ""


def disabled_emails(raw_policy: dict) -> set[str]:
    disabled: set[str] = set()
    for key in ("disabled", "unclassified"):
        for entry in raw_policy.get(key, []):
            email = entry_email(entry)
            if not email and isinstance(entry, dict):
                email = str(entry.get("hubspot_owner_email") or "").strip().lower()
            if email:
                disabled.add(email)
    return disabled


with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

profile_env = read_profile_env(profile_dir)
slack_token = os.environ.get("SLACK_BOT_TOKEN") or profile_env.get("SLACK_BOT_TOKEN") or ""
allowed_users_raw = os.environ.get("SLACK_ALLOWED_USERS") or profile_env.get("SLACK_ALLOWED_USERS") or ""
if not slack_token:
    print("slack-allowlist:bot-token-missing")
    raise SystemExit(1)
if not allowed_users_raw:
    print("slack-allowlist:allowed-users-missing")
    raise SystemExit(1)

servers = config.get("mcp_servers") or {}
hubspot_env = ((servers.get("hubspot_nurtureany") or {}).get("env") or {})
policy_path = (
    os.environ.get("NURTUREANY_ACCESS_POLICY_PATH")
    or profile_env.get("NURTUREANY_ACCESS_POLICY_PATH")
    or hubspot_env.get("NURTUREANY_ACCESS_POLICY_PATH")
    or ""
)
if not policy_path:
    print("slack-allowlist:access-policy-path-missing")
    raise SystemExit(1)
if not os.path.exists(policy_path):
    print("slack-allowlist:access-policy-not-found")
    raise SystemExit(1)

with open(policy_path, "r", encoding="utf-8") as handle:
    raw_policy = json.load(handle)

disabled = disabled_emails(raw_policy)
policy_emails: list[str] = [
    "eugene@staffany.com",
    "kaiyi@staffany.com",
    "kai.yi@staffany.com",
    "leekai.yi@staffany.com",
    "kerren.fong@staffany.com",
    "sarah@staffany.com",
    "sarah.ayutania@staffany.com",
]
for entry in raw_policy.get("admins", []):
    email = entry_email(entry)
    if email and email not in disabled:
        policy_emails.append(email)
for entry in raw_policy.get("managers", []):
    email = entry_email(entry)
    if email and email not in disabled:
        policy_emails.append(email)
for key in ("partnerships_viewers", "event_operators", "regional_event_operators"):
    for entry in raw_policy.get(key, []):
        if isinstance(entry, dict) and entry.get("active") is False:
            continue
        email = entry_email(entry)
        if email and email not in disabled:
            policy_emails.append(email)
for entry in raw_policy.get("sales_reps", []):
    if not isinstance(entry, dict) or entry.get("active") is False:
        continue
    slack_email = str(entry.get("slack_email") or entry.get("email") or "").strip().lower()
    owner_email = str(entry.get("hubspot_owner_email") or "").strip().lower()
    if slack_email and slack_email not in disabled and owner_email not in disabled:
        policy_emails.append(slack_email)
for entry in raw_policy.get("partnerships_viewers", []):
    if not isinstance(entry, dict) or entry.get("active") is False:
        continue
    email = entry_email(entry)
    if email and email not in disabled:
        policy_emails.append(email)
policy_emails = [email for email in policy_emails if email and email not in disabled]

allowed_ids = {value.strip() for value in allowed_users_raw.split(",") if value.strip()}
if not allowed_ids:
    print("slack-allowlist:allowed-users-empty")
    raise SystemExit(1)

resolved_ids: set[str] = set()
for email in sorted(set(policy_emails)):
    url = "https://slack.com/api/users.lookupByEmail?" + urllib.parse.urlencode({"email": email})
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {slack_token}"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        print("slack-allowlist:user-lookup-failed")
        raise SystemExit(1)
    if not data.get("ok"):
        if data.get("error") == "users_not_found":
            continue
        print("slack-allowlist:user-lookup-error")
        raise SystemExit(1)
    user = data.get("user") or {}
    if user.get("deleted") or user.get("is_bot"):
        continue
    user_id = str(user.get("id") or "").strip()
    if user_id:
        resolved_ids.add(user_id)
    time.sleep(0.05)

if not resolved_ids:
    print("slack-allowlist:no-resolved-policy-users")
    raise SystemExit(1)

if resolved_ids - allowed_ids:
    print("slack-allowlist:missing-policy-users")
    raise SystemExit(1)
if allowed_ids - resolved_ids:
    print("slack-allowlist:extra-users")
    raise SystemExit(1)

intent_channels_raw = (
    os.environ.get("NURTUREANY_SLACK_INTENT_CHANNEL_IDS")
    or profile_env.get("NURTUREANY_SLACK_INTENT_CHANNEL_IDS")
    or os.environ.get("SLACK_HOME_CHANNEL")
    or profile_env.get("SLACK_HOME_CHANNEL")
    or ""
)
intent_channels = [value.strip() for value in intent_channels_raw.split(",") if value.strip()]
if not intent_channels:
    print("slack-intent:configured-channel-ids-missing")
    raise SystemExit(1)
thread_channels_raw = (
    os.environ.get("NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS")
    or profile_env.get("NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS")
    or intent_channels_raw
)
thread_channels = [value.strip() for value in thread_channels_raw.split(",") if value.strip()]
if not thread_channels:
    print("slack-thread-context:configured-channel-ids-missing")
    raise SystemExit(1)
inbound_channels_raw = (
    os.environ.get("NURTUREANY_INBOUND_ALERT_CHANNEL_IDS")
    or profile_env.get("NURTUREANY_INBOUND_ALERT_CHANNEL_IDS")
    or ""
)
inbound_channels = [value.strip() for value in inbound_channels_raw.split(",") if value.strip()]
if not inbound_channels:
    print("slack-inbound-alert:configured-channel-ids-missing")
    raise SystemExit(1)


def slack_get(method: str, params: dict[str, str]) -> dict:
    url = f"https://slack.com/api/{method}?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {slack_token}"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        print("slack-intent:request-failed")
        raise SystemExit(1)


auth_data = slack_get("auth.test", {})
if not auth_data.get("ok"):
    print("slack-intent:auth-test-failed")
    raise SystemExit(1)

channel_id = intent_channels[0]
history_data = slack_get("conversations.history", {"channel": channel_id, "limit": "1"})
if not history_data.get("ok"):
    error = str(history_data.get("error") or "unknown")
    if error == "missing_scope":
        print("slack-intent:missing-conversations-history-scope")
    elif error in {"not_in_channel", "channel_not_found"}:
        print("slack-intent:channel-not-found-or-not-in-channel")
    else:
        print("slack-intent:history-check-failed")
    raise SystemExit(1)

messages = history_data.get("messages") or []
if messages:
    message_ts = str((messages[0] or {}).get("ts") or "")
    replies_data = slack_get("conversations.replies", {"channel": channel_id, "ts": message_ts, "limit": "1"})
    if not replies_data.get("ok"):
        print("slack-intent:replies-check-failed")
        raise SystemExit(1)
    permalink_data = slack_get("chat.getPermalink", {"channel": channel_id, "message_ts": message_ts})
    if not permalink_data.get("ok"):
        print("slack-intent:permalink-check-failed")
        raise SystemExit(1)

thread_channel_id = thread_channels[0]
thread_history_data = slack_get("conversations.history", {"channel": thread_channel_id, "limit": "1"})
if not thread_history_data.get("ok"):
    error = str(thread_history_data.get("error") or "unknown")
    if error == "not_in_channel":
        join_data = slack_get("conversations.join", {"channel": thread_channel_id})
        if not join_data.get("ok"):
            print("slack-thread-context:join-failed")
            raise SystemExit(1)
        thread_history_data = slack_get("conversations.history", {"channel": thread_channel_id, "limit": "1"})
        if not thread_history_data.get("ok"):
            print("slack-thread-context:history-after-join-failed")
            raise SystemExit(1)
    elif error == "missing_scope":
        print("slack-thread-context:missing-conversations-history-scope")
        raise SystemExit(1)
    elif error == "channel_not_found":
        print("slack-thread-context:channel-not-found-or-not-in-channel")
        raise SystemExit(1)
    else:
        print("slack-thread-context:history-check-failed")
        raise SystemExit(1)

thread_messages = thread_history_data.get("messages") or []
if thread_messages:
    thread_message_ts = str((thread_messages[0] or {}).get("ts") or "")
    thread_replies_data = slack_get("conversations.replies", {"channel": thread_channel_id, "ts": thread_message_ts, "limit": "1"})
    if not thread_replies_data.get("ok"):
        print("slack-thread-context:replies-check-failed")
        raise SystemExit(1)

standup_channels_raw = (
    os.environ.get("NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS")
    or profile_env.get("NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS")
    or ""
)
standup_channels = [value.strip() for value in standup_channels_raw.split(",") if value.strip()]
if not standup_channels:
    print("slack-standup:configured-channel-ids-missing")
    raise SystemExit(1)

standup_channel_id = standup_channels[0]
standup_info = slack_get("conversations.info", {"channel": standup_channel_id})
if not standup_info.get("ok"):
    print("slack-standup:channel-info-failed")
    raise SystemExit(1)
channel_info = standup_info.get("channel") or {}
if not channel_info.get("is_channel") or channel_info.get("is_private"):
    print("slack-standup:channel-not-public")
    raise SystemExit(1)

standup_members_data = slack_get("conversations.members", {"channel": standup_channel_id, "limit": "1"})
if not standup_members_data.get("ok"):
    error = str(standup_members_data.get("error") or "unknown")
    if error == "not_in_channel":
        join_data = slack_get("conversations.join", {"channel": standup_channel_id})
        if not join_data.get("ok"):
            print("slack-standup:join-failed")
            raise SystemExit(1)
        standup_members_data = slack_get("conversations.members", {"channel": standup_channel_id, "limit": "1"})
        if not standup_members_data.get("ok"):
            print("slack-standup:members-after-join-failed")
            raise SystemExit(1)
    elif error == "missing_scope":
        print("slack-standup:missing-conversations-members-scope")
        raise SystemExit(1)
    else:
        print("slack-standup:members-check-failed")
        raise SystemExit(1)

standup_history_data = slack_get("conversations.history", {"channel": standup_channel_id, "limit": "1"})
if not standup_history_data.get("ok"):
    error = str(standup_history_data.get("error") or "unknown")
    if error == "not_in_channel":
        join_data = slack_get("conversations.join", {"channel": standup_channel_id})
        if not join_data.get("ok"):
            print("slack-standup:join-failed")
            raise SystemExit(1)
        standup_history_data = slack_get("conversations.history", {"channel": standup_channel_id, "limit": "1"})
        if not standup_history_data.get("ok"):
            print("slack-standup:history-after-join-failed")
            raise SystemExit(1)
    elif error == "missing_scope":
        print("slack-standup:missing-conversations-history-scope")
        raise SystemExit(1)
    elif error == "channel_not_found":
        print("slack-standup:channel-not-found-or-not-in-channel")
        raise SystemExit(1)
    else:
        print("slack-standup:history-check-failed")
        raise SystemExit(1)

standup_messages = standup_history_data.get("messages") or []
if standup_messages:
    standup_message_ts = str((standup_messages[0] or {}).get("ts") or "")
    standup_permalink_data = slack_get("chat.getPermalink", {"channel": standup_channel_id, "message_ts": standup_message_ts})
    if not standup_permalink_data.get("ok"):
        print("slack-standup:permalink-check-failed")
        raise SystemExit(1)
    first_member = str((standup_members_data.get("members") or [""])[0] or "")
    if first_member:
        user_info_data = slack_get("users.info", {"user": first_member})
        if not user_info_data.get("ok"):
            print("slack-standup:users-info-check-failed")
            raise SystemExit(1)
PY
then
  fail "$(cat "$slack_allowlist_out")"
fi

if [ "$EXPECT_GATEWAY" = "1" ]; then
  check_gateway_service
  check_single_nurtureany_gateway
fi

if [ "$EXPECT_MODEL_AUTH" = "1" ]; then
  auth_out="$tmp_dir/auth.out"
  hermes -p "$PROFILE" auth status "$EXPECT_MODEL_PROVIDER" >"$auth_out" 2>&1 || fail "model-auth:$EXPECT_MODEL_PROVIDER-status-failed"
  grep -q "$EXPECT_MODEL_PROVIDER: logged in" "$auth_out" || fail "model-auth:$EXPECT_MODEL_PROVIDER-not-logged-in"
fi

memory_out="$tmp_dir/memory.out"
env -u HERMES_HOME hermes -p "$PROFILE" memory status >"$memory_out" 2>&1 || fail "memory:status-failed"
if grep -Eq 'Provider:[[:space:]]+honcho|Status:[[:space:]]+available.*honcho' "$memory_out"; then
  fail "memory:honcho-active"
fi

mcp_test() {
  local name="$1"
  local count="$2"
  local out="$tmp_dir/mcp-$name.out"
  if ! "$hermes_python" - "$PROFILE" "$name" "$out" "$MCP_TEST_TIMEOUT_SECONDS" <<'PY'
import subprocess
import sys

profile, name, output_path, timeout_seconds = sys.argv[1:5]
try:
    timeout = float(timeout_seconds)
except ValueError:
    print("mcp:timeout-config-invalid")
    raise SystemExit(1)

with open(output_path, "w", encoding="utf-8") as handle:
    try:
        completed = subprocess.run(
            ["hermes", "-p", profile, "mcp", "test", name],
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        handle.write(f"mcp:{name}:timeout-after-{timeout_seconds}s\n")
        raise SystemExit(124)

raise SystemExit(completed.returncode)
PY
  then
    grep -q "mcp:$name:timeout-after-" "$out" && fail "mcp:$name-test-timeout"
    fail "mcp:$name-test-failed"
  fi
  grep -q "Tools discovered: $count" "$out" || fail "mcp:$name-tool-count-unexpected"
}

mcp_test slack_nurtureany "$EXPECT_SLACK_INTENT_TOOLS"
mcp_test staffany_bigquery "$EXPECT_STAFFANY_BIGQUERY_TOOLS"
mcp_test hubspot_nurtureany "$EXPECT_HUBSPOT_TOOLS"
mcp_test aircall_nurtureany "$EXPECT_AIRCALL_TOOLS"
mcp_test demo_sources_nurtureany "$EXPECT_DEMO_SOURCES_TOOLS"
mcp_test google_calendar_nurtureany "$EXPECT_GOOGLE_CALENDAR_TOOLS"
mcp_test google_drive_nurtureany "$EXPECT_GOOGLE_DRIVE_TOOLS"
mcp_test google_sheets_nurtureany "$EXPECT_GOOGLE_SHEETS_TOOLS"
mcp_test eazybe_nurtureany "$EXPECT_EAZYBE_TOOLS"
mcp_test luma_nurtureany "$EXPECT_LUMA_TOOLS"
mcp_test public_research_nurtureany "$EXPECT_PUBLIC_RESEARCH_TOOLS"
mcp_test lusha_nurtureany "$EXPECT_LUSHA_TOOLS"
mcp_test prospeo_nurtureany "$EXPECT_PROSPEO_TOOLS"
mcp_test exa_nurtureany "$EXPECT_EXA_TOOLS"
mcp_test apify_nurtureany "$EXPECT_APIFY_TOOLS"
mcp_test near_me_nurtureany "$EXPECT_NEAR_ME_TOOLS"

if [ "$EXPECT_C360_SALES_PACKET" = "1" ]; then
  c360_packet_out="$tmp_dir/c360-sales-packet.out"
  if ! "$hermes_python" - "$config_path" "$profile_dir" "$C360_SALES_PACKET_SMOKE_COMPANY_ID" "$C360_SALES_PACKET_SMOKE_COMPANY_NAME" >"$c360_packet_out" 2>&1 <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

config_path, profile_dir, company_id, company_name = sys.argv[1:5]
DEFAULT_C360_SALES_PACKET_URL_TEMPLATE = "https://customer-360-qv4r5xkisq-as.a.run.app/api/companies/{customer360_route_key}/sales-packet"

try:
    import yaml
except Exception:
    print("dependency:yaml-not-available")
    raise SystemExit(1)


def read_profile_env(profile_dir: str) -> dict[str, str]:
    env_path = os.path.join(profile_dir, ".env")
    values: dict[str, str] = {}
    if not os.path.exists(env_path):
        return values
    with open(env_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            values[key] = value
    return values


def configured_value(key: str, profile_env: dict[str, str], hubspot_env: dict[str, str]) -> str:
    for source in (os.environ, profile_env, hubspot_env):
        raw = str(source.get(key) or "").strip()
        if raw and not (raw.startswith("${") and raw.endswith("}")):
            return raw
    return ""


with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

profile_env = read_profile_env(profile_dir)
servers = config.get("mcp_servers") or {}
hubspot_env = ((servers.get("hubspot_nurtureany") or {}).get("env") or {})

token = configured_value("NURTUREANY_C360_INTERNAL_API_TOKEN", profile_env, hubspot_env)
if not token:
    print("c360-sales-packet:token-missing")
    raise SystemExit(1)

template = (
    configured_value("NURTUREANY_C360_SALES_PACKET_URL_TEMPLATE", profile_env, hubspot_env)
    or DEFAULT_C360_SALES_PACKET_URL_TEMPLATE
)
customer_key = str(company_id or "").strip()
if not customer_key:
    print("c360-sales-packet:company-id-missing")
    raise SystemExit(1)

values = {
    "customer360_route_key": urllib.parse.quote(customer_key, safe=""),
    "hubspot_company_id": urllib.parse.quote(customer_key, safe=""),
    "hubspot_numeric_company_id": urllib.parse.quote(customer_key, safe=""),
    "company_name": urllib.parse.quote(str(company_name or "").strip(), safe=""),
}
try:
    url = template.format(**values)
except Exception:
    print("c360-sales-packet:url-template-invalid")
    raise SystemExit(1)

request = urllib.request.Request(
    url,
    headers={
        "authorization": f"Bearer {token}",
        "accept": "application/json",
        "user-agent": "StaffAny-NurtureAny/1.0",
    },
    method="GET",
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
except urllib.error.HTTPError as error:
    print(f"c360-sales-packet:http-{error.code}")
    raise SystemExit(1)
except Exception:
    print("c360-sales-packet:request-failed")
    raise SystemExit(1)

try:
    payload = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    print("c360-sales-packet:invalid-json")
    raise SystemExit(1)

if not isinstance(payload, dict):
    print("c360-sales-packet:invalid-payload")
    raise SystemExit(1)

status = str(payload.get("status") or "ok").strip().lower()
if status != "ok":
    print("c360-sales-packet:status-not-ok")
    raise SystemExit(1)

data = payload.get("data")
if not isinstance(data, dict):
    print("c360-sales-packet:payload-missing-data")
    raise SystemExit(1)
if not str(data.get("segment") or "").strip():
    print("c360-sales-packet:payload-missing-segment")
    raise SystemExit(1)
PY
  then
    fail "$(cat "$c360_packet_out")"
  fi
fi
