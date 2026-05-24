#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-staffanydatabot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
DATA_GATEWAY_SERVICE="${DATA_GATEWAY_SERVICE:-hermes-gateway-staffanydatabot.service}"
LAUNCHBOT_GATEWAY_SERVICE="${LAUNCHBOT_GATEWAY_SERVICE:-hermes-gateway-launchbot.service}"
EXPECTED_HEALTH_CRON_NAME="${EXPECTED_HEALTH_CRON_NAME:-staffanydatabot health check}"
EXPECTED_HONCHO_BACKUP_CRON_NAME="${EXPECTED_HONCHO_BACKUP_CRON_NAME:-staffanydatabot Honcho backup}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-staffanydatabot local cloud heartbeat}"
EXPECTED_CLOUD_HEARTBEAT_SCRIPT="${EXPECTED_CLOUD_HEARTBEAT_SCRIPT:-staffanydatabot-check-cloud-heartbeat.sh}"
EXPECTED_ENABLED_CRON_COUNT="${EXPECTED_ENABLED_CRON_COUNT:-3}"
EXPECTED_CRON_TIMEZONE="${EXPECTED_CRON_TIMEZONE:-Asia/Singapore}"

PATH="$HOME/.local/bin:$HOME/.hermes/hermes-agent/venv/bin:$HOME/.hermes/hermes-agent:$PATH"
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

check_user_service() {
  local service_name="$1"
  systemctl --user is-active --quiet "$service_name" || fail "gateway:not-active:$service_name"
  [ "$(systemctl --user is-enabled "$service_name" 2>/dev/null || true)" = "enabled" ] || fail "gateway:not-enabled:$service_name"
}

need_command systemctl
need_command python3

check_user_service "$DATA_GATEWAY_SERVICE"
check_user_service "$LAUNCHBOT_GATEWAY_SERVICE"

cron_json="$PROFILE_DIR/cron/jobs.json"
[ -r "$cron_json" ] || fail "cron:jobs-json-missing"

python3 - "$cron_json" \
  "$EXPECTED_HEALTH_CRON_NAME" \
  "$EXPECTED_HONCHO_BACKUP_CRON_NAME" \
  "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" \
  "$EXPECTED_CLOUD_HEARTBEAT_SCRIPT" \
  "$EXPECTED_ENABLED_CRON_COUNT" \
  "$EXPECTED_CRON_TIMEZONE" <<'PY'
import json
import sys

(
    jobs_path,
    health_name,
    honcho_name,
    heartbeat_name,
    heartbeat_script,
    expected_enabled_count,
    expected_timezone,
) = sys.argv[1:8]

try:
    with open(jobs_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
except Exception:
    print("cron:jobs-json-unreadable")
    raise SystemExit(1)

jobs = raw.get("jobs", raw) if isinstance(raw, dict) else raw
if not isinstance(jobs, list):
    print("cron:jobs-json-invalid")
    raise SystemExit(1)

enabled = [job for job in jobs if isinstance(job, dict) and job.get("enabled", True)]
if len(enabled) < int(expected_enabled_count):
    print(f"cron:enabled-count-below-minimum:{len(enabled)}")
    raise SystemExit(1)

by_name = {job.get("name"): job for job in enabled if isinstance(job, dict)}
for required_name in [health_name, honcho_name, heartbeat_name]:
    if required_name not in by_name:
        print(f"cron:missing:{required_name}")
        raise SystemExit(1)

heartbeat = by_name[heartbeat_name]
if heartbeat.get("script") != heartbeat_script:
    print("cron:heartbeat-script-unexpected")
    raise SystemExit(1)
schedule = heartbeat.get("schedule")
schedule_expr = schedule.get("expr") if isinstance(schedule, dict) else schedule
if schedule_expr != "*/15 * * * *":
    print("cron:heartbeat-schedule-unexpected")
    raise SystemExit(1)
if heartbeat.get("timezone") != expected_timezone:
    print("cron:heartbeat-timezone-unexpected")
    raise SystemExit(1)
if heartbeat.get("deliver"):
    print("cron:heartbeat-delivery-enabled")
    raise SystemExit(1)
PY
