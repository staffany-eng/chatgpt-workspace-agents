#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
ENV_PATH="${LAUNCHBOT_PROFILE_ENV_PATH:-$PROFILE_DIR/.env}"
if [ -f "$ENV_PATH" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_PATH"
  set +a
fi
REPO_DIR="${LAUNCHBOT_APP_REPO_DIR:-$HOME/chatgpt-workspace-agents}"
APPLY_SCRIPT="${LAUNCHBOT_APPLY_APP_SYNC_SCRIPT:-$PROFILE_DIR/scripts/launchbot-apply-app-sync.sh}"
STATUS_PATH="${LAUNCHBOT_APP_SYNC_STATUS_PATH:-$PROFILE_DIR/runtime/app-sync-status.json}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
DBUS_ADDR="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$RUNTIME_DIR/bus}"
REQUESTER_SLACK_USER_ID="${LAUNCHBOT_REQUESTER_SLACK_USER_ID:-}"
UPDATE_APPROVER_USER_IDS="${LAUNCHBOT_RUNTIME_UPDATE_APPROVER_USER_IDS:-}"

need_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '%s\n' "launchbot-app-sync:error:missing-command:$1" >&2
    exit 1
  }
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

write_status() {
  state="$1"
  commit_sha="$2"
  message="$3"
  worker_unit="${4:-}"
  mkdir -p "$(dirname "$STATUS_PATH")"
  cat > "$STATUS_PATH" <<EOF
{
  "state": "$(json_escape "$state")",
  "commit_sha": "$(json_escape "$commit_sha")",
  "message": "$(json_escape "$message")",
  "worker_unit": "$(json_escape "$worker_unit")",
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

csv_contains() {
  needle="$1"
  csv="$2"
  old_ifs="$IFS"
  IFS=','
  for item in $csv; do
    trimmed="$(printf '%s' "$item" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    if [ -n "$trimmed" ] && [ "$trimmed" = "$needle" ]; then
      IFS="$old_ifs"
      return 0
    fi
  done
  IFS="$old_ifs"
  return 1
}

has_app_diff() {
  src="$1"
  dst="$2"
  diff -qr \
    -x output \
    -x __pycache__ \
    -x '*.pyc' \
    -x '*.pyo' \
    "$src" "$dst" >/dev/null 2>&1
}

COMMIT_CHANGES=0
PUSH_CHANGES=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --commit)
      COMMIT_CHANGES=1
      shift
      ;;
    --push)
      PUSH_CHANGES=1
      shift
      ;;
    *)
      fail_sync "" "unsupported-arg:$1"
      ;;
  esac
done

[ -d "$PROFILE_DIR/source/launchbot" ] || fail_sync "" "profile-source-not-found:$PROFILE_DIR/source/launchbot"
[ -d "$REPO_DIR/apps/launchbot" ] || fail_sync "" "repo-app-not-found:$REPO_DIR/apps/launchbot"
[ -d "$REPO_DIR/.git" ] || fail_sync "" "repo-not-found:$REPO_DIR"
[ -x "$APPLY_SCRIPT" ] || fail_sync "" "apply-script-missing:$APPLY_SCRIPT"

need_command systemd-run
need_command git
need_command diff
need_command date

if [ -n "$UPDATE_APPROVER_USER_IDS" ]; then
  [ -n "$REQUESTER_SLACK_USER_ID" ] || fail_sync "" "requester-user-id-required"
  csv_contains "$REQUESTER_SLACK_USER_ID" "$UPDATE_APPROVER_USER_IDS" || fail_sync "" "unauthorized-requester:$REQUESTER_SLACK_USER_ID"
fi

cd "$REPO_DIR"
commit_sha="$(git rev-parse HEAD)"

dirty_status="$(git status --porcelain=v1 --untracked-files=no)"
[ -z "$dirty_status" ] || fail_sync "$commit_sha" "repo-dirty-worktree"

if has_app_diff "$PROFILE_DIR/source/launchbot" "$REPO_DIR/apps/launchbot"; then
  write_status "no_change" "$commit_sha" "repo app already matches live profile source"
  printf '%s\n' "launchbot-app-sync:no-change:$commit_sha"
  exit 0
fi

unit_name="launchbot-app-sync-$(date -u +%Y%m%d%H%M%S)"

export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

write_status "scheduled" "$commit_sha" "app sync scheduled; repo source and live profile will be reconciled" "$unit_name"

systemd-run --user \
  --unit "$unit_name" \
  --property Type=oneshot \
  --property CollectMode=inactive-or-failed \
  --setenv "HERMES_PROFILE=$PROFILE" \
  --setenv "HERMES_PROFILE_DIR=$PROFILE_DIR" \
  --setenv "LAUNCHBOT_APP_REPO_DIR=$REPO_DIR" \
  --setenv "LAUNCHBOT_APP_SYNC_STATUS_PATH=$STATUS_PATH" \
  --setenv "LAUNCHBOT_APP_SYNC_COMMIT=$COMMIT_CHANGES" \
  --setenv "LAUNCHBOT_APP_SYNC_PUSH=$PUSH_CHANGES" \
  /bin/bash "$APPLY_SCRIPT" >/dev/null

printf '%s\n' "launchbot-app-sync:scheduled:$commit_sha:$unit_name"
