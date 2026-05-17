#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-psmopsbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
GATEWAY_SERVICE_NAME="${PSM_OPS_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
HERMES_PYTHON="${HERMES_PYTHON:-$HERMES_AGENT_DIR/venv/bin/python}"
PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

if [ -r "$PROFILE_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$PROFILE_DIR/.env"
  set +a
fi

fail() {
  printf '%s\n' "$1"
  exit 1
}

if command -v systemctl >/dev/null 2>&1; then
  active="$(systemctl --user is-active "$GATEWAY_SERVICE_NAME" 2>/dev/null || true)"
  [ "$active" = "active" ] || fail "gateway_service:not-active:$GATEWAY_SERVICE_NAME"
fi

if command -v hermes >/dev/null 2>&1; then
  for server in psm_jira psm_c360 psm_google_calendar; do
    out="$(hermes -p "$PROFILE" mcp test "$server" 2>&1 || true)"
    case "$server" in
      psm_jira) expected=24 ;;
      psm_c360) expected=3 ;;
      psm_google_calendar) expected=1 ;;
    esac
    count="$(printf '%s\n' "$out" | sed -nE 's/.*Tools discovered: ([0-9]+).*/\1/p' | tail -1)"
    [ "$count" = "$expected" ] || fail "mcp:$server:tools=${count:-unavailable}:expected=$expected"
  done
else
  fail "hermes:not-found"
fi

config_path="$(hermes -p "$PROFILE" config path 2>/dev/null || true)"
if [ -n "$config_path" ] && [ -r "$config_path" ]; then
  grep -Eq 'provider: *"?anthropic"?' "$config_path" || fail "model:provider-not-anthropic"
  grep -q 'claude-sonnet-4-6' "$config_path" || fail "model:default-not-claude-sonnet-4-6"
  grep -q 'require_mention: *true' "$config_path" || fail "slack:require-mention-not-enabled"
  if [ -n "${SLACK_ALLOWED_CHANNELS:-}" ]; then
    fail "slack:allowed-channels-should-be-empty-for-open-channel-mode"
  fi
  grep -q 'max_parallel_jobs: *1' "$config_path" || fail "cron:max_parallel_jobs-not-1"
  [ -x "$HERMES_PYTHON" ] || fail "hermes:python-not-found"
  "$HERMES_PYTHON" - "$config_path" "$HERMES_AGENT_DIR" <<'PY'
import sys

config_path, hermes_agent_dir = sys.argv[1:3]
sys.path.insert(0, hermes_agent_dir)

try:
    import yaml
    from gateway.display_config import resolve_display_setting
except Exception as exc:
    print(f"dependency:hermes-config-parser-failed:{exc.__class__.__name__}")
    raise SystemExit(1)

with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

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

title_generation = ((config.get("auxiliary") or {}).get("title_generation") or {})
if title_generation.get("provider") != "anthropic":
    print("auxiliary:title-generation-provider-not-anthropic")
    raise SystemExit(1)
if title_generation.get("model") != "claude-haiku-4-5":
    print("auxiliary:title-generation-model-not-haiku")
    raise SystemExit(1)
try:
    title_timeout = float(title_generation.get("timeout"))
except (TypeError, ValueError):
    print("auxiliary:title-generation-timeout-invalid")
    raise SystemExit(1)
if title_timeout > 10:
    print("auxiliary:title-generation-timeout-too-high")
    raise SystemExit(1)
PY
fi

for key in \
  JIRA_BASE_URL \
  JIRA_EMAIL \
  JIRA_API_TOKEN \
  SLACK_BOT_TOKEN \
  PSM_OPS_JIRA_SERVICE_DESK_ID \
  PSM_OPS_ROI_JIRA_PROJECT_KEY \
  PSM_OPS_ROI_JIRA_SERVICE_DESK_ID \
  PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID \
  CUSTOMER360_INTERNAL_API_TOKEN \
  GOOGLE_CALENDAR_TOKEN_FILE \
  GOOGLE_CALENDAR_CLIENT_SECRET_FILE; do
  value="${!key:-}"
  [ -n "$value" ] || fail "env:$key:missing"
done

[ "${GOOGLE_CALENDAR_ACCOUNT_EMAIL:-team@staffany.com}" = "team@staffany.com" ] || fail "google_calendar:account-not-team"
[ -r "${GOOGLE_CALENDAR_TOKEN_FILE:-}" ] || fail "google_calendar:token-file-unreadable"
[ -r "${GOOGLE_CALENDAR_CLIENT_SECRET_FILE:-}" ] || fail "google_calendar:client-secret-file-unreadable"

