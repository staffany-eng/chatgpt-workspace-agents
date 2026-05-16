#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-nurtureanysalesbot}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$HOME/.hermes/profiles/$PROFILE" ]; then
  export HERMES_HOME="$HOME/.hermes/profiles/$PROFILE"
fi

PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
GATEWAY_SERVICE_NAME="${NURTUREANY_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
EXPECTED_HEALTH_CRON_NAME="${EXPECTED_HEALTH_CRON_NAME:-nurtureanysalesbot health check}"
EXPECTED_AUDIT_CRON_NAME="${EXPECTED_AUDIT_CRON_NAME:-nurtureanysalesbot live profile audit}"
EXPECTED_SLACK_SOCKET_WATCHDOG_CRON_NAME="${EXPECTED_SLACK_SOCKET_WATCHDOG_CRON_NAME:-nurtureanysalesbot Slack socket watchdog}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-nurtureanysalesbot local cloud heartbeat}"
EXPECTED_TASK_REMINDER_CRON_NAME="${EXPECTED_TASK_REMINDER_CRON_NAME:-nurtureanysalesbot HubSpot task reminders}"
EXPECTED_TASK_REMINDER_EOD_CRON_NAME="${EXPECTED_TASK_REMINDER_EOD_CRON_NAME:-nurtureanysalesbot HubSpot task EOD catch-up}"
EXPECTED_SG_MY_WHATSAPP_BLITZ_CRON_NAME="${EXPECTED_SG_MY_WHATSAPP_BLITZ_CRON_NAME:-SG MY WhatsApp Morning Blitz Report}"
EXPECTED_ID_MORNING_WHATSAPP_BLITZ_CRON_NAME="${EXPECTED_ID_MORNING_WHATSAPP_BLITZ_CRON_NAME:-ID Morning WhatsApp Blitz Report}"
EXPECTED_ID_WHATSAPP_BLITZ_CRON_NAME="${EXPECTED_ID_WHATSAPP_BLITZ_CRON_NAME:-ID WhatsApp Morning Blitz Report}"
EXPECTED_CRON_TIMEZONE="${EXPECTED_CRON_TIMEZONE:-Asia/Singapore}"
EXPECT_CLOUD_HEARTBEAT_CRON="${EXPECT_CLOUD_HEARTBEAT_CRON:-1}"
EXPECT_ENABLED_CRON_COUNT="${EXPECT_ENABLED_CRON_COUNT:-9}"
EXPECT_SLACK_INTENT_TOOLS="${EXPECT_SLACK_INTENT_TOOLS:-5}"
EXPECT_HUBSPOT_TOOLS="${EXPECT_HUBSPOT_TOOLS:-56}"
EXPECT_PUBLIC_RESEARCH_TOOLS="${EXPECT_PUBLIC_RESEARCH_TOOLS:-2}"
EXPECT_PROSPEO_TOOLS="${EXPECT_PROSPEO_TOOLS:-4}"
EXPECT_CLOUD_DOCTOR="${EXPECT_CLOUD_DOCTOR:-1}"

HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -d "/run/user/$(id -u)" ]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

need_command python3

[ -d "$PROFILE_DIR" ] || fail "profile:not-found"

case "$(uname -s)" in
  Linux)
    need_command systemctl
    systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME" || fail "gateway:not-active"
    enabled="$(systemctl --user is-enabled "$GATEWAY_SERVICE_NAME" 2>/dev/null || true)"
    [ "$enabled" = "enabled" ] || fail "gateway:not-enabled"
    ;;
  *)
    fail "host:unsupported-os"
    ;;
esac

cron_jobs_path="$PROFILE_DIR/cron/jobs.json"
[ -r "$cron_jobs_path" ] || fail "cron:jobs-json-unreadable"
python3 - "$cron_jobs_path" \
  "$EXPECTED_HEALTH_CRON_NAME" \
  "$EXPECTED_AUDIT_CRON_NAME" \
  "$EXPECTED_SLACK_SOCKET_WATCHDOG_CRON_NAME" \
  "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" \
  "$EXPECTED_TASK_REMINDER_CRON_NAME" \
  "$EXPECTED_TASK_REMINDER_EOD_CRON_NAME" \
  "$EXPECTED_SG_MY_WHATSAPP_BLITZ_CRON_NAME" \
  "$EXPECTED_ID_MORNING_WHATSAPP_BLITZ_CRON_NAME" \
  "$EXPECTED_ID_WHATSAPP_BLITZ_CRON_NAME" \
  "$EXPECTED_CRON_TIMEZONE" \
  "$EXPECT_CLOUD_HEARTBEAT_CRON" \
  "$EXPECT_ENABLED_CRON_COUNT" <<'PY' || fail "cron:records-invalid"
import json
import sys

(
    jobs_path,
    health_name,
    audit_name,
    socket_name,
    heartbeat_name,
    task_reminder_name,
    task_reminder_eod_name,
    sg_my_blitz_name,
    id_morning_blitz_name,
    id_blitz_name,
    timezone,
    expect_heartbeat,
    expected_enabled_count,
) = sys.argv[1:14]

payload = json.loads(open(jobs_path, "r", encoding="utf-8").read())
jobs = payload.get("jobs") if isinstance(payload, dict) else payload
if not isinstance(jobs, list):
    print("cron:jobs-json-invalid")
    raise SystemExit(1)

by_name = {str(job.get("name") or ""): job for job in jobs if isinstance(job, dict)}

def schedule_expr(job):
    schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
    return schedule.get("expr")

def has_unsafe_send_message(prompt):
    return "send_message(target=" in prompt or "send_message(" in prompt

