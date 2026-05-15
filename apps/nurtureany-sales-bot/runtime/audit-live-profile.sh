#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-nurtureanysalesbot}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$HOME/.hermes/profiles/$PROFILE" ]; then
  export HERMES_HOME="$HOME/.hermes/profiles/$PROFILE"
fi
EXPECTED_HEALTH_CRON_NAME="${EXPECTED_HEALTH_CRON_NAME:-nurtureanysalesbot health check}"
EXPECTED_AUDIT_CRON_NAME="${EXPECTED_AUDIT_CRON_NAME:-nurtureanysalesbot live profile audit}"
EXPECTED_SLACK_SOCKET_WATCHDOG_CRON_NAME="${EXPECTED_SLACK_SOCKET_WATCHDOG_CRON_NAME:-nurtureanysalesbot Slack socket watchdog}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-nurtureanysalesbot local cloud heartbeat}"
EXPECTED_TASK_REMINDER_CRON_NAME="${EXPECTED_TASK_REMINDER_CRON_NAME:-nurtureanysalesbot HubSpot task reminders}"
EXPECTED_TASK_REMINDER_EOD_CRON_NAME="${EXPECTED_TASK_REMINDER_EOD_CRON_NAME:-nurtureanysalesbot HubSpot task EOD catch-up}"
EXPECTED_CRON_TIMEZONE="${EXPECTED_CRON_TIMEZONE:-Asia/Singapore}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
if [ -n "${NURTUREANY_APP_ROOT:-}" ]; then
  APP_ROOT="$NURTUREANY_APP_ROOT"
elif [ "$(basename "$SCRIPT_DIR")" = "runtime" ] && [ -f "$SCRIPT_DIR/../app.manifest.json" ]; then
  APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_ROOT="$PROFILE_DIR/source/nurtureany-sales-bot"
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
need_command python3

[ -d "$PROFILE_DIR" ] || fail "profile:not-found"

cmp -s "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile-drift:soul"
diff -qr "$APP_ROOT/skills/nurtureany-sales-bot" "$PROFILE_DIR/skills/nurtureany-sales-bot" >/dev/null || fail "profile-drift:nurtureany-sales-bot-skill"
diff -qr "$APP_ROOT/skills/target-account-news-scout" "$PROFILE_DIR/skills/target-account-news-scout" >/dev/null || fail "profile-drift:target-account-news-scout-skill"
python3 - "$APP_ROOT/runtime/mcp" "$PROFILE_DIR/source/nurtureany-sales-bot/runtime/mcp" <<'PY' || fail "profile-drift:runtime-mcp"
import hashlib
import sys
from pathlib import Path

source_root = Path(sys.argv[1])
runtime_root = Path(sys.argv[2])
if not source_root.is_dir() or not runtime_root.is_dir():
    print("profile-drift:runtime-mcp:missing-dir")
    raise SystemExit(1)

def include(path: Path) -> bool:
    ignored_parts = {"__pycache__", ".gcloud"}
    return not (ignored_parts & set(path.parts)) and not path.name.endswith((".pyc", ".orig"))

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

source_files = {
    path.relative_to(source_root).as_posix(): digest(path)
    for path in source_root.rglob("*")
    if path.is_file() and include(path)
}
runtime_files = {
    path.relative_to(runtime_root).as_posix(): digest(path)
    for path in runtime_root.rglob("*")
    if path.is_file() and include(path)
}

for rel in sorted(set(source_files) | set(runtime_files)):
    if source_files.get(rel) != runtime_files.get(rel):
        print(f"profile-drift:runtime-mcp:{rel}")
        raise SystemExit(1)
print(f"profile-drift:runtime-mcp:ok:{len(source_files)}")
PY
cmp -s "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/nurtureanysalesbot-check-health.sh" || fail "profile-drift:health-script"
cmp -s "$APP_ROOT/runtime/check-cloud-heartbeat.sh" "$PROFILE_DIR/scripts/nurtureanysalesbot-check-cloud-heartbeat.sh" || fail "profile-drift:cloud-heartbeat-script"
cmp -s "$APP_ROOT/runtime/audit-live-profile.sh" "$PROFILE_DIR/scripts/nurtureanysalesbot-audit-live-profile.sh" || fail "profile-drift:audit-script"
cmp -s "$APP_ROOT/runtime/check-slack-socket-health.sh" "$PROFILE_DIR/scripts/nurtureanysalesbot-check-slack-socket-health.sh" || fail "profile-drift:slack-socket-watchdog-script"
[ -f "$PROFILE_DIR/scripts/nurtureany_sales_task_reminders.py" ] || fail "profile-drift:hs-reminder-file-missing"
[ -f "$PROFILE_DIR/scripts/nurtureany_sales_task_reminders_eod.py" ] || fail "profile-drift:hs-reminder-eod-file-missing"
cmp -s "$APP_ROOT/runtime/scripts/nurtureany_sales_task_reminders.py" "$PROFILE_DIR/scripts/nurtureany_sales_task_reminders.py" || fail "profile-drift:hs-reminder-file"
cmp -s "$APP_ROOT/runtime/scripts/nurtureany_sales_task_reminders_eod.py" "$PROFILE_DIR/scripts/nurtureany_sales_task_reminders_eod.py" || fail "profile-drift:hs-reminder-eod-file"
if [ -e "$PROFILE_DIR/scripts/nurtureanysalesbot-cloud-doctor.sh" ]; then
  cmp -s "$APP_ROOT/runtime/nurtureany-cloud-doctor.sh" "$PROFILE_DIR/scripts/nurtureanysalesbot-cloud-doctor.sh" || fail "profile-drift:cloud-doctor-script"
