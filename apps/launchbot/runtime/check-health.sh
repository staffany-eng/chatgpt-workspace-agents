#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-launchbot}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$HOME/.hermes/profiles/$PROFILE" ]; then
  export HERMES_HOME="$HOME/.hermes/profiles/$PROFILE"
fi
EXPECT_MODEL_PROVIDER="${EXPECT_MODEL_PROVIDER:-anthropic}"
EXPECT_MODEL_DEFAULT="${EXPECT_MODEL_DEFAULT:-claude-sonnet-4-6}"
EXPECT_HOME_CHANNEL="${EXPECT_HOME_CHANNEL:-C0B32M34J3W}"
GATEWAY_LAUNCHD_LABEL="${LAUNCHBOT_GATEWAY_LAUNCHD_LABEL:-ai.hermes.gateway-$PROFILE}"
GATEWAY_SERVICE_NAME="${LAUNCHBOT_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

need_command hermes
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

"$hermes_python" - "$config_path" "$EXPECT_MODEL_PROVIDER" "$EXPECT_MODEL_DEFAULT" "$EXPECT_HOME_CHANNEL" <<'PY' || exit 1
import sys
from pathlib import Path

import yaml

config_path, expected_provider, expected_model, expected_home_channel = sys.argv[1:5]
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
PY
