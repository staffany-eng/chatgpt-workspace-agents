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
EXPECTED_CRON_TIMEZONE="${EXPECTED_CRON_TIMEZONE:-Asia/Singapore}"
EXPECT_CLOUD_HEARTBEAT_CRON="${EXPECT_CLOUD_HEARTBEAT_CRON:-1}"
EXPECT_ENABLED_CRON_COUNT="${EXPECT_ENABLED_CRON_COUNT:-4}"
EXPECT_HUBSPOT_TOOLS="${EXPECT_HUBSPOT_TOOLS:-49}"
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
    timezone,
    expect_heartbeat,
    expected_enabled_count,
) = sys.argv[1:9]

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

def require_job(name, *, expr, script=None, require_timezone=True):
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
    if has_unsafe_send_message(str(job.get("prompt") or "")):
        print(f"cron:{name}:unsafe-send-message")
        raise SystemExit(1)

require_job(health_name, expr="0 1 * * 1-5", script="nurtureanysalesbot-check-health.sh")
require_job(audit_name, expr="15 1 * * 1-5", script="nurtureanysalesbot-audit-live-profile.sh")
require_job(socket_name, expr="*/5 * * * *", script="nurtureanysalesbot-check-slack-socket-health.sh")
if expect_heartbeat == "1":
    require_job(heartbeat_name, expr="*/15 * * * *", script="nurtureanysalesbot-check-cloud-heartbeat.sh")

enabled = [job for job in jobs if isinstance(job, dict) and job.get("enabled") is True]
if len(enabled) != int(expected_enabled_count):
    print(f"cron:enabled-count-unexpected:{len(enabled)}")
    raise SystemExit(1)

for job in jobs:
    name = str(job.get("name") or "")
    prompt = str(job.get("prompt") or "")
    if name.startswith("event-roi-") and job.get("enabled") is True:
        print(f"cron:{name}:event-roi-enabled")
        raise SystemExit(1)
    if job.get("enabled") is True and job.get("timezone") is None:
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
  grep -Fq "cron:enabled=$EXPECT_ENABLED_CRON_COUNT:missing_timezone=0:event_roi_enabled=0:unsafe_send_message=0" "$doctor_out" || fail "cloud-doctor:cron-unhealthy"
  for expected in \
    "mcp:staffany_bigquery:tools=4" \
    "mcp:hubspot_nurtureany:tools=$EXPECT_HUBSPOT_TOOLS" \
    "mcp:google_calendar_nurtureany:tools=2" \
    "mcp:google_drive_nurtureany:tools=5" \
    "mcp:eazybe_nurtureany:tools=4" \
    "mcp:luma_nurtureany:tools=3" \
    "mcp:public_research_nurtureany:tools=1" \
    "mcp:lusha_nurtureany:tools=3" \
    "mcp:exa_nurtureany:tools=1" \
    "mcp:near_me_nurtureany:tools=6"; do
    grep -Fq "$expected" "$doctor_out" || fail "cloud-doctor:${expected}:missing"
  done
fi
