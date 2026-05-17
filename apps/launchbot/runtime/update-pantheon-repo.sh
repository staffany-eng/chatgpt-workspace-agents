#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
PANTHEON_REPO_URL="${LAUNCHBOT_PANTHEON_REPO_URL:-git@github.com:staffany-eng/pantheon.git}"
PANTHEON_BRANCH="${LAUNCHBOT_PANTHEON_BRANCH:-develop}"
PANTHEON_REPO_DIR="${LAUNCHBOT_PANTHEON_REPO_DIR:-$PROFILE_DIR/source/pantheon}"
PANTHEON_SSH_KEY="${LAUNCHBOT_PANTHEON_SSH_KEY:-$PROFILE_DIR/ssh/pantheon_deploy_key}"
STATUS_PATH="${LAUNCHBOT_PANTHEON_STATUS_PATH:-$PROFILE_DIR/runtime/pantheon-repo-status.json}"

PATH="$HOME/.local/bin:$PATH"
export PATH

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

fail_git_access() {
  message="$1"
  if printf '%s\n' "$message" | grep -Fq "Permission denied (publickey)"; then
    fail "pantheon:ssh-access-denied:$PANTHEON_REPO_URL"
  fi
  fail "pantheon:ssh-access-check-failed:$(printf '%s' "$message" | head -c 160)"
}

need_command git
need_command date
need_command mkdir

if [ -r "$PANTHEON_SSH_KEY" ]; then
  export GIT_SSH_COMMAND="ssh -i $PANTHEON_SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
fi

mkdir -p "$(dirname "$PANTHEON_REPO_DIR")" "$(dirname "$STATUS_PATH")" "$(dirname "$PANTHEON_SSH_KEY")"

access_out="$(GIT_TERMINAL_PROMPT=0 git ls-remote "$PANTHEON_REPO_URL" "refs/heads/$PANTHEON_BRANCH" 2>&1)" || fail_git_access "$access_out"

if [ -e "$PANTHEON_REPO_DIR" ] && [ ! -d "$PANTHEON_REPO_DIR/.git" ]; then
  fail "pantheon:path-exists-not-git:$PANTHEON_REPO_DIR"
fi

if [ ! -d "$PANTHEON_REPO_DIR/.git" ]; then
  git clone --branch "$PANTHEON_BRANCH" --single-branch "$PANTHEON_REPO_URL" "$PANTHEON_REPO_DIR"
else
  remote_url="$(git -C "$PANTHEON_REPO_DIR" remote get-url origin 2>/dev/null || true)"
  [ "$remote_url" = "$PANTHEON_REPO_URL" ] || fail "pantheon:remote-unexpected:$remote_url"

  branch="$(git -C "$PANTHEON_REPO_DIR" rev-parse --abbrev-ref HEAD)"
  [ "$branch" = "$PANTHEON_BRANCH" ] || fail "pantheon:branch-unexpected:$branch"

  status="$(git -C "$PANTHEON_REPO_DIR" status --porcelain=v1)"
  [ -z "$status" ] || fail "pantheon:dirty-checkout"

  git -C "$PANTHEON_REPO_DIR" fetch --prune origin "$PANTHEON_BRANCH"
  git -C "$PANTHEON_REPO_DIR" pull --ff-only origin "$PANTHEON_BRANCH"
fi

remote_url="$(git -C "$PANTHEON_REPO_DIR" remote get-url origin)"
branch="$(git -C "$PANTHEON_REPO_DIR" rev-parse --abbrev-ref HEAD)"
sha="$(git -C "$PANTHEON_REPO_DIR" rev-parse HEAD)"
updated_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

[ "$remote_url" = "$PANTHEON_REPO_URL" ] || fail "pantheon:remote-unexpected:$remote_url"
[ "$branch" = "$PANTHEON_BRANCH" ] || fail "pantheon:branch-unexpected:$branch"

cat > "$STATUS_PATH" <<EOF
{
  "repo": "pantheon",
  "remote": "$(json_escape "$remote_url")",
  "branch": "$(json_escape "$branch")",
  "sha": "$(json_escape "$sha")",
  "updated_at": "$(json_escape "$updated_at")",
  "path": "$(json_escape "$PANTHEON_REPO_DIR")"
}
EOF

printf 'pantheon:updated:%s:%s\n' "$branch" "$sha"
