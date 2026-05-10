#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-nurtureanysalesbot}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$HOME/.hermes/profiles/$PROFILE" ]; then
  export HERMES_HOME="$HOME/.hermes/profiles/$PROFILE"
fi
EXPECTED_HEALTH_CRON_NAME="${EXPECTED_HEALTH_CRON_NAME:-nurtureanysalesbot health check}"
EXPECTED_AUDIT_CRON_NAME="${EXPECTED_AUDIT_CRON_NAME:-nurtureanysalesbot live profile audit}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
if [ -n "${NURTUREANY_APP_ROOT:-}" ]; then
  APP_ROOT="$NURTUREANY_APP_ROOT"
elif [ -f "$SCRIPT_DIR/../app.manifest.json" ]; then
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

[ -d "$PROFILE_DIR" ] || fail "profile:not-found"

cmp -s "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile-drift:soul"
diff -qr "$APP_ROOT/skills/nurtureany-sales-bot" "$PROFILE_DIR/skills/nurtureany-sales-bot" >/dev/null || fail "profile-drift:nurtureany-sales-bot-skill"
cmp -s "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/nurtureanysalesbot-check-health.sh" || fail "profile-drift:health-script"
cmp -s "$APP_ROOT/runtime/audit-live-profile.sh" "$PROFILE_DIR/scripts/nurtureanysalesbot-audit-live-profile.sh" || fail "profile-drift:audit-script"

if [ -e "$PROFILE_DIR/skills/staffany-data-bot/SKILL.md" ]; then
  fail "profile-boundary:staffany-data-bot-skill-installed"
fi

cron_out="$(hermes -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_HEALTH_CRON_NAME" || fail "cron:health-check-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_AUDIT_CRON_NAME" || fail "cron:audit-missing"

"$PROFILE_DIR/scripts/nurtureanysalesbot-check-health.sh" >/dev/null

printf 'live-profile:audit-ok\n'
