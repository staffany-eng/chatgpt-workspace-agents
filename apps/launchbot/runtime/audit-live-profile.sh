#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
HERMES_PYTHON="${HERMES_PYTHON:-$HERMES_AGENT_DIR/venv/bin/python}"
HERMES_BIN="${HERMES_BIN:-$HERMES_AGENT_DIR/hermes}"
EXPECT_PANTHEON_REPO_URL="${EXPECT_PANTHEON_REPO_URL:-git@github.com:staffany-eng/pantheon.git}"
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
command -v git >/dev/null 2>&1 || fail "dependency:git:not-found"
[ -x "$HERMES_PYTHON" ] || fail "dependency:hermes-python:not-found"
[ -f "$HERMES_BIN" ] || fail "dependency:hermes-bin:not-found"

[ -d "$PROFILE_DIR" ] || fail "profile:not-found"
[ -d "$APP_ROOT" ] || fail "app-root:not-found"

cmp -s "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile-drift:soul"
cmp -s "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/launchbot-check-health.sh" || fail "profile-drift:health-script"
cmp -s "$APP_ROOT/runtime/audit-live-profile.sh" "$PROFILE_DIR/scripts/launchbot-audit-live-profile.sh" || fail "profile-drift:audit-script"
cmp -s "$APP_ROOT/runtime/update-pantheon-repo.sh" "$PROFILE_DIR/scripts/launchbot-update-pantheon-repo.sh" || fail "profile-drift:pantheon-update-script"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_ker_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_ker_server.py" || fail "profile-drift:ker-mcp"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_feature_intake_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_feature_intake_server.py" || fail "profile-drift:feature-intake-mcp"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_help_article_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_help_article_server.py" || fail "profile-drift:help-article-mcp"
cmp -s "$APP_ROOT/skills/help-article-generator/references/video-placement-registry.json" "$PROFILE_DIR/source/launchbot/skills/help-article-generator/references/video-placement-registry.json" || fail "profile-drift:help-article-video-registry"
"$PROFILE_DIR/scripts/launchbot-check-health.sh" >/dev/null

cron_out="$("$HERMES_PYTHON" "$HERMES_BIN" -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "launchbot health check" || fail "cron:health-check-missing"
if GIT_TERMINAL_PROMPT=0 git ls-remote "$EXPECT_PANTHEON_REPO_URL" HEAD >/dev/null 2>&1; then
  printf '%s\n' "$cron_out" | grep -Fq "launchbot pantheon repo update" || fail "cron:pantheon-repo-update-missing"
elif printf '%s\n' "$cron_out" | grep -Fq "launchbot pantheon repo update"; then
  fail "cron:pantheon-repo-update-present-without-github-ssh"
fi

printf 'live-profile:audit-ok\n'
