#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$PROFILE_DIR" ]; then
  export HERMES_HOME="$PROFILE_DIR"
fi
EXPECT_MODEL_PROVIDER="${EXPECT_MODEL_PROVIDER:-anthropic}"
EXPECT_MODEL_DEFAULT="${EXPECT_MODEL_DEFAULT:-claude-sonnet-4-6}"
EXPECT_HOME_CHANNEL="${EXPECT_HOME_CHANNEL:-C0B32M34J3W}"
EXPECT_ALLOWED_CHANNELS="${EXPECT_ALLOWED_CHANNELS:-C0B32M34J3W,C0AJAUNCEL8,CF8PK6V4J}"
GATEWAY_LAUNCHD_LABEL="${LAUNCHBOT_GATEWAY_LAUNCHD_LABEL:-ai.hermes.gateway-$PROFILE}"
GATEWAY_SERVICE_NAME="${LAUNCHBOT_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

if [ -r "$PROFILE_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$PROFILE_DIR/.env"
  set +a
fi

EXPECT_PANTHEON_REPO_URL="${EXPECT_PANTHEON_REPO_URL:-git@github.com:staffany-eng/pantheon.git}"
EXPECT_PANTHEON_BRANCH="${EXPECT_PANTHEON_BRANCH:-develop}"
PANTHEON_REPO_DIR="${LAUNCHBOT_PANTHEON_REPO_DIR:-$PROFILE_DIR/source/pantheon}"
PANTHEON_STATUS_PATH="${LAUNCHBOT_PANTHEON_STATUS_PATH:-$PROFILE_DIR/runtime/pantheon-repo-status.json}"
PANTHEON_STATUS_MAX_AGE_SECONDS="${LAUNCHBOT_PANTHEON_STATUS_MAX_AGE_SECONDS:-172800}"
HELP_ARTICLE_VIDEO_REGISTRY_PATH="${LAUNCHBOT_VIDEO_PLACEMENT_REGISTRY:-$PROFILE_DIR/source/launchbot/skills/help-article-generator/references/video-placement-registry.json}"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

check_mcp_server() {
  server_name="$1"
  expected_count="$2"
  server_file="$3"
  mcp_out="$(hermes -p "$PROFILE" mcp test "$server_name" 2>&1)" && {
    count="$(printf '%s\n' "$mcp_out" | sed -nE 's/.*Tools discovered: ([0-9]+).*/\1/p' | tail -1)"
    [ "$count" = "$expected_count" ] || fail "mcp:$server_name:tools=${count:-unavailable}:expected=$expected_count"
    return 0
  }
  if printf '%s\n' "$mcp_out" | grep -Fq "StdioServerParameters"; then
    "$hermes_python" -m py_compile "$PROFILE_DIR/source/launchbot/runtime/mcp/$server_file" || fail "mcp:$server_name:py-compile-failed"
    return 0
  fi
  fail "mcp:$server_name:test-failed"
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

need_command hermes
need_command git
config_path="$(hermes -p "$PROFILE" config path 2>/dev/null)" || fail "hermes:config-path-failed"
[ -r "$config_path" ] || fail "hermes:config-unreadable"
hermes -p "$PROFILE" config check >/dev/null 2>&1 || fail "hermes:config-check-failed"
hermes_python="$HERMES_AGENT_DIR/venv/bin/python"
[ -x "$hermes_python" ] || fail "hermes:python-not-found"

case "$(uname -s)" in
  Darwin)
    need_command launchctl
    launchctl print "gui/$(id -u)/$GATEWAY_LAUNCHD_LABEL" >/dev/null 2>&1 || fail "gateway:not-running"
    ;;
  Linux)
    need_command systemctl
    systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME" || fail "gateway:not-running"
    ;;
  *)
    hermes -p "$PROFILE" gateway status >/dev/null 2>&1 || fail "gateway:status-failed"
    ;;
esac

