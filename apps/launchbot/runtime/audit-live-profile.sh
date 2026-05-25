#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
HERMES_PYTHON="${HERMES_PYTHON:-$HERMES_AGENT_DIR/venv/bin/python}"
HERMES_BIN="${HERMES_BIN:-$HERMES_AGENT_DIR/hermes}"
EXPECT_PANTHEON_REPO_URL="${EXPECT_PANTHEON_REPO_URL:-git@github.com:staffany-eng/pantheon.git}"
PANTHEON_SSH_KEY="${LAUNCHBOT_PANTHEON_SSH_KEY:-$PROFILE_DIR/ssh/pantheon_deploy_key}"
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
command -v bq >/dev/null 2>&1 || fail "dependency:bq:not-found"
[ -x "$HERMES_PYTHON" ] || fail "dependency:hermes-python:not-found"
[ -f "$HERMES_BIN" ] || fail "dependency:hermes-bin:not-found"

[ -d "$PROFILE_DIR" ] || fail "profile:not-found"
[ -d "$APP_ROOT" ] || fail "app-root:not-found"

cmp -s "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile-drift:soul"
cmp -s "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/launchbot-check-health.sh" || fail "profile-drift:health-script"
cmp -s "$APP_ROOT/runtime/audit-live-profile.sh" "$PROFILE_DIR/scripts/launchbot-audit-live-profile.sh" || fail "profile-drift:audit-script"
cmp -s "$APP_ROOT/runtime/update-pantheon-repo.sh" "$PROFILE_DIR/scripts/launchbot-update-pantheon-repo.sh" || fail "profile-drift:pantheon-update-script"
cmp -s "$APP_ROOT/runtime/monitor-feature-intake.py" "$PROFILE_DIR/scripts/launchbot-monitor-feature-intake.py" || fail "profile-drift:feature-intake-monitor-script"
cmp -s "$APP_ROOT/runtime/monitor-support-watch.py" "$PROFILE_DIR/scripts/launchbot-monitor-support-watch.py" || fail "profile-drift:support-watch-monitor-script"
cmp -s "$APP_ROOT/runtime/support-watch-whatsapp-refresh.sql" "$PROFILE_DIR/source/launchbot/runtime/support-watch-whatsapp-refresh.sql" || fail "profile-drift:support-watch-whatsapp-refresh-sql"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_ker_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_ker_server.py" || fail "profile-drift:ker-mcp"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_ifi_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_ifi_server.py" || fail "profile-drift:ifi-mcp"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_product_commitment_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_product_commitment_server.py" || fail "profile-drift:product-commitment-mcp"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_feature_intake_core.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_feature_intake_core.py" || fail "profile-drift:feature-intake-core"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_feature_intake_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_feature_intake_server.py" || fail "profile-drift:feature-intake-mcp"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_support_watch_core.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_support_watch_core.py" || fail "profile-drift:support-watch-core"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_support_watch_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_support_watch_server.py" || fail "profile-drift:support-watch-mcp"
cmp -s "$APP_ROOT/runtime/mcp/launchbot_help_article_server.py" "$PROFILE_DIR/source/launchbot/runtime/mcp/launchbot_help_article_server.py" || fail "profile-drift:help-article-mcp"
cmp -s "$APP_ROOT/skills/help-article-generator/references/video-placement-registry.json" "$PROFILE_DIR/source/launchbot/skills/help-article-generator/references/video-placement-registry.json" || fail "profile-drift:help-article-video-registry"

"$HERMES_PYTHON" - "$PROFILE_DIR" <<'PY' || exit 1
import json
import sys
from pathlib import Path

profile_dir = Path(sys.argv[1])
soul_path = profile_dir / "SOUL.md"
sessions_dir = profile_dir / "sessions"
sessions_index_path = sessions_dir / "sessions.json"


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


if soul_path.exists() and sessions_index_path.exists():
    soul = soul_path.read_text(encoding="utf-8")
    try:
        sessions = json.loads(sessions_index_path.read_text(encoding="utf-8"))
    except Exception:
        fail("sessions:index-invalid-json")
    for _, metadata in (sessions or {}).items():
        if not isinstance(metadata, dict):
            continue
        if metadata.get("expiry_finalized") or metadata.get("suspended"):
            continue
        session_id = str(metadata.get("session_id") or "")
        if not session_id:
            continue
        session_path = sessions_dir / f"session_{session_id}.json"
        if not session_path.exists():
            fail(f"sessions:active-session-json-missing:{session_id}")
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
        except Exception:
            fail(f"sessions:active-session-json-invalid:{session_id}")
        system_prompt = str(session.get("system_prompt") or "")
        if system_prompt and system_prompt != soul:
            origin = metadata.get("origin") or {}
            chat_id = origin.get("chat_id") or "unknown-chat"
            thread_id = origin.get("thread_id") or "unknown-thread"
            fail(f"sessions:stale-system-prompt:{session_id}:{chat_id}:{thread_id}")
PY
"$PROFILE_DIR/scripts/launchbot-check-health.sh" >/dev/null

cron_out="$("$HERMES_PYTHON" "$HERMES_BIN" -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "launchbot health check" || fail "cron:health-check-missing"
printf '%s\n' "$cron_out" | grep -Fq "launchbot feature intake monitor" || fail "cron:feature-intake-monitor-missing"
printf '%s\n' "$cron_out" | grep -Fq "launchbot support watch" || fail "cron:support-watch-missing"
if [ "$(bq ls --transfer_config --transfer_location=asia-southeast1 --project_id=staffany-warehouse --format=prettyjson 2>/dev/null | grep -F "Launchbot support watch WhatsApp native mirror refresh" | wc -l | tr -d ' ')" = "0" ]; then
  fail "bigquery:whatsapp-refresh-transfer-missing"
fi
if [ -r "$PANTHEON_SSH_KEY" ]; then
  export GIT_SSH_COMMAND="ssh -i $PANTHEON_SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
fi
if GIT_TERMINAL_PROMPT=0 git ls-remote "$EXPECT_PANTHEON_REPO_URL" HEAD >/dev/null 2>&1; then
  printf '%s\n' "$cron_out" | grep -Fq "launchbot pantheon repo update" || fail "cron:pantheon-repo-update-missing"
elif printf '%s\n' "$cron_out" | grep -Fq "launchbot pantheon repo update"; then
  fail "cron:pantheon-repo-update-present-without-github-ssh"
fi

printf 'live-profile:audit-ok\n'
