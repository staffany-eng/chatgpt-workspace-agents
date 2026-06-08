#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-psmopsbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
GATEWAY_SERVICE="${GATEWAY_SERVICE:-hermes-gateway-psmopsbot.service}"
EXPECTED_REMINDER_CRON_NAME="${EXPECTED_REMINDER_CRON_NAME:-psmopsbot due-date reminders}"
EXPECTED_REMINDER_SCRIPT="${EXPECTED_REMINDER_SCRIPT:-psm_ops_due_date_reminders.py}"
EXPECTED_EOD_REMINDER_CRON_NAME="${EXPECTED_EOD_REMINDER_CRON_NAME:-psmopsbot due-date eod catch-up}"
EXPECTED_EOD_REMINDER_SCRIPT="${EXPECTED_EOD_REMINDER_SCRIPT:-psm_ops_due_date_reminders_eod.py}"
EXPECTED_ASSIGNMENT_HYGIENE_CRON_NAME="${EXPECTED_ASSIGNMENT_HYGIENE_CRON_NAME:-psmopsbot assignment hygiene}"
EXPECTED_ASSIGNMENT_HYGIENE_SCRIPT="${EXPECTED_ASSIGNMENT_HYGIENE_SCRIPT:-psm_ops_pco_assignment_hygiene.py}"
EXPECTED_ROI_TRACKER_SYNC_CRON_NAME="${EXPECTED_ROI_TRACKER_SYNC_CRON_NAME:-psmopsbot roi tracker sync}"
EXPECTED_ROI_TRACKER_SYNC_SCRIPT="${EXPECTED_ROI_TRACKER_SYNC_SCRIPT:-psm_ops_roi_tracker_sync.py}"
EXPECTED_CHURN_REPORTING_CHASE_CRON_NAME="${EXPECTED_CHURN_REPORTING_CHASE_CRON_NAME:-psmopsbot churn reporting chase}"
EXPECTED_CHURN_REPORTING_CHASE_SCRIPT="${EXPECTED_CHURN_REPORTING_CHASE_SCRIPT:-psm_ops_churn_reporting_chase.py}"
EXPECTED_STORE_REVIEW_CRON_NAME="${EXPECTED_STORE_REVIEW_CRON_NAME:-psmopsbot store review poll}"
EXPECTED_STORE_REVIEW_SCRIPT="${EXPECTED_STORE_REVIEW_SCRIPT:-psm_ops_store_review_poll.py}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-psmopsbot local cloud heartbeat}"
EXPECTED_CLOUD_HEARTBEAT_SCRIPT="${EXPECTED_CLOUD_HEARTBEAT_SCRIPT:-psmopsbot-check-cloud-heartbeat.sh}"
EXPECTED_ADOPTION_DIGEST_CRON_NAME="${EXPECTED_ADOPTION_DIGEST_CRON_NAME:-psmopsbot adoption digest}"
EXPECTED_ADOPTION_DIGEST_SCRIPT="${EXPECTED_ADOPTION_DIGEST_SCRIPT:-psm_ops_adoption_digest.py}"
EXPECTED_ENABLED_CRON_COUNT="${EXPECTED_ENABLED_CRON_COUNT:-8}"
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
  "$EXPECTED_REMINDER_SCRIPT" \
  "$EXPECTED_EOD_REMINDER_CRON_NAME" \
  "$EXPECTED_EOD_REMINDER_SCRIPT" \
  "$EXPECTED_ASSIGNMENT_HYGIENE_CRON_NAME" \
  "$EXPECTED_ASSIGNMENT_HYGIENE_SCRIPT" \
  "$EXPECTED_ROI_TRACKER_SYNC_CRON_NAME" \
  "$EXPECTED_ROI_TRACKER_SYNC_SCRIPT" \
  "$EXPECTED_CHURN_REPORTING_CHASE_CRON_NAME" \
  "$EXPECTED_CHURN_REPORTING_CHASE_SCRIPT" \
  "$EXPECTED_STORE_REVIEW_CRON_NAME" \
  "$EXPECTED_STORE_REVIEW_SCRIPT" \
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
    reminder_script,
    eod_reminder_name,
    eod_reminder_script,
    assignment_hygiene_name,
    assignment_hygiene_script,
    roi_tracker_sync_name,
    roi_tracker_sync_script,
    churn_reporting_chase_name,
    churn_reporting_chase_script,
    store_review_name,
    store_review_script,
    heartbeat_name,
    heartbeat_script,
    adoption_digest_name,
    adoption_digest_script,
    expected_enabled_count,
    expected_timezone,
) = sys.argv[1:21]

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
for required_name in [reminder_name, eod_reminder_name, assignment_hygiene_name, roi_tracker_sync_name, churn_reporting_chase_name, store_review_name, heartbeat_name, adoption_digest_name]:
    if required_name not in by_name:
        print(f"cron:missing:{required_name}")
        raise SystemExit(1)

