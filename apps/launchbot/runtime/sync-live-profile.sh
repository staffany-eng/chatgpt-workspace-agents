#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "${LAUNCHBOT_APP_ROOT:-}" ]; then
  APP_ROOT="$LAUNCHBOT_APP_ROOT"
elif [ -f "$SCRIPT_DIR/../app.manifest.json" ]; then
  APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  printf '%s\n' "launchbot-sync:app-root:not-found" >&2
  exit 1
fi

required_skills=(
  help-article-generator
  help-article-validator
  help-article-feedback-updater
  help-article-screenshot-capture
  help-article-screenshot-troubleshooter
  product-marketing-launch-workflow
  launch-priority-identifier
  customer-support-release-notes-generator
  customer-support-release-notes-validator
  customer-support-release-notes-feedback-updater
  weekly-support-watch
  staffany-indonesia-payroll-tax-grimoire
  product-ops-bot-full-workflow
)

sync_dir() {
  src="$1"
  dst="$2"
  [ -d "$src" ] || {
    printf '%s\n' "launchbot-sync:source-missing:$src" >&2
    exit 1
  }
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ]; then
    rm "$dst"
  fi
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$src/" "$dst/"
  else
    rm -rf "$dst"
    mkdir -p "$dst"
    cp -R "$src/." "$dst/"
  fi
}

mkdir -p "$PROFILE_DIR/scripts" "$PROFILE_DIR/source" "$PROFILE_DIR/skills"

if [ -L "$PROFILE_DIR/source/launchbot" ]; then
  rm "$PROFILE_DIR/source/launchbot"
fi
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude output/ "$APP_ROOT/" "$PROFILE_DIR/source/launchbot/"
else
  sync_dir "$APP_ROOT" "$PROFILE_DIR/source/launchbot"
  rm -rf "$PROFILE_DIR/source/launchbot/output"
fi

install_file() {
  mode="$1"
  src="$2"
  dst="$3"
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ]; then
    rm "$dst"
  fi
  install -m "$mode" "$src" "$dst"
}

install_file 0644 "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md"
install_file 0755 "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/launchbot-check-health.sh"
install_file 0755 "$APP_ROOT/runtime/audit-live-profile.sh" "$PROFILE_DIR/scripts/launchbot-audit-live-profile.sh"
install_file 0755 "$APP_ROOT/runtime/update-pantheon-repo.sh" "$PROFILE_DIR/scripts/launchbot-update-pantheon-repo.sh"
install_file 0755 "$APP_ROOT/runtime/monitor-feature-intake.py" "$PROFILE_DIR/scripts/launchbot-monitor-feature-intake.py"
install_file 0755 "$APP_ROOT/runtime/monitor-support-watch.py" "$PROFILE_DIR/scripts/launchbot-monitor-support-watch.py"

for skill in "${required_skills[@]}"; do
  sync_dir "$APP_ROOT/skills/$skill" "$PROFILE_DIR/skills/$skill"
done

printf '%s\n' "launchbot-sync:ok:$PROFILE_DIR"