"$hermes_python" - "$config_path" "$EXPECT_MODEL_PROVIDER" "$EXPECT_MODEL_DEFAULT" "$EXPECT_HOME_CHANNEL" "$EXPECT_ALLOWED_CHANNELS" <<'PY' || exit 1
import sys
from pathlib import Path

import yaml

config_path, expected_provider, expected_model, expected_home_channel, expected_allowed_channels = sys.argv[1:6]
config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

model = config.get("model") or {}
if model.get("provider") != expected_provider:
    fail("model:provider-unexpected")
if model.get("default") != expected_model:
    fail("model:default-unexpected")

security = config.get("security") or {}
if security.get("redact_secrets") is not True:
    fail("security:redact-secrets-not-enabled")

display = config.get("display") or {}
if display.get("interim_assistant_messages") is not False:
    fail("display:interim-assistant-messages-not-disabled")
if display.get("streaming") is not False:
    fail("display:streaming-not-disabled")
if display.get("tool_progress") != "off":
    fail("display:tool-progress-not-off")

slack = config.get("slack") or {}
if slack.get("require_mention") is not True:
    fail("slack:require-mention-not-enabled")
if slack.get("reactions") is not False:
    fail("slack:reactions-not-disabled")
if str(config.get("SLACK_HOME_CHANNEL") or "").strip('"') != expected_home_channel:
    fail("slack:home-channel-unexpected")
allowed = str(slack.get("allowed_channels") or "")
for channel_id in [item.strip() for item in expected_allowed_channels.split(",") if item.strip()]:
    if channel_id not in allowed:
        fail(f"slack:allowed-channel-missing:{channel_id}")

mcp_servers = config.get("mcp_servers") or {}
launchbot_ker = mcp_servers.get("launchbot_ker") or {}
tools = set(launchbot_ker.get("tool_allowlist") or [])
expected_tools = {"find_ker_ticket_from_slack_thread", "lookup_ker_ticket_by_key"}
if tools != expected_tools:
    fail("mcp:launchbot_ker:tool-allowlist-unexpected")

launchbot_feature_intake = mcp_servers.get("launchbot_feature_intake") or {}
feature_intake_tools = set(launchbot_feature_intake.get("tool_allowlist") or [])
expected_feature_intake_tools = {"preview_feature_intake_from_slack_thread", "create_feature_intake_from_slack_thread"}
if feature_intake_tools != expected_feature_intake_tools:
    fail("mcp:launchbot_feature_intake:tool-allowlist-unexpected")
feature_intake_policy = launchbot_feature_intake.get("access_policy") or {}
if feature_intake_policy.get("mode") != "confirmed_jpd_intake_create":
    fail("mcp:launchbot_feature_intake:mode-unexpected")
if feature_intake_policy.get("required_confirmation") != "create intake":
    fail("mcp:launchbot_feature_intake:confirmation-unexpected")
for key in ["no_slack_post_from_mcp", "no_jira_comments", "no_jira_transitions", "no_jira_assignment"]:
    if feature_intake_policy.get(key) is not True:
        fail(f"mcp:launchbot_feature_intake:{key}:must-be-true")

launchbot_help_article = mcp_servers.get("launchbot_help_article") or {}
video_tools = set(launchbot_help_article.get("tool_allowlist") or [])
expected_video_tools = {"preview_help_article_video_update", "create_help_article_video_update_draft"}
if video_tools != expected_video_tools:
    fail("mcp:launchbot_help_article:tool-allowlist-unexpected")
video_policy = launchbot_help_article.get("access_policy") or {}
if video_policy.get("mode") != "draft_only_registered_video_slots":
    fail("mcp:launchbot_help_article:mode-unexpected")
for key in ["allow_publish", "allow_delete", "allow_tag_mutation", "allow_collection_mutation"]:
    if video_policy.get(key) is not False:
        fail(f"mcp:launchbot_help_article:{key}:must-be-false")
PY

