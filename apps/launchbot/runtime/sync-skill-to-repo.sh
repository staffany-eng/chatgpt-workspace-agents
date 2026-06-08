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
APPLY_SCRIPT="${LAUNCHBOT_APPLY_SKILL_SYNC_SCRIPT:-$PROFILE_DIR/scripts/launchbot-apply-skill-sync.sh}"
STATUS_PATH="${LAUNCHBOT_SKILL_SYNC_STATUS_PATH:-$PROFILE_DIR/runtime/skill-sync-status.json}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
DBUS_ADDR="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$RUNTIME_DIR/bus}"
REQUESTER_SLACK_USER_ID="${LAUNCHBOT_REQUESTER_SLACK_USER_ID:-}"
UPDATE_APPROVER_USER_IDS="${LAUNCHBOT_RUNTIME_UPDATE_APPROVER_USER_IDS:-}"

need_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '%s\n' "launchbot-skill-sync:error:missing-command:$1" >&2
    exit 1
  }
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

write_status() {
  state="$1"
  skill_name="$2"
  repo_path="$3"
  message="$4"
  worker_unit="${5:-}"
  commit_sha="${6:-}"
  mkdir -p "$(dirname "$STATUS_PATH")"
  cat > "$STATUS_PATH" <<EOF
{
  "state": "$(json_escape "$state")",
  "skill_name": "$(json_escape "$skill_name")",
  "repo_path": "$(json_escape "$repo_path")",
  "message": "$(json_escape "$message")",
  "worker_unit": "$(json_escape "$worker_unit")",
  "commit_sha": "$(json_escape "$commit_sha")",
  "updated_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
}

fail_sync() {
  skill_name="${1:-}"
  repo_path="${2:-}"
  message="$3"
  write_status "error" "$skill_name" "$repo_path" "$message"
  printf '%s\n' "launchbot-skill-sync:error:$message" >&2
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

SKILL_NAME=""
COMMIT_CHANGES=0
PUSH_CHANGES=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skill)
      [ "$#" -ge 2 ] || fail_sync "" "" "missing-skill-name"
      SKILL_NAME="$2"
      shift 2
      ;;
    --commit)
      COMMIT_CHANGES=1
      shift
      ;;
    --push)
      PUSH_CHANGES=1
      shift
      ;;
    *)
      fail_sync "$SKILL_NAME" "" "unsupported-arg:$1"
      ;;
  esac
done

[ -n "$SKILL_NAME" ] || fail_sync "" "" "missing-skill-name"
[ -d "$REPO_DIR/.git" ] || fail_sync "$SKILL_NAME" "" "repo-not-found:$REPO_DIR"
[ -x "$APPLY_SCRIPT" ] || fail_sync "$SKILL_NAME" "" "apply-script-missing:$APPLY_SCRIPT"

need_command systemd-run
need_command date

if [ -n "$UPDATE_APPROVER_USER_IDS" ]; then
  [ -n "$REQUESTER_SLACK_USER_ID" ] || fail_sync "$SKILL_NAME" "" "requester-user-id-required"
  csv_contains "$REQUESTER_SLACK_USER_ID" "$UPDATE_APPROVER_USER_IDS" || fail_sync "$SKILL_NAME" "" "unauthorized-requester:$REQUESTER_SLACK_USER_ID"
fi

unit_name="launchbot-skill-sync-$(date -u +%Y%m%d%H%M%S)"

export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

systemd-run --user \
  --unit "$unit_name" \
  --property Type=oneshot \
  --property CollectMode=inactive-or-failed \
  --setenv "HERMES_PROFILE=$PROFILE" \
  --setenv "HERMES_PROFILE_DIR=$PROFILE_DIR" \
  --setenv "LAUNCHBOT_APP_REPO_DIR=$REPO_DIR" \
  --setenv "LAUNCHBOT_SKILL_SYNC_STATUS_PATH=$STATUS_PATH" \
  --setenv "LAUNCHBOT_SKILL_SYNC_NAME=$SKILL_NAME" \
  --setenv "LAUNCHBOT_SKILL_SYNC_COMMIT=$COMMIT_CHANGES" \
  --setenv "LAUNCHBOT_SKILL_SYNC_PUSH=$PUSH_CHANGES" \
  /bin/bash "$APPLY_SCRIPT" >/dev/null

write_status "scheduled" "$SKILL_NAME" "" "skill sync scheduled; repo and live profile will be reconciled" "$unit_name"
printf '%s\n' "launchbot-skill-sync:scheduled:$SKILL_NAME:$unit_name"