def schedule_expr(job):
    schedule = job.get("schedule")
    return schedule.get("expr") if isinstance(schedule, dict) else schedule

reminder = by_name[reminder_name]
if reminder.get("script") != reminder_script:
    print("cron:reminder-script-unexpected")
    raise SystemExit(1)
if schedule_expr(reminder) != "0 1 * * 1-5":
    print("cron:reminder-schedule-unexpected")
    raise SystemExit(1)
if reminder.get("deliver") != "slack:#ps-weeman-bot-test":
    print("cron:reminder-delivery-unexpected")
    raise SystemExit(1)
if reminder.get("no_agent") is not True:
    print("cron:reminder-mode-unexpected")
    raise SystemExit(1)

eod_reminder = by_name[eod_reminder_name]
if eod_reminder.get("script") != eod_reminder_script:
    print("cron:eod-reminder-script-unexpected")
    raise SystemExit(1)
if schedule_expr(eod_reminder) != "0 9 * * 1-5":
    print("cron:eod-reminder-schedule-unexpected")
    raise SystemExit(1)
if eod_reminder.get("deliver") != "slack:#ps-weeman-bot-test":
    print("cron:eod-reminder-delivery-unexpected")
    raise SystemExit(1)
if eod_reminder.get("no_agent") is not True:
    print("cron:eod-reminder-mode-unexpected")
    raise SystemExit(1)

assignment_hygiene = by_name[assignment_hygiene_name]
if assignment_hygiene.get("script") != assignment_hygiene_script:
    print("cron:assignment-hygiene-script-unexpected")
    raise SystemExit(1)
if schedule_expr(assignment_hygiene) != "15 1 * * 1-5":
    print("cron:assignment-hygiene-schedule-unexpected")
    raise SystemExit(1)
if assignment_hygiene.get("deliver") != "slack:#ps-weeman-bot-test":
    print("cron:assignment-hygiene-delivery-unexpected")
    raise SystemExit(1)
if assignment_hygiene.get("no_agent") is not True:
    print("cron:assignment-hygiene-mode-unexpected")
    raise SystemExit(1)

roi_tracker_sync = by_name[roi_tracker_sync_name]
if roi_tracker_sync.get("script") != roi_tracker_sync_script:
    print("cron:roi-tracker-sync-script-unexpected")
    raise SystemExit(1)
if schedule_expr(roi_tracker_sync) != "*/30 1-10 * * 1-5":
    print("cron:roi-tracker-sync-schedule-unexpected")
    raise SystemExit(1)
if roi_tracker_sync.get("deliver") != "slack:#ps-weeman-bot-test":
    print("cron:roi-tracker-sync-delivery-unexpected")
    raise SystemExit(1)
if roi_tracker_sync.get("no_agent") is not True:
    print("cron:roi-tracker-sync-mode-unexpected")
    raise SystemExit(1)

churn_reporting_chase = by_name[churn_reporting_chase_name]
if churn_reporting_chase.get("script") != churn_reporting_chase_script:
    print("cron:churn-reporting-chase-script-unexpected")
    raise SystemExit(1)
if schedule_expr(churn_reporting_chase) != "0 1 * * 1":
    print("cron:churn-reporting-chase-schedule-unexpected")
    raise SystemExit(1)
if churn_reporting_chase.get("deliver") != "slack:#team-rev-account-management":
    print("cron:churn-reporting-chase-delivery-unexpected")
    raise SystemExit(1)
if churn_reporting_chase.get("no_agent") is not True:
    print("cron:churn-reporting-chase-mode-unexpected")
    raise SystemExit(1)

store_review = by_name[store_review_name]
if store_review.get("script") != store_review_script:
    print("cron:store-review-script-unexpected")
    raise SystemExit(1)
if schedule_expr(store_review) != "0 1 * * *":
    print("cron:store-review-schedule-unexpected")
    raise SystemExit(1)
if store_review.get("deliver") != "slack:#ps-weeman-bot-test":
    print("cron:store-review-delivery-unexpected")
    raise SystemExit(1)
if store_review.get("no_agent") is not True:
    print("cron:store-review-mode-unexpected")
    raise SystemExit(1)

heartbeat = by_name[heartbeat_name]
if heartbeat.get("script") != heartbeat_script:
    print("cron:heartbeat-script-unexpected")
    raise SystemExit(1)
if schedule_expr(heartbeat) != "*/15 * * * *":
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
if schedule_expr(adoption_digest) != "0 2 * * 1-5":
    print("cron:adoption-digest-schedule-unexpected")
    raise SystemExit(1)
if adoption_digest.get("deliver") != "slack:#ps-weeman-bot-test":
    print("cron:adoption-digest-delivery-unexpected")
    raise SystemExit(1)
if adoption_digest.get("no_agent") is not True:
    print("cron:adoption-digest-mode-unexpected")
    raise SystemExit(1)
PY