python3 - <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
query = urllib.parse.urlencode({"limit": "20"})
request = urllib.request.Request(
    f"https://slack.com/api/users.list?{query}",
    headers={"Authorization": f"Bearer {token}"},
)
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    print("slack:users-list-unavailable")
    sys.exit(1)
if not payload.get("ok"):
    print(f"slack:users-list:{payload.get('error', 'unknown_error')}")
    sys.exit(1)
members = payload.get("members") or []
if not any(((member.get("profile") or {}).get("email")) for member in members if isinstance(member, dict)):
    print("slack:users-list-email-scope-missing")
    sys.exit(1)
central_channel = os.environ.get("PSM_OPS_CENTRAL_SLACK_CHANNEL_ID", "").strip()
if central_channel:
    query = urllib.parse.urlencode({"channel": central_channel})
    request = urllib.request.Request(
        f"https://slack.com/api/conversations.info?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        print("slack:central-channel-info-unavailable")
        sys.exit(1)
    if not payload.get("ok"):
        print(f"slack:central-channel-info:{payload.get('error', 'unknown_error')}")
        sys.exit(1)
    channel = payload.get("channel") or {}
    if channel.get("is_member") is False:
        print("slack:central-channel-bot-not-member")
        sys.exit(1)
public_join_smoke_channel = os.environ.get("PSM_OPS_PUBLIC_CHANNEL_JOIN_SMOKE_CHANNEL_ID", "").strip() or central_channel
if public_join_smoke_channel:
    data = urllib.parse.urlencode({"channel": public_join_smoke_channel}).encode("utf-8")
    request = urllib.request.Request(
        "https://slack.com/api/conversations.join",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        print("slack:public-channel-join-smoke-unavailable")
        sys.exit(1)
    if not payload.get("ok"):
        error = payload.get("error", "unknown_error")
        if error == "missing_scope":
            print("slack:public-channel-join-scope-missing")
        else:
            print(f"slack:public-channel-join-smoke:{error}")
        sys.exit(1)
PY

if [ "${PSM_OPS_JIRA_MODE:-}" != "thin_poc" ]; then
  for key in \
    PSM_OPS_ACCESS_POLICY_PATH \
    PSM_OPS_JIRA_FIELD_REMINDER_AT; do
    value="${!key:-}"
    [ -n "$value" ] || fail "env:$key:missing"
  done
fi

cron_jobs="$PROFILE_DIR/cron/jobs.json"
if [ -r "$cron_jobs" ] && command -v python3 >/dev/null 2>&1; then
python3 - "$cron_jobs" <<'PY'
import json
import os
import sys

payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
jobs = payload.get("jobs") if isinstance(payload, dict) else payload
enabled = [job for job in jobs if isinstance(job, dict) and job.get("enabled") is True]
names = {str(job.get("name") or "") for job in enabled}
missing = [
    name
    for name in ["psmopsbot due-date reminders", "psmopsbot assignment hygiene", "psmopsbot due-date eod catch-up", "psmopsbot roi tracker sync"]
    if name not in names
]
scripts = {str(job.get("name") or ""): job for job in enabled}
for name, expected_script in {
    "psmopsbot due-date reminders": "psm_ops_due_date_reminders.py",
    "psmopsbot assignment hygiene": "psm_ops_pco_assignment_hygiene.py",
    "psmopsbot due-date eod catch-up": "psm_ops_due_date_reminders_eod.py",
    "psmopsbot roi tracker sync": "psm_ops_roi_tracker_sync.py",
}.items():
    job = scripts.get(name)
    if not job:
        continue
    if job.get("script") != expected_script:
        print(f"cron:{name}:script-unexpected")
        sys.exit(1)
    if job.get("no_agent") is not True:
        print(f"cron:{name}:mode-unexpected")
        sys.exit(1)
if os.environ.get("PSM_OPS_ADOPTION_METRICS_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
    if "psmopsbot adoption digest" not in names:
        missing.append("psmopsbot adoption digest")
if missing:
    print(f"cron:missing:{','.join(missing)}")
    sys.exit(1)
PY
fi

hook_dir="$PROFILE_DIR/hooks/psm-ops-adoption-telemetry"
if [ -d "$hook_dir" ]; then
  [ -r "$hook_dir/HOOK.yaml" ] || fail "hook:adoption:missing-HOOK.yaml"
  [ -r "$hook_dir/handler.py" ] || fail "hook:adoption:missing-handler.py"
elif [ "${PSM_OPS_ADOPTION_METRICS_ENABLED:-}" = "true" ] || [ "${PSM_OPS_ADOPTION_METRICS_ENABLED:-}" = "1" ]; then
  fail "hook:adoption:missing"
fi