def require_job(name, *, expr, script=None, deliver=None, no_agent=None, require_timezone=True):
    job = by_name.get(name)
    if not job or job.get("enabled") is not True:
        print(f"cron:{name}:missing-or-disabled")
        raise SystemExit(1)
    if schedule_expr(job) != expr:
        print(f"cron:{name}:schedule-unexpected")
        raise SystemExit(1)
    if require_timezone and job.get("timezone") != timezone:
        print(f"cron:{name}:timezone-unexpected")
        raise SystemExit(1)
    if script is not None and job.get("script") != script:
        print(f"cron:{name}:script-unexpected")
        raise SystemExit(1)
    if deliver is not None and job.get("deliver") != deliver:
        print(f"cron:{name}:deliver-unexpected")
        raise SystemExit(1)
    if no_agent is not None and job.get("no_agent") is not no_agent:
        print(f"cron:{name}:mode-unexpected")
        raise SystemExit(1)
    if has_unsafe_send_message(str(job.get("prompt") or "")):
        print(f"cron:{name}:unsafe-send-message")
        raise SystemExit(1)

require_job(health_name, expr="0 1 * * 1-5", script="nurtureanysalesbot-check-health.sh")
require_job(audit_name, expr="15 1 * * 1-5", script="nurtureanysalesbot-audit-live-profile.sh")
require_job(socket_name, expr="*/5 * * * *", script="nurtureanysalesbot-check-slack-socket-health.sh")
if expect_heartbeat == "1":
    require_job(heartbeat_name, expr="*/15 * * * *", script="nurtureanysalesbot-check-cloud-heartbeat.sh")
require_job(task_reminder_name, expr="0 1 * * 1-5", script="nurtureany_sales_task_reminders.py", deliver="slack:#nurtureany-testing", no_agent=True)
require_job(task_reminder_eod_name, expr="0 9 * * 1-5", script="nurtureany_sales_task_reminders_eod.py", deliver="slack:#nurtureany-testing", no_agent=True)
require_job(sg_my_blitz_name, expr="35 2 * * 1-5", deliver="slack:C04HYF0NM8A", no_agent=False)
require_job(id_morning_blitz_name, expr="45 3 * * 1-5", deliver="slack:C0B2UGK4DB6", no_agent=False)
require_job(id_blitz_name, expr="35 3 * * 1-5", deliver="slack:C04MSJ1BGF9", no_agent=False)

enabled = [job for job in jobs if isinstance(job, dict) and job.get("enabled") is True]
enabled_recurring = [
    job
    for job in enabled
    if (job.get("schedule") if isinstance(job.get("schedule"), dict) else {}).get("kind") != "once"
]
if len(enabled_recurring) != int(expected_enabled_count):
    print(f"cron:enabled-recurring-count-unexpected:{len(enabled_recurring)}")
    raise SystemExit(1)

for job in jobs:
    name = str(job.get("name") or "")
    prompt = str(job.get("prompt") or "")
    if name.startswith("event-roi-") and job.get("enabled") is True:
        print(f"cron:{name}:event-roi-enabled")
        raise SystemExit(1)
    schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
    if job.get("enabled") is True and schedule.get("kind") != "once" and job.get("timezone") is None:
        print(f"cron:{name}:timezone-missing")
        raise SystemExit(1)
    if job.get("enabled") is True and has_unsafe_send_message(prompt):
        print(f"cron:{name}:unsafe-send-message")
        raise SystemExit(1)
PY

if [ "$EXPECT_CLOUD_DOCTOR" = "1" ]; then
  doctor="$PROFILE_DIR/scripts/nurtureanysalesbot-cloud-doctor.sh"
  [ -x "$doctor" ] || fail "cloud-doctor:missing"
  doctor_out="$(mktemp)"
  trap 'rm -f "$doctor_out"' EXIT
  "$doctor" >"$doctor_out" 2>&1 || fail "cloud-doctor:failed"
  grep -Fq "gateway_service:systemd:$GATEWAY_SERVICE_NAME:active=active:substate=running" "$doctor_out" || fail "cloud-doctor:gateway-unhealthy"
  grep -Fq "enabled_recurring=$EXPECT_ENABLED_CRON_COUNT:" "$doctor_out" || fail "cloud-doctor:cron-unhealthy"
  grep -Fq "missing_timezone=0:event_roi_enabled=0:unsafe_send_message=0" "$doctor_out" || fail "cloud-doctor:cron-unhealthy"
  grep -Fq "slack_allowlist:ok=true:" "$doctor_out" || fail "cloud-doctor:slack-allowlist-drift"
  for expected in \
    "mcp:slack_nurtureany:tools=$EXPECT_SLACK_INTENT_TOOLS" \
    "mcp:staffany_bigquery:tools=4" \
    "mcp:hubspot_nurtureany:tools=$EXPECT_HUBSPOT_TOOLS" \
    "mcp:google_calendar_nurtureany:tools=2" \
    "mcp:google_drive_nurtureany:tools=5" \
    "mcp:eazybe_nurtureany:tools=4" \
    "mcp:luma_nurtureany:tools=3" \
    "mcp:public_research_nurtureany:tools=$EXPECT_PUBLIC_RESEARCH_TOOLS" \
    "mcp:lusha_nurtureany:tools=4" \
    "mcp:prospeo_nurtureany:tools=$EXPECT_PROSPEO_TOOLS" \
    "mcp:exa_nurtureany:tools=1" \
    "mcp:near_me_nurtureany:tools=6"; do
    grep -Fq "$expected" "$doctor_out" || fail "cloud-doctor:${expected}:missing"
  done
fi
