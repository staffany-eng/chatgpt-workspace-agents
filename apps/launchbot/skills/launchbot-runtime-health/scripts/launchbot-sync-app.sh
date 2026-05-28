#!/usr/bin/env bash
# launchbot-sync-app.sh
# Pulls latest origin/main from chatgpt-workspace-agents and syncs
# Launchbot app files to the live profile. Restarts the gateway only
# when files actually changed. Safe to run every 5 minutes.
set -euo pipefail

PROFILE_DIR="${HERMES_PROFILE_DIR:-/home/leekaiyi/.hermes/profiles/launchbot}"
REPO_DIR="${LAUNCHBOT_APP_REPO_DIR:-/home/leekaiyi/chatgpt-workspace-agents}"
APP_DIR="$REPO_DIR/apps/launchbot"
GATEWAY_SERVICE="${LAUNCHBOT_GATEWAY_SERVICE_NAME:-hermes-gateway-launchbot.service}"
LOG_PREFIX="launchbot-sync-app"

fail() {
  printf '%s ERROR: %s\n' "$LOG_PREFIX" "$1" >&2
  exit 1
}

log() {
  printf '%s: %s\n' "$LOG_PREFIX" "$1"
}

# ── 1. Fetch and pull origin/main ───────────────────────────────────────────
[ -d "$REPO_DIR/.git" ] || fail "repo not found: $REPO_DIR"

cd "$REPO_DIR"

# Stash any staged/unstaged changes so pull doesn't fail (we never edit locally)
git stash --include-untracked --quiet 2>/dev/null || true

git fetch origin --quiet 2>&1 || fail "git fetch failed"

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse origin/main)"

if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
  log "already up to date ($LOCAL_SHA) — nothing to sync"
  exit 0
fi

log "new commits detected: $LOCAL_SHA → $REMOTE_SHA"

git checkout main --quiet 2>/dev/null || true
git pull origin main --ff-only --quiet 2>&1 || fail "git pull failed"

# ── 2. Copy app files to live profile ────────────────────────────────────────
CHANGED=0

copy_if_changed() {
  src="$1"
  dst="$2"
  # Skip files not present in repo (e.g. live-only MCP servers not yet in origin/main)
  [ -f "$src" ] || { log "skipping (not in repo): $src"; return 0; }
  mkdir -p "$(dirname "$dst")"
  if ! cmp -s "$src" "$dst" 2>/dev/null; then
    cp "$src" "$dst"
    log "updated: $dst"
    CHANGED=1
  fi
}

# profile/SOUL.md → PROFILE_DIR/SOUL.md
copy_if_changed "$APP_DIR/profile/SOUL.md" "$PROFILE_DIR/SOUL.md"

# runtime scripts → PROFILE_DIR/scripts/
copy_if_changed "$APP_DIR/runtime/check-health.sh"          "$PROFILE_DIR/scripts/launchbot-check-health.sh"
copy_if_changed "$APP_DIR/runtime/audit-live-profile.sh"    "$PROFILE_DIR/scripts/launchbot-audit-live-profile.sh"
copy_if_changed "$APP_DIR/runtime/update-pantheon-repo.sh"  "$PROFILE_DIR/scripts/launchbot-update-pantheon-repo.sh"
copy_if_changed "$APP_DIR/runtime/monitor-feature-intake.py" "$PROFILE_DIR/scripts/launchbot-monitor-feature-intake.py"
copy_if_changed "$APP_DIR/runtime/monitor-support-watch.py"  "$PROFILE_DIR/scripts/launchbot-monitor-support-watch.py"

# runtime/mcp → source/launchbot/runtime/mcp/
MCP_SRC="$APP_DIR/runtime/mcp"
MCP_DST="$PROFILE_DIR/source/launchbot/runtime/mcp"
for f in \
  launchbot_ker_server.py \
  launchbot_ifi_server.py \
  launchbot_product_gap_triage_server.py \
  launchbot_product_commitment_server.py \
  launchbot_feature_intake_core.py \
  launchbot_feature_intake_server.py \
  launchbot_support_watch_core.py \
  launchbot_support_watch_server.py \
  launchbot_help_article_server.py \
  profile_env.py; do
  copy_if_changed "$MCP_SRC/$f" "$MCP_DST/$f"
done

# runtime SQL → source/launchbot/runtime/
copy_if_changed \
  "$APP_DIR/runtime/support-watch-whatsapp-refresh.sql" \
  "$PROFILE_DIR/source/launchbot/runtime/support-watch-whatsapp-refresh.sql"

# skills references → source/launchbot/skills/
SKILLS_SRC="$APP_DIR/skills/help-article-generator/references"
SKILLS_DST="$PROFILE_DIR/source/launchbot/skills/help-article-generator/references"
copy_if_changed "$SKILLS_SRC/video-placement-registry.json" "$SKILLS_DST/video-placement-registry.json"
copy_if_changed "$SKILLS_SRC/article-planning-profile.json" "$SKILLS_DST/article-planning-profile.json"
copy_if_changed "$SKILLS_SRC/help-article-skeleton.md"      "$SKILLS_DST/help-article-skeleton.md"
copy_if_changed "$SKILLS_SRC/intercom-article-inventory.json" "$SKILLS_DST/intercom-article-inventory.json"
copy_if_changed "$SKILLS_SRC/intercom-format-profile.json"  "$SKILLS_DST/intercom-format-profile.json"
copy_if_changed "$SKILLS_SRC/staffany-help-center-style.md" "$SKILLS_DST/staffany-help-center-style.md"

# Also mirror the full apps/launchbot tree to source/launchbot (for audit script APP_ROOT)
rsync -a --delete \
  "$APP_DIR/" \
  "$PROFILE_DIR/source/launchbot/" \
  2>/dev/null || {
  log "rsync not available; key files already copied individually above"
}

# ── 3. Restart gateway only if something changed ────────────────────────────
if [ "$CHANGED" -eq 1 ]; then
  log "restarting gateway: $GATEWAY_SERVICE"
  systemctl --user restart "$GATEWAY_SERVICE" \
    && log "gateway restarted ok" \
    || fail "systemctl restart failed"
else
  log "no file changes — skipping gateway restart"
fi

log "sync complete (head: $REMOTE_SHA)"
