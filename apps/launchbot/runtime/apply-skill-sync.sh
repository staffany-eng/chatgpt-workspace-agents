#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
REPO_DIR="${LAUNCHBOT_APP_REPO_DIR:-$HOME/chatgpt-workspace-agents}"
SKILL_NAME="${LAUNCHBOT_SKILL_SYNC_NAME:-}"
COMMIT_CHANGES="${LAUNCHBOT_SKILL_SYNC_COMMIT:-0}"
PUSH_CHANGES="${LAUNCHBOT_SKILL_SYNC_PUSH:-0}"
STATUS_PATH="${LAUNCHBOT_SKILL_SYNC_STATUS_PATH:-$PROFILE_DIR/runtime/skill-sync-status.json}"
SYNC_SCRIPT="${LAUNCHBOT_SYNC_SCRIPT:-$REPO_DIR/apps/launchbot/runtime/sync-live-profile.sh}"
HEALTH_SCRIPT="${LAUNCHBOT_HEALTH_SCRIPT:-$PROFILE_DIR/scripts/launchbot-check-health.sh}"
GATEWAY_SERVICE_NAME="${LAUNCHBOT_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
REMOTE="${LAUNCHBOT_APP_REMOTE:-origin}"
BRANCH="${LAUNCHBOT_APP_BRANCH:-main}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
DBUS_ADDR="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$RUNTIME_DIR/bus}"

need_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '%s\n' "launchbot-skill-sync:error:missing-command:$1" >&2
    exit 1
  }
}

sync_dir() {
  src="$1"
  dst="$2"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$src/" "$dst/"
  else
    rm -rf "$dst"
    mkdir -p "$dst"
    cp -R "$src/." "$dst/"
  fi
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

write_status() {
  state="$1"
  skill_name="$2"
  repo_path="$3"
  message="$4"
  commit_sha="${5:-}"
  mkdir -p "$(dirname "$STATUS_PATH")"
  cat > "$STATUS_PATH" <<EOF
{
  "state": "$(json_escape "$state")",
  "skill_name": "$(json_escape "$skill_name")",
  "repo_path": "$(json_escape "$repo_path")",
  "message": "$(json_escape "$message")",
  "commit_sha": "$(json_escape "$commit_sha")",
  "updated_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF
}

fail_sync() {
  repo_path="${1:-}"
  message="$2"
  commit_sha="${3:-}"
  write_status "error" "$SKILL_NAME" "$repo_path" "$message" "$commit_sha"
  printf '%s\n' "launchbot-skill-sync:error:$message" >&2
  exit 1
}

resolve_skill_dir() {
  root="$1"
  name="$2"
  matches="$(find "$root" -type f -name SKILL.md -path "*/$name/SKILL.md" | sort || true)"
  count="$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ')"
  case "$count" in
    0) return 1 ;;
    1) dirname "$(printf '%s\n' "$matches")" ;;
    *) return 2 ;;
  esac
}

need_command git
need_command diff
need_command cp
need_command rm
need_command mkdir
need_command systemctl
need_command date

[ -n "$SKILL_NAME" ] || fail_sync "" "missing-skill-name"
[ -d "$PROFILE_DIR/skills" ] || fail_sync "" "profile-skills-not-found:$PROFILE_DIR/skills"
[ -d "$REPO_DIR/.git" ] || fail_sync "" "repo-not-found:$REPO_DIR"
[ -x "$SYNC_SCRIPT" ] || fail_sync "" "sync-script-missing:$SYNC_SCRIPT"
[ -x "$HEALTH_SCRIPT" ] || fail_sync "" "health-script-missing:$HEALTH_SCRIPT"

profile_skill_dir="$(resolve_skill_dir "$PROFILE_DIR/skills" "$SKILL_NAME")" || {
  rc="$?"
  if [ "$rc" -eq 2 ]; then
    fail_sync "" "profile-skill-ambiguous:$SKILL_NAME"
  fi
  fail_sync "" "profile-skill-not-found:$SKILL_NAME"
}

repo_skill_dir="$(resolve_skill_dir "$REPO_DIR/apps/launchbot/skills" "$SKILL_NAME")" || {
  rc="$?"
  if [ "$rc" -eq 2 ]; then
    fail_sync "" "repo-skill-ambiguous:$SKILL_NAME"
  fi
  fail_sync "" "repo-skill-not-found:$SKILL_NAME"
}

repo_skill_rel="${repo_skill_dir#$REPO_DIR/}"

cd "$REPO_DIR"

dirty_status="$(git status --porcelain=v1 --untracked-files=no)"
[ -z "$dirty_status" ] || fail_sync "$repo_skill_rel" "repo-dirty-worktree"

current_branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$current_branch" = "$BRANCH" ] || fail_sync "$repo_skill_rel" "repo-branch-unexpected:$current_branch"

if diff -qr "$profile_skill_dir" "$repo_skill_dir" >/dev/null; then
  write_status "no_change" "$SKILL_NAME" "$repo_skill_rel" "repo already matches live profile skill"
  printf '%s\n' "launchbot-skill-sync:no-change:$SKILL_NAME:$repo_skill_rel"
  exit 0
fi

write_status "running" "$SKILL_NAME" "$repo_skill_rel" "copying live profile skill into repo source"
sync_dir "$profile_skill_dir" "$repo_skill_dir"

commit_sha=""
if [ "$COMMIT_CHANGES" = "1" ] || [ "$PUSH_CHANGES" = "1" ]; then
  git add -- "$repo_skill_rel"
  if ! git commit -m "Sync Launchbot skill update for $SKILL_NAME" -- "$repo_skill_rel" >/dev/null 2>&1; then
    fail_sync "$repo_skill_rel" "git-commit-failed"
  fi
  commit_sha="$(git rev-parse HEAD)"
fi

if [ "$PUSH_CHANGES" = "1" ]; then
  if ! git push "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
    fail_sync "$repo_skill_rel" "git-push-failed:$REMOTE/$BRANCH" "$commit_sha"
  fi
fi

"$SYNC_SCRIPT" >/dev/null 2>&1 || fail_sync "$repo_skill_rel" "profile-sync-failed" "$commit_sha"

export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

if ! systemctl --user restart "$GATEWAY_SERVICE_NAME" >/dev/null 2>&1; then
  fail_sync "$repo_skill_rel" "gateway-restart-failed" "$commit_sha"
fi

if ! systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME"; then
  fail_sync "$repo_skill_rel" "gateway-not-active" "$commit_sha"
fi

if ! HERMES_HOME="$PROFILE_DIR" HERMES_PROFILE_DIR="$PROFILE_DIR" "$HEALTH_SCRIPT" >/dev/null 2>&1; then
  fail_sync "$repo_skill_rel" "health-check-failed" "$commit_sha"
fi

write_status "updated" "$SKILL_NAME" "$repo_skill_rel" "repo synced from live profile, profile rebuilt, gateway restarted, health passed" "$commit_sha"
printf '%s\n' "launchbot-skill-sync:updated:$SKILL_NAME:$repo_skill_rel${commit_sha:+:$commit_sha}"
