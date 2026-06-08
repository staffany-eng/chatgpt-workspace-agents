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
REMOTE="${LAUNCHBOT_APP_REMOTE:-origin}"
BRANCH="${LAUNCHBOT_APP_BRANCH:-main}"
APPLY_SCRIPT="${LAUNCHBOT_APPLY_APP_UPDATE_SCRIPT:-$PROFILE_DIR/scripts/launchbot-apply-app-update.sh}"
STATUS_PATH="${LAUNCHBOT_APP_UPDATE_STATUS_PATH:-$PROFILE_DIR/runtime/app-update-status.json}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
DBUS_ADDR="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$RUNTIME_DIR/bus}"
REQUESTER_SLACK_USER_ID="${LAUNCHBOT_REQUESTER_SLACK_USER_ID:-}"
UPDATE_APPROVER_USER_IDS="${LAUNCHBOT_RUNTIME_UPDATE_APPROVER_USER_IDS:-}"

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
  worker_unit="${5:-}"
  mkdir -p "$(dirname "$STATUS_PATH")"
  cat > "$STATUS_PATH" <<EOF
{
  "state": "$(json_escape "$state")",
  "from_sha": "$(json_escape "$from_sha")",
  "to_sha": "$(json_escape "$to_sha")",
  "message": "$(json_escape "$message")",
  "worker_unit": "$(json_escape "$worker_unit")",
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

csv_contains() {
  needle="$1"
  csv="$2"
  OLD_IFS="$IFS"
  IFS=','
  for item in $csv; do
    trimmed="$(printf '%s' "$item" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    if [ -n "$trimmed" ] && [ "$trimmed" = "$needle" ]; then
      IFS="$OLD_IFS"
      return 0
    fi
  done
  IFS="$OLD_IFS"
  return 1
}

need_command git
need_command systemd-run
need_command date

if [ -n "$UPDATE_APPROVER_USER_IDS" ]; then
  [ -n "$REQUESTER_SLACK_USER_ID" ] || fail_update "" "" "requester-user-id-required"
  csv_contains "$REQUESTER_SLACK_USER_ID" "$UPDATE_APPROVER_USER_IDS" || fail_update "" "" "unauthorized-requester:$REQUESTER_SLACK_USER_ID"
fi

[ -d "$REPO_DIR/.git" ] || fail_update "" "" "repo-not-found:$REPO_DIR"
[ -x "$APPLY_SCRIPT" ] || fail_update "" "" "apply-script-missing:$APPLY_SCRIPT"

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

unit_name="launchbot-app-update-$(date -u +%Y%m%d%H%M%S)"

export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

systemd-run --user \
  --unit "$unit_name" \
  --property Type=oneshot \
  --property CollectMode=inactive-or-failed \
  --setenv "HERMES_PROFILE=$PROFILE" \
  --setenv "HERMES_PROFILE_DIR=$PROFILE_DIR" \
  --setenv "LAUNCHBOT_APP_REPO_DIR=$REPO_DIR" \
  --setenv "LAUNCHBOT_APP_REMOTE=$REMOTE" \
  --setenv "LAUNCHBOT_APP_BRANCH=$BRANCH" \
  --setenv "LAUNCHBOT_APP_UPDATE_STATUS_PATH=$STATUS_PATH" \
  /bin/bash "$APPLY_SCRIPT" >/dev/null

write_status "scheduled" "$from_sha" "$to_sha" "update scheduled; gateway will restart if the pull succeeds" "$unit_name"
printf '%s\n' "launchbot-app-update:scheduled:$from_sha:$to_sha:$unit_name"
