#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
REPO_DIR="${LAUNCHBOT_APP_REPO_DIR:-$HOME/chatgpt-workspace-agents}"
COMMIT_CHANGES="${LAUNCHBOT_APP_SYNC_COMMIT:-0}"
PUSH_CHANGES="${LAUNCHBOT_APP_SYNC_PUSH:-0}"
STATUS_PATH="${LAUNCHBOT_APP_SYNC_STATUS_PATH:-$PROFILE_DIR/runtime/app-sync-status.json}"
SYNC_SCRIPT="${LAUNCHBOT_SYNC_SCRIPT:-$REPO_DIR/apps/launchbot/runtime/sync-live-profile.sh}"
HEALTH_SCRIPT="${LAUNCHBOT_HEALTH_SCRIPT:-$PROFILE_DIR/scripts/launchbot-check-health.sh}"
GATEWAY_SERVICE_NAME="${LAUNCHBOT_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
REMOTE="${LAUNCHBOT_APP_REMOTE:-origin}"
BRANCH="${LAUNCHBOT_APP_BRANCH:-main}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
DBUS_ADDR="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$RUNTIME_DIR/bus}"

need_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '%s\n' "launchbot-app-sync:error:missing-command:$1" >&2
    exit 1
  }
}

sync_dir() {
  src="$1"
  dst="$2"
  mkdir -p "$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude output/ \
      --exclude __pycache__/ \
      --exclude '*.pyc' \
      --exclude '*.pyo' \
      "$src/" "$dst/"
  else
    rm -rf "$dst"
    mkdir -p "$dst"
    cp -R "$src/." "$dst/"
    rm -rf "$dst/output"
    find "$dst" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$dst" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
  fi
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

write_status() {
  state="$1"
  commit_sha="$2"
  message="$3"
  mkdir -p "$(dirname "$STATUS_PATH")"
  cat > "$STATUS_PATH" <<EOF
{
  "state": "$(json_escape "$state")",
  "commit_sha": "$(json_escape "$commit_sha")",
  "message": "$(json_escape "$message")",
  "updated_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
}

fail_sync() {
  commit_sha="${1:-}"
  message="$2"
  write_status "error" "$commit_sha" "$message"
  printf '%s\n' "launchbot-app-sync:error:$message" >&2
  exit 1
}

need_command git
need_command diff
need_command cp
need_command rm
need_command mkdir
need_command systemctl
need_command date

[ -d "$PROFILE_DIR/source/launchbot" ] || fail_sync "" "profile-source-not-found:$PROFILE_DIR/source/launchbot"
[ -d "$REPO_DIR/apps/launchbot" ] || fail_sync "" "repo-app-not-found:$REPO_DIR/apps/launchbot"
[ -d "$REPO_DIR/.git" ] || fail_sync "" "repo-not-found:$REPO_DIR"
[ -x "$SYNC_SCRIPT" ] || fail_sync "" "sync-script-missing:$SYNC_SCRIPT"
[ -x "$HEALTH_SCRIPT" ] || fail_sync "" "health-script-missing:$HEALTH_SCRIPT"

cd "$REPO_DIR"

commit_sha="$(git rev-parse HEAD)"
dirty_status="$(git status --porcelain=v1 --untracked-files=no)"
[ -z "$dirty_status" ] || fail_sync "$commit_sha" "repo-dirty-worktree"

write_status "running" "$commit_sha" "copying live Launchbot profile source into repo app"
sync_dir "$PROFILE_DIR/source/launchbot" "$REPO_DIR/apps/launchbot"

new_commit_sha="$commit_sha"
if [ "$COMMIT_CHANGES" = "1" ] || [ "$PUSH_CHANGES" = "1" ]; then
  git add -- apps/launchbot
  if ! git commit -m "Sync Launchbot app packet from live profile" -- apps/launchbot >/dev/null 2>&1; then
    fail_sync "$commit_sha" "git-commit-failed"
  fi
  new_commit_sha="$(git rev-parse HEAD)"
fi

if [ "$PUSH_CHANGES" = "1" ]; then
  if ! git push "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
    fail_sync "$new_commit_sha" "git-push-failed:$REMOTE/$BRANCH"
  fi
fi

"$SYNC_SCRIPT" >/dev/null 2>&1 || fail_sync "$new_commit_sha" "profile-sync-failed"

export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

if ! systemctl --user restart "$GATEWAY_SERVICE_NAME" >/dev/null 2>&1; then
  fail_sync "$new_commit_sha" "gateway-restart-failed"
fi

if ! systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME"; then
  fail_sync "$new_commit_sha" "gateway-not-active"
fi

if ! HERMES_HOME="$PROFILE_DIR" HERMES_PROFILE_DIR="$PROFILE_DIR" "$HEALTH_SCRIPT" >/dev/null 2>&1; then
  fail_sync "$new_commit_sha" "health-check-failed"
fi

write_status "updated" "$new_commit_sha" "repo synced from live app profile, profile rebuilt, gateway restarted, health passed"
printf '%s\n' "launchbot-app-sync:updated:$new_commit_sha"
