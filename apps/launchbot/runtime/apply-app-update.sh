#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
REPO_DIR="${LAUNCHBOT_APP_REPO_DIR:-$HOME/chatgpt-workspace-agents}"
REMOTE="${LAUNCHBOT_APP_REMOTE:-origin}"
BRANCH="${LAUNCHBOT_APP_BRANCH:-main}"
SYNC_SCRIPT="${LAUNCHBOT_SYNC_SCRIPT:-$REPO_DIR/apps/launchbot/runtime/sync-live-profile.sh}"
HEALTH_SCRIPT="${LAUNCHBOT_HEALTH_SCRIPT:-$PROFILE_DIR/scripts/launchbot-check-health.sh}"
STATUS_PATH="${LAUNCHBOT_APP_UPDATE_STATUS_PATH:-$PROFILE_DIR/runtime/app-update-status.json}"
GATEWAY_SERVICE_NAME="${LAUNCHBOT_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
DBUS_ADDR="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$RUNTIME_DIR/bus}"

need_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '%s\n' "launchbot-app-update:error:missing-command:$1" >&2
    exit 1
  }
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

write_status() {
  state="$1"
  from_sha="$2"
  to_sha="$3"
  message="$4"
  mkdir -p "$(dirname "$STATUS_PATH")"
  cat > "$STATUS_PATH" <<EOF
{
  "state": "$(json_escape "$state")",
  "from_sha": "$(json_escape "$from_sha")",
  "to_sha": "$(json_escape "$to_sha")",
  "message": "$(json_escape "$message")",
  "updated_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
}

fail_update() {
  from_sha="${1:-}"
  to_sha="${2:-}"
  message="$3"
  write_status "error" "$from_sha" "$to_sha" "$message"
  printf '%s\n' "launchbot-app-update:error:$message" >&2
  exit 1
}

need_command git
need_command systemctl
need_command date

[ -d "$REPO_DIR/.git" ] || fail_update "" "" "repo-not-found:$REPO_DIR"
[ -x "$SYNC_SCRIPT" ] || fail_update "" "" "sync-script-missing:$SYNC_SCRIPT"
[ -x "$HEALTH_SCRIPT" ] || fail_update "" "" "health-script-missing:$HEALTH_SCRIPT"

cd "$REPO_DIR"

dirty_status="$(git status --porcelain=v1 --untracked-files=no)"
[ -z "$dirty_status" ] || fail_update "" "" "repo-dirty-worktree"

current_branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$current_branch" = "$BRANCH" ] || fail_update "" "" "repo-branch-unexpected:$current_branch"

from_sha="$(git rev-parse HEAD)"

if ! git fetch "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
  fail_update "$from_sha" "" "git-fetch-failed:$REMOTE/$BRANCH"
fi

to_sha="$(git rev-parse "$REMOTE/$BRANCH")"

if [ "$from_sha" = "$to_sha" ]; then
  write_status "no_change" "$from_sha" "$to_sha" "already up to date"
  printf '%s\n' "launchbot-app-update:no-change:$from_sha"
  exit 0
fi

write_status "running" "$from_sha" "$to_sha" "pulling latest repo and syncing profile"

if ! git pull --ff-only "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
  fail_update "$from_sha" "$to_sha" "git-pull-failed:$REMOTE/$BRANCH"
fi

new_sha="$(git rev-parse HEAD)"

"$SYNC_SCRIPT" >/dev/null 2>&1 || fail_update "$from_sha" "$new_sha" "profile-sync-failed"

export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

if ! systemctl --user restart "$GATEWAY_SERVICE_NAME" >/dev/null 2>&1; then
  fail_update "$from_sha" "$new_sha" "gateway-restart-failed"
fi

if ! systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME"; then
  fail_update "$from_sha" "$new_sha" "gateway-not-active"
fi

if ! HERMES_HOME="$PROFILE_DIR" HERMES_PROFILE_DIR="$PROFILE_DIR" "$HEALTH_SCRIPT" >/dev/null 2>&1; then
  fail_update "$from_sha" "$new_sha" "health-check-failed"
fi

write_status "updated" "$from_sha" "$new_sha" "repo pulled, profile synced, gateway restarted, health passed"
printf '%s\n' "launchbot-app-update:updated:$from_sha:$new_sha"
