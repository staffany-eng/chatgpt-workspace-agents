#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-psmopsbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
SOURCE_DIR="${PSM_OPS_SOURCE_DIR:-$(pwd)/apps/psm-ops-bot}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-psmopsbot local cloud heartbeat}"

fail() {
  printf '%s\n' "$1"
  exit 1
}

[ -r "$PROFILE_DIR/SOUL.md" ] || fail "profile:soul-missing"
[ -d "$PROFILE_DIR/skills/psm-ops-bot" ] || fail "profile:skill-missing"

cmp -s "$SOURCE_DIR/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile:soul-drift"
diff -qr "$SOURCE_DIR/skills/psm-ops-bot" "$PROFILE_DIR/skills/psm-ops-bot" >/dev/null || fail "profile:skill-drift"
cmp -s "$SOURCE_DIR/runtime/check-cloud-heartbeat.sh" "$PROFILE_DIR/scripts/psmopsbot-check-cloud-heartbeat.sh" || fail "profile:cloud-heartbeat-script-drift"

cron_out="$(hermes -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" || fail "cron:cloud-heartbeat-missing"

"$SOURCE_DIR/runtime/check-health.sh"
