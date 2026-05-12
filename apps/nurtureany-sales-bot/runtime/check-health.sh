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
EXPECT_HUBSPOT_TOOLS="${EXPECT_HUBSPOT_TOOLS:-33}"
EXPECT_GOOGLE_CALENDAR_TOOLS="${EXPECT_GOOGLE_CALENDAR_TOOLS:-2}"
EXPECT_GOOGLE_DRIVE_TOOLS="${EXPECT_GOOGLE_DRIVE_TOOLS:-5}"
EXPECT_EAZYBE_TOOLS="${EXPECT_EAZYBE_TOOLS:-4}"
EXPECT_LUMA_TOOLS="${EXPECT_LUMA_TOOLS:-3}"
EXPECT_LUSHA_TOOLS="${EXPECT_LUSHA_TOOLS:-3}"
EXPECT_EXA_TOOLS="${EXPECT_EXA_TOOLS:-1}"
EXPECT_PUBLIC_RESEARCH_TOOLS="${EXPECT_PUBLIC_RESEARCH_TOOLS:-1}"
EXPECT_NEAR_ME_TOOLS="${EXPECT_NEAR_ME_TOOLS:-6}"
EXPECT_C360_SALES_PACKET="${EXPECT_C360_SALES_PACKET:-1}"
C360_SALES_PACKET_SMOKE_COMPANY_ID="${C360_SALES_PACKET_SMOKE_COMPANY_ID:-9003704457}"
C360_SALES_PACKET_SMOKE_COMPANY_NAME="${C360_SALES_PACKET_SMOKE_COMPANY_NAME:-Stripes Australia}"

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
        "audit_inbound_sla",
        "list_marketing_campaigns",
        "get_campaign_assets",
        "get_campaign_social_effectiveness",
        "get_marketing_touch_context",
        "get_marketing_campaign_attribution",
        "list_my_target_accounts",
        "list_team_target_accounts",
        "audit_hubspot_owner_roster",
        "audit_priority_account_coverage",
        "build_sales_metric_actuals_query",
        "build_friday_sales_review",
        "build_manager_chase_plan",
        "get_account_context",
        "build_pre_demo_game_plans",
        "list_active_deals_missing_next_meeting",
        "list_sales_followup_tasks",
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
        "draft_nurture_message",
        "plan_hubspot_writeback",
        "build_daily_nurture_plan",
    ],
    "google_calendar_nurtureany": ["list_google_calendar_events", "audit_google_calendar_meeting_quality"],
    "google_drive_nurtureany": [
        "list_drive_folder_images",
        "read_google_slides_deck",
        "extract_drive_image_clues",
        "read_nurture_material_registry",
        "read_indonesia_event_registration_attendance",
    ],
    "eazybe_nurtureany": [
        "preview_eazybe_template_messages",
        "send_approved_eazybe_messages",
        "check_eazybe_send_status",
        "build_daily_nurture_reminder",
    ],
    "luma_nurtureany": ["list_luma_events", "get_luma_event_match_keys", "get_luma_event_context"],
    "public_research_nurtureany": ["research_public_company_signals"],
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
policy_emails: list[str] = []
for entry in raw_policy.get("admins", []):
    email = entry_email(entry)
    if email and email not in disabled:
        policy_emails.append(email)
for entry in raw_policy.get("managers", []):
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
PY
then
  fail "$(cat "$slack_allowlist_out")"
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
env -u HERMES_HOME hermes -p "$PROFILE" memory status >"$memory_out" 2>&1 || fail "memory:status-failed"
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
mcp_test eazybe_nurtureany "$EXPECT_EAZYBE_TOOLS"
mcp_test luma_nurtureany "$EXPECT_LUMA_TOOLS"
mcp_test public_research_nurtureany "$EXPECT_PUBLIC_RESEARCH_TOOLS"
mcp_test lusha_nurtureany "$EXPECT_LUSHA_TOOLS"
mcp_test exa_nurtureany "$EXPECT_EXA_TOOLS"
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