fi

if [ -e "$PROFILE_DIR/skills/staffany-data-bot/SKILL.md" ]; then
  fail "profile-boundary:staffany-data-bot-skill-installed"
fi

cron_out="$(hermes -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_HEALTH_CRON_NAME" || fail "cron:health-check-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_AUDIT_CRON_NAME" || fail "cron:audit-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" || fail "cron:cloud-heartbeat-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_SLACK_SOCKET_WATCHDOG_CRON_NAME" || fail "cron:slack-socket-watchdog-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_TASK_REMINDER_CRON_NAME" || fail "cron:hs-reminder-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_TASK_REMINDER_EOD_CRON_NAME" || fail "cron:hs-reminder-eod-missing"

cron_jobs_path="$PROFILE_DIR/cron/jobs.json"
[ -r "$cron_jobs_path" ] || fail "cron:jobs-json-unreadable"
python3 - "$cron_jobs_path" "$EXPECTED_HEALTH_CRON_NAME" "$EXPECTED_AUDIT_CRON_NAME" "$EXPECTED_SLACK_SOCKET_WATCHDOG_CRON_NAME" "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" "$EXPECTED_TASK_REMINDER_CRON_NAME" "$EXPECTED_TASK_REMINDER_EOD_CRON_NAME" "$EXPECTED_CRON_TIMEZONE" > /dev/null <<'PY' || fail "cron:records-invalid"
import json
import sys

jobs_path, health_name, audit_name, watchdog_name, heartbeat_name, task_reminder_name, task_reminder_eod_name, timezone = sys.argv[1:9]
payload = json.loads(open(jobs_path, "r", encoding="utf-8").read())
jobs = payload.get("jobs") if isinstance(payload, dict) else payload
if not isinstance(jobs, list):
    print("cron:jobs-json-invalid")
    raise SystemExit(1)

by_name = {str(job.get("name") or ""): job for job in jobs if isinstance(job, dict)}

def has_unsafe_send_message(prompt):
    return "send_message(target=" in prompt or "send_message(" in prompt

def require_job(name, *, expr, script=None, prompt_contains=None, deliver_prefix=None):
    job = by_name.get(name)
    if not job or job.get("enabled") is not True:
        print(f"cron:{name}:missing-or-disabled")
        raise SystemExit(1)
    schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
    if schedule.get("expr") != expr:
        print(f"cron:{name}:schedule-unexpected")
        raise SystemExit(1)
    if job.get("timezone") not in (None, timezone):
        print(f"cron:{name}:timezone-unexpected")
        raise SystemExit(1)
    if script is not None and job.get("script") != script:
        print(f"cron:{name}:script-unexpected")
        raise SystemExit(1)
    if deliver_prefix is not None and not str(job.get("deliver") or "").startswith(deliver_prefix):
        print(f"cron:{name}:deliver-unexpected")
        raise SystemExit(1)
    prompt = str(job.get("prompt") or "")
    for needle in prompt_contains or []:
        if needle not in prompt:
            print(f"cron:{name}:prompt-missing:{needle}")
            raise SystemExit(1)
    if job.get("enabled") is True and has_unsafe_send_message(prompt):
        print(f"cron:{name}:unsafe-send-message")
        raise SystemExit(1)

require_job(health_name, expr="0 1 * * 1-5", script="nurtureanysalesbot-check-health.sh")
require_job(audit_name, expr="15 1 * * 1-5", script="nurtureanysalesbot-audit-live-profile.sh")
require_job(watchdog_name, expr="*/5 * * * *", script="nurtureanysalesbot-check-slack-socket-health.sh")
require_job(heartbeat_name, expr="*/15 * * * *", script="nurtureanysalesbot-check-cloud-heartbeat.sh")
require_job(task_reminder_name, expr="0 1 * * 1-5", script="nurtureany_sales_task_reminders.py", deliver_prefix="slack:")
require_job(task_reminder_eod_name, expr="0 9 * * 1-5", script="nurtureany_sales_task_reminders_eod.py", deliver_prefix="slack:")

for job in jobs:
    name = str(job.get("name") or "")
    prompt = str(job.get("prompt") or "")
    if name.startswith("event-roi-") and job.get("enabled") is True:
        print(f"cron:{name}:event-roi-enabled")
        raise SystemExit(1)
    if job.get("enabled") is True and job.get("timezone") not in (None, timezone):
        print(f"cron:{name}:timezone-unexpected")
        raise SystemExit(1)
    if job.get("enabled") is True and has_unsafe_send_message(prompt):
        print(f"cron:{name}:unsafe-send-message")
        raise SystemExit(1)
PY

if [ "${RUN_NESTED_HEALTH_CHECK:-1}" = "1" ]; then
  "$PROFILE_DIR/scripts/nurtureanysalesbot-check-health.sh" >/dev/null
fi

printf 'live-profile:audit-ok\n'
