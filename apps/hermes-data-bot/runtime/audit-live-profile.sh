#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-staffanydatabot}"
EXPECTED_MODEL_PROVIDER="${EXPECTED_MODEL_PROVIDER:-anthropic}"
EXPECTED_MODEL_DEFAULT="${EXPECTED_MODEL_DEFAULT:-claude-sonnet-4-6}"
EXPECTED_PERSONALITY="${EXPECTED_PERSONALITY:-concise}"
EXPECTED_HEALTH_CRON_NAME="${EXPECTED_HEALTH_CRON_NAME:-staffanydatabot health check}"
EXPECTED_CLOUD_HEARTBEAT_CRON_NAME="${EXPECTED_CLOUD_HEARTBEAT_CRON_NAME:-staffanydatabot local cloud heartbeat}"
EXPECTED_DIGEST_CRON_NAME="${EXPECTED_DIGEST_CRON_NAME:-staffanydatabot high-priority release feature usage digest}"
EXPECT_DIGEST_CRON="${EXPECT_DIGEST_CRON:-0}"
EXPECTED_MCP_TOOLS="${EXPECTED_MCP_TOOLS:-4}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
if [ -n "${HERMES_DATA_BOT_APP_ROOT:-}" ]; then
  APP_ROOT="$HERMES_DATA_BOT_APP_ROOT"
elif [ "$(basename "$SCRIPT_DIR")" = "runtime" ] && [ -f "$SCRIPT_DIR/../app.manifest.json" ]; then
  APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  APP_ROOT="$PROFILE_DIR/source/hermes-data-bot"
fi
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
need_command diff
need_command cmp

config_path="$(hermes -p "$PROFILE" config path 2>/dev/null)" || fail "hermes:config-path-failed"
[ -r "$config_path" ] || fail "hermes:config-unreadable"

cmp -s "$APP_ROOT/profile/SOUL.md" "$PROFILE_DIR/SOUL.md" || fail "profile-drift:soul"
diff -qr "$APP_ROOT/skills/staffany-data-bot" "$PROFILE_DIR/skills/staffany-data-bot" >/dev/null || fail "profile-drift:staffany-data-bot-skill"
cmp -s "$APP_ROOT/runtime/check-health.sh" "$PROFILE_DIR/scripts/staffanydatabot-check-health.sh" || fail "profile-drift:health-script"
cmp -s "$APP_ROOT/runtime/check-cloud-heartbeat.sh" "$PROFILE_DIR/scripts/staffanydatabot-check-cloud-heartbeat.sh" || fail "profile-drift:cloud-heartbeat-script"

hermes_python="$HERMES_AGENT_DIR/venv/bin/python"
[ -x "$hermes_python" ] || fail "hermes:python-not-found"

config_check_out="$(mktemp)"
trap 'rm -f "$config_check_out"' EXIT

if ! "$hermes_python" - "$config_path" "$HERMES_AGENT_DIR" \
  "$EXPECTED_MODEL_PROVIDER" "$EXPECTED_MODEL_DEFAULT" "$EXPECTED_PERSONALITY" \
  >"$config_check_out" 2>&1 <<'PY'
import sys

config_path, hermes_agent_dir, expected_provider, expected_model, expected_personality = sys.argv[1:6]
sys.path.insert(0, hermes_agent_dir)

try:
    import yaml
    from gateway.display_config import resolve_display_setting
except Exception as exc:
    print(f"dependency:hermes-config-parser-failed:{exc.__class__.__name__}")
    raise SystemExit(1)

with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

model = config.get("model") or {}
if model.get("provider") != expected_provider:
    print("model:provider-drift")
    raise SystemExit(1)
if model.get("default") != expected_model:
    print("model:default-drift")
    raise SystemExit(1)

display = config.get("display") or {}
if display.get("personality") != expected_personality:
    print("display:personality-drift")
    raise SystemExit(1)
if display.get("interim_assistant_messages") is not False:
    print("slack-display:interim-assistant-messages-not-disabled")
    raise SystemExit(1)
if resolve_display_setting(config, "slack", "tool_progress") != "off":
    print("slack-display:tool-progress-not-off")
    raise SystemExit(1)
if resolve_display_setting(config, "slack", "streaming") is not False:
    print("slack-display:streaming-not-disabled")
    raise SystemExit(1)

if ((config.get("slack") or {}).get("reactions")) is not False:
    print("slack:reactions-not-disabled")
    raise SystemExit(1)
if ((config.get("kanban") or {}).get("dispatch_in_gateway")) is not False:
    print("kanban:dispatch-in-gateway-not-disabled")
    raise SystemExit(1)
if ((config.get("security") or {}).get("redact_secrets")) is not True:
    print("security:redact-secrets-not-enabled")
    raise SystemExit(1)

server = ((config.get("mcp_servers") or {}).get("staffany_bigquery") or {})
tools = server.get("tools") or {}
allowlist = tools.get("include") or server.get("tool_allowlist") or []
expected_tools = [
    "list_dataset_ids",
    "list_table_ids",
    "get_table_info",
    "execute_sql_readonly",
]
if allowlist != expected_tools:
    print("mcp:staffany_bigquery-tool-allowlist-drift")
    raise SystemExit(1)
if tools.get("resources") is not False or tools.get("prompts") is not False:
    print("mcp:staffany_bigquery-resources-prompts-enabled")
    raise SystemExit(1)
PY
then
  fail "$(cat "$config_check_out")"
fi

cron_out="$(hermes -p "$PROFILE" cron list 2>&1)" || fail "cron:list-failed"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_HEALTH_CRON_NAME" || fail "cron:health-check-missing"
printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_CLOUD_HEARTBEAT_CRON_NAME" || fail "cron:cloud-heartbeat-missing"
if [ "$EXPECT_DIGEST_CRON" = "1" ]; then
  printf '%s\n' "$cron_out" | grep -Fq "$EXPECTED_DIGEST_CRON_NAME" || fail "cron:feature-usage-digest-missing"
fi

mcp_out="$(hermes -p "$PROFILE" mcp test staffany_bigquery 2>&1)" || fail "mcp:staffany_bigquery-test-failed"
printf '%s\n' "$mcp_out" | grep -q "Tools discovered: $EXPECTED_MCP_TOOLS" || fail "mcp:staffany_bigquery-tool-count-unexpected"

printf 'live-profile:audit-ok\n'
