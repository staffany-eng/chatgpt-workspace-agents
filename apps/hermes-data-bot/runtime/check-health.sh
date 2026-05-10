#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-staffanydatabot}"
HONCHO_HEALTH_URL="${HONCHO_HEALTH_URL:-http://localhost:8000/health}"
EXPECT_HONCHO="${EXPECT_HONCHO:-1}"
EXPECT_GATEWAY="${EXPECT_GATEWAY:-1}"
EXPECT_MCP_TOOLS="${EXPECT_MCP_TOOLS:-4}"
EXPECT_MODEL_AUTH="${EXPECT_MODEL_AUTH:-1}"
CHECK_GATEWAY_AUTH_LOGS="${CHECK_GATEWAY_AUTH_LOGS:-1}"

PATH="$HOME/.local/bin:$HOME/.hermes/hermes-agent:$PATH"
export PATH

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

need_command hermes

config_path="$(hermes -p "$PROFILE" config path 2>/dev/null)" || fail "hermes:config-path-failed"
[ -r "$config_path" ] || fail "hermes:config-unreadable"
hermes_agent_dir="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
hermes_python="$hermes_agent_dir/venv/bin/python"
[ -x "$hermes_python" ] || fail "hermes:python-not-found"

grep -Eq 'redact_secrets:[[:space:]]*true' "$config_path" || fail "security:redact_secrets-not-enabled"

config_check_out="$tmp_dir/config-check.out"
if ! "$hermes_python" - "$config_path" "$hermes_agent_dir" >"$config_check_out" 2>&1 <<'PY'
import sys

config_path, hermes_agent_dir = sys.argv[1], sys.argv[2]
sys.path.insert(0, hermes_agent_dir)

try:
    import yaml
    from gateway.display_config import resolve_display_setting
except Exception as exc:
    print(f"dependency:hermes-config-parser-failed:{exc.__class__.__name__}")
    raise SystemExit(1)

with open(config_path, "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

if resolve_display_setting(config, "slack", "tool_progress") != "off":
    print("slack-display:tool-progress-not-off")
    raise SystemExit(1)

if ((config.get("kanban") or {}).get("dispatch_in_gateway")) is not False:
    print("kanban:dispatch-in-gateway-not-disabled")
    raise SystemExit(1)
PY
then
  fail "$(cat "$config_check_out")"
fi

if [ "$EXPECT_GATEWAY" = "1" ]; then
  hermes -p "$PROFILE" gateway status >/dev/null 2>&1 || fail "gateway:status-failed"
fi

if [ "$EXPECT_MODEL_AUTH" = "1" ]; then
  auth_out="$tmp_dir/auth.out"
  if ! hermes -p "$PROFILE" auth status openai-codex >"$auth_out" 2>&1; then
    fail "model-auth:openai-codex-status-failed"
  fi
  grep -q "openai-codex: logged in" "$auth_out" || fail "model-auth:openai-codex-not-logged-in"

  auth_list_out="$tmp_dir/auth-list.out"
  if ! hermes -p "$PROFILE" auth list >"$auth_list_out" 2>&1; then
    fail "model-auth:credential-list-failed"
  fi
  if awk '
    /^openai-codex[[:space:]]/ { in_provider=1; next }
    /^[^[:space:]].*\([0-9]+ credentials\):/ && in_provider { in_provider=0 }
    in_provider && /auth failed|token_invalidated|invalidated|re-auth/ { bad=1 }
    END { exit bad ? 0 : 1 }
  ' "$auth_list_out"; then
    fail "model-auth:openai-codex-credential-invalidated"
  fi
fi

if [ "$CHECK_GATEWAY_AUTH_LOGS" = "1" ] && command -v systemctl >/dev/null 2>&1 && command -v journalctl >/dev/null 2>&1; then
  svc="hermes-gateway-$PROFILE.service"
  active_since="$(systemctl --user show "$svc" -p ActiveEnterTimestamp --value 2>/dev/null || true)"
  if [ -n "$active_since" ]; then
    logs_out="$tmp_dir/gateway-auth.log"
    journalctl --user -u "$svc" --since "$active_since" --no-pager >"$logs_out" 2>/dev/null || true
    if grep -Eq 'token_invalidated|No Codex credentials|AuthenticationError|HTTP 401' "$logs_out"; then
      fail "model-auth:recent-gateway-auth-error"
    fi
  fi
fi

mcp_out="$tmp_dir/mcp.out"
if ! hermes -p "$PROFILE" mcp test staffany_bigquery >"$mcp_out" 2>&1; then
  fail "mcp:staffany_bigquery-test-failed"
fi
grep -q "Tools discovered: $EXPECT_MCP_TOOLS" "$mcp_out" || fail "mcp:staffany_bigquery-tool-count-unexpected"

if [ "$EXPECT_HONCHO" = "1" ]; then
  need_command curl
  curl -fsS "$HONCHO_HEALTH_URL" >/dev/null || fail "honcho:health-failed"

  memory_out="$tmp_dir/memory.out"
  if ! hermes -p "$PROFILE" memory status >"$memory_out" 2>&1; then
    fail "memory:status-failed"
  fi
  grep -Eq 'Provider:[[:space:]]+honcho' "$memory_out" || fail "memory:honcho-not-active"
  grep -Eq 'Status:[[:space:]]+available' "$memory_out" || fail "memory:honcho-not-available"
fi
