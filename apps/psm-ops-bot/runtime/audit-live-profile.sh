#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-psmopsbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
SOURCE_DIR="${PSM_OPS_SOURCE_DIR:-$(pwd)/apps/psm-ops-bot}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-psmopsbot local cloud heartbeat}"
EXPECTED_ADOPTION_DIGEST_CRON_NAME="${EXPECTED_ADOPTION_DIGEST_CRON_NAME:-psmopsbot adoption digest}"
EXPECTED_REMINDER_CRON_NAME="${EXPECTED_REMINDER_CRON_NAME:-psmopsbot due-date reminders}"
EXPECTED_EOD_REMINDER_CRON_NAME="${EXPECTED_EOD_REMINDER_CRON_NAME:-psmopsbot due-date eod catch-up}"
EXPECTED_ASSIGNMENT_HYGIENE_CRON_NAME="${EXPECTED_ASSIGNMENT_HYGIENE_CRON_NAME:-psmopsbot assignment hygiene}"
EXPECTED_ROI_TRACKER_SYNC_CRON_NAME="${EXPECTED_ROI_TRACKER_SYNC_CRON_NAME:-psmopsbot roi tracker sync}"
EXPECTED_CHURN_REPORTING_CHASE_CRON_NAME="${EXPECTED_CHURN_REPORTING_CHASE_CRON_NAME:-psmopsbot churn reporting chase}"
EXPECTED_STORE_REVIEW_CRON_NAME="${EXPECTED_STORE_REVIEW_CRON_NAME:-psmopsbot store review poll}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
HERMES_PYTHON="${HERMES_PYTHON:-$HERMES_AGENT_DIR/venv/bin/python}"
HERMES_BIN="${HERMES_BIN:-$HERMES_AGENT_DIR/hermes}"

fail() {
  printf '%s\n' "$1"
  exit 1
}

[ -r "$PROFILE_DIR/SOUL.md" ] || fail "profile:soul-missing"
[ -d "$PROFILE_DIR/skills/psm-ops-bot" ] || fail "profile:skill-missing:psm-ops-bot"
[ -d "$PROFILE_DIR/skills/psm-ops-onboarding-task-creator" ] || fail "profile:skill-missing:psm-ops-onboarding-task-creator"

cmp -s "$SOURCE_DIR/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile:soul-drift"
diff -qr "$SOURCE_DIR/skills/psm-ops-bot" "$PROFILE_DIR/skills/psm-ops-bot" >/dev/null || fail "profile:skill-drift:psm-ops-bot"
diff -qr "$SOURCE_DIR/skills/psm-ops-onboarding-task-creator" "$PROFILE_DIR/skills/psm-ops-onboarding-task-creator" >/dev/null || fail "profile:skill-drift:psm-ops-onboarding-task-creator"
diff -qr -x __pycache__ "$SOURCE_DIR/runtime/mcp" "$PROFILE_DIR/runtime/mcp" >/dev/null || fail "profile:mcp-drift"
cmp -s "$SOURCE_DIR/runtime/check-health.sh" "$PROFILE_DIR/scripts/psmopsbot-check-health.sh" || fail "profile:health-script-drift"
cmp -s "$SOURCE_DIR/runtime/check-cloud-heartbeat.sh" "$PROFILE_DIR/scripts/psmopsbot-check-cloud-heartbeat.sh" || fail "profile:cloud-heartbeat-script-drift"
diff -qr -x __pycache__ "$SOURCE_DIR/runtime/hooks/psm-ops-adoption-telemetry" "$PROFILE_DIR/hooks/psm-ops-adoption-telemetry" >/dev/null || fail "profile:adoption-hook-drift"
diff -qr -x __pycache__ "$SOURCE_DIR/runtime/hooks/psm-ops-mention-guard" "$PROFILE_DIR/hooks/psm-ops-mention-guard" >/dev/null || fail "profile:mention-guard-hook-drift"
cmp -s "$SOURCE_DIR/runtime/psm_ops_adoption_digest.py" "$PROFILE_DIR/scripts/psm_ops_adoption_digest.py" || fail "profile:adoption-digest-script-drift"
cmp -s "$SOURCE_DIR/runtime/scripts/psm_ops_due_date_reminders.py" "$PROFILE_DIR/scripts/psm_ops_due_date_reminders.py" || fail "profile:due-date-reminder-script-drift"
cmp -s "$SOURCE_DIR/runtime/scripts/psm_ops_due_date_reminders.py" "$PROFILE_DIR/scripts/psm_ops_due_date_reminders_eod.py" || fail "profile:eod-due-date-reminder-script-drift"
cmp -s "$SOURCE_DIR/runtime/scripts/psm_ops_pco_assignment_hygiene.py" "$PROFILE_DIR/scripts/psm_ops_pco_assignment_hygiene.py" || fail "profile:assignment-hygiene-script-drift"
cmp -s "$SOURCE_DIR/runtime/scripts/psm_ops_roi_tracker_sync.py" "$PROFILE_DIR/scripts/psm_ops_roi_tracker_sync.py" || fail "profile:roi-tracker-sync-script-drift"
cmp -s "$SOURCE_DIR/runtime/scripts/psm_ops_churn_reporting_chase.py" "$PROFILE_DIR/scripts/psm_ops_churn_reporting_chase.py" || fail "profile:churn-reporting-chase-script-drift"
cmp -s "$SOURCE_DIR/runtime/scripts/psm_ops_store_review_poll.py" "$PROFILE_DIR/scripts/psm_ops_store_review_poll.py" || fail "profile:store-review-poll-script-drift"
cmp -s "$SOURCE_DIR/runtime/sql/psm_ops_churn_projection_dashboard_292.sql" "$PROFILE_DIR/runtime/sql/psm_ops_churn_projection_dashboard_292.sql" || fail "profile:churn-projection-dashboard-292-sql-drift"
cmp -s "$SOURCE_DIR/runtime/scripts/psm_ops_join_public_channels.py" "$PROFILE_DIR/scripts/psm_ops_join_public_channels.py" || fail "profile:public-channel-join-script-drift"

cron_out="$("$HERMES_PYTHON" "$HERMES_BIN" -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_REMINDER_CRON_NAME" || fail "cron:due-date-reminder-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_EOD_REMINDER_CRON_NAME" || fail "cron:eod-due-date-reminder-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_ASSIGNMENT_HYGIENE_CRON_NAME" || fail "cron:assignment-hygiene-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_ROI_TRACKER_SYNC_CRON_NAME" || fail "cron:roi-tracker-sync-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_CHURN_REPORTING_CHASE_CRON_NAME" || fail "cron:churn-reporting-chase-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_STORE_REVIEW_CRON_NAME" || fail "cron:store-review-poll-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" || fail "cron:cloud-heartbeat-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_ADOPTION_DIGEST_CRON_NAME" || fail "cron:adoption-digest-missing"

"$SOURCE_DIR/runtime/check-health.sh"
