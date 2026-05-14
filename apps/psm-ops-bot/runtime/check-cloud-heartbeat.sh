#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-psmopsbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
GATEWAY_SERVICE="${GATEWAY_SERVICE:-hermes-gateway-psmopsbot.service}"
EXPECTED_REMINDER_CRON_NAME="${EXPECTED_REMINDER_CRON_NAME:-psmopsbot due-date reminders}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-psmopsbot local cloud heartbeat}"
EXPECTED_CLOUD_HEARTBEAT_SCRIPT="${EXPECTED_CLOUD_HEARTBEAT_SCRIPT:-psmopsbot-check-cloud-heartbeat.sh}"
EXPECTED_ADOPTION_DIGEST_CRON_NAME="${EXPECTED_ADOPTION_DIGEST_CRON_NAME:-psmopsbot adoption digest}"
EXPECTED_ADOPTION_DIGEST_SCRIPT="${EXPECTED_ADOPTION_DIGEST_SCRIPT:-psm_ops_adoption_digest.py}"
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

need_command systemctl
need_command python3

systemctl --user is-active --quiet "$GATEWAY_SERVICE" || fail "gateway:not-active:$GATEWAY_SERVICE"
[ "$(systemctl --user is-enabled "$GATEWAY_SERVICE" 2>/dev/null || true)" = "enabled" ] || fail "gateway:not-enabled:$GATEWAY_SERVICE"

cron_json="$PROFILE_DIR/cron/jobs.json"
[ -r "$cron_json" ] || fail "cron:jobs-json-missing"

python3 - "$cron_json" \
  "$EXPECTED_REMINDER_CRON_NAME" \
  "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" \
  "$EXPECTED_CLOUD_HEARTBEAT_SCRIPT" \
  "$EXPECTED_ADOPTION_DIGEST_CRON_NAME" \
  "$EXPECTED_ADOPTION_DIGEST_SCRIPT" \
  "$EXPECTED_ENABLED_CRON_COUNT" \
  "$EXPECTED_CRON_TIMEZONE" <<'PY'
import json
import sys

(
    jobs_path,
    reminder_name,
    heartbeat_name,
    heartbeat_script,
    adoption_digest_name,
    adoption_digest_script,
    expected_enabled_count,
    expected_timezone,
) = sys.argv[1:9]

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
if len(enabled) != int(expected_enabled_count):
    print(f"cron:enabled-count-unexpected:{len(enabled)}")
    raise SystemExit(1)

by_name = {job.get("name"): job for job in enabled if isinstance(job, dict)}
for required_name in [reminder_name, heartbeat_name, adoption_digest_name]:
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

adoption_digest = by_name[adoption_digest_name]
if adoption_digest.get("script") != adoption_digest_script:
    print("cron:adoption-digest-script-unexpected")
    raise SystemExit(1)
adoption_schedule = adoption_digest.get("schedule")
adoption_schedule_expr = adoption_schedule.get("expr") if isinstance(adoption_schedule, dict) else adoption_schedule
if adoption_schedule_expr != "0 2 * * 1-5":
    print("cron:adoption-digest-schedule-unexpected")
    raise SystemExit(1)
if adoption_digest.get("deliver") != "slack:#ps-weeman-bot-test":
    print("cron:adoption-digest-delivery-unexpected")
    raise SystemExit(1)
if adoption_digest.get("no_agent") is not True:
    print("cron:adoption-digest-mode-unexpected")
    raise SystemExit(1)
PY