for key in \
  SLACK_BOT_TOKEN \
  JIRA_BASE_URL \
  JIRA_EMAIL \
  JIRA_API_TOKEN \
  LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN; do
  value="${!key:-}"
  [ -n "$value" ] || fail "env:$key:missing"
done

check_mcp_server launchbot_ker 2 launchbot_ker_server.py
check_mcp_server launchbot_feature_intake 2 launchbot_feature_intake_server.py
check_mcp_server launchbot_help_article 2 launchbot_help_article_server.py

[ -r "$HELP_ARTICLE_VIDEO_REGISTRY_PATH" ] || fail "help-article-video-registry:missing"
"$hermes_python" - "$HELP_ARTICLE_VIDEO_REGISTRY_PATH" <<'PY' || exit 1
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

try:
    registry = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    fail("help-article-video-registry:invalid-json")

if registry.get("version") != 1:
    fail("help-article-video-registry:version-unexpected")
articles = registry.get("articles")
if not isinstance(articles, list) or len(articles) < 3:
    fail("help-article-video-registry:articles-missing")
for article in articles:
    if article.get("locale") != "en":
        fail("help-article-video-registry:non-en-locale")
    if not article.get("intercom_article_id"):
        fail("help-article-video-registry:article-id-missing")
    slots = article.get("slots")
    if not isinstance(slots, list) or not slots:
        fail("help-article-video-registry:slot-missing")
    for slot in slots:
        if slot.get("provider") != "loom":
            fail("help-article-video-registry:provider-unexpected")
        if slot.get("replace_policy") != "replace_next_video_after_anchor":
            fail("help-article-video-registry:replace-policy-unexpected")
PY

[ -d "$PANTHEON_REPO_DIR/.git" ] || fail "pantheon:checkout-missing"
pantheon_remote="$(git -C "$PANTHEON_REPO_DIR" remote get-url origin 2>/dev/null)" || fail "pantheon:remote-unreadable"
[ "$pantheon_remote" = "$EXPECT_PANTHEON_REPO_URL" ] || fail "pantheon:remote-unexpected"
pantheon_branch="$(git -C "$PANTHEON_REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)" || fail "pantheon:branch-unreadable"
[ "$pantheon_branch" = "$EXPECT_PANTHEON_BRANCH" ] || fail "pantheon:branch-unexpected"
pantheon_status="$(git -C "$PANTHEON_REPO_DIR" status --porcelain=v1 2>/dev/null)" || fail "pantheon:status-unreadable"
[ -z "$pantheon_status" ] || fail "pantheon:dirty-checkout"
[ -r "$PANTHEON_STATUS_PATH" ] || fail "pantheon:status-json-missing"

"$hermes_python" - "$PANTHEON_STATUS_PATH" "$EXPECT_PANTHEON_REPO_URL" "$EXPECT_PANTHEON_BRANCH" "$PANTHEON_REPO_DIR" "$PANTHEON_STATUS_MAX_AGE_SECONDS" <<'PY' || exit 1
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path, expected_remote, expected_branch, expected_path, max_age_seconds = sys.argv[1:6]

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

try:
    status = json.loads(Path(status_path).read_text(encoding="utf-8"))
except Exception:
    fail("pantheon:status-json-invalid")

if status.get("remote") != expected_remote:
    fail("pantheon:status-remote-unexpected")
if status.get("branch") != expected_branch:
    fail("pantheon:status-branch-unexpected")
if status.get("path") != expected_path:
    fail("pantheon:status-path-unexpected")
sha = status.get("sha")
if not isinstance(sha, str) or len(sha) != 40:
    fail("pantheon:status-sha-invalid")
updated_at = status.get("updated_at")
if not isinstance(updated_at, str):
    fail("pantheon:status-updated-at-missing")
try:
    timestamp = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
except ValueError:
    fail("pantheon:status-updated-at-invalid")
age = (datetime.now(timezone.utc) - timestamp).total_seconds()
if age < 0:
    fail("pantheon:status-updated-at-future")
if age > int(max_age_seconds):
    fail("pantheon:status-stale")
PY
