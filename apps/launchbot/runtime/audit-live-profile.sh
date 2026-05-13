#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "${LAUNCHBOT_APP_ROOT:-}" ]; then
  APP_ROOT="$LAUNCHBOT_APP_ROOT"
elif [ -f "$SCRIPT_DIR/../app.manifest.json" ]; then
  APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_ROOT="$PROFILE_DIR/source/launchbot"
fi

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

command -v cmp >/dev/null 2>&1 || fail "dependency:cmp:not-found"
command -v hermes >/dev/null 2>&1 || fail "dependency:hermes:not-found"

[ -d "$PROFILE_DIR" ] || fail "profile:not-found"
[ -d "$APP_ROOT" ] || fail "app-root:not-found"

cmp -s "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile-drift:soul"
cmp -s "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/launchbot-check-health.sh" || fail "profile-drift:health-script"
cmp -s "$APP_ROOT/runtime/audit-live-profile.sh" "$PROFILE_DIR/scripts/launchbot-audit-live-profile.sh" || fail "profile-drift:audit-script"
"$PROFILE_DIR/scripts/launchbot-check-health.sh" >/dev/null

cron_out="$(hermes -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "launchbot health check" || fail "cron:health-check-missing"

printf 'live-profile:audit-ok\n'
