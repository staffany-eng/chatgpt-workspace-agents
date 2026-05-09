#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-staffanydatabot}"
HONCHO_HEALTH_URL="${HONCHO_HEALTH_URL:-http://localhost:8000/health}"
EXPECT_HONCHO="${EXPECT_HONCHO:-1}"
EXPECT_GATEWAY="${EXPECT_GATEWAY:-1}"
EXPECT_MCP_TOOLS="${EXPECT_MCP_TOOLS:-4}"

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

grep -Eq 'redact_secrets:[[:space:]]*true' "$config_path" || fail "security:redact_secrets-not-enabled"

if [ "$EXPECT_GATEWAY" = "1" ]; then
  hermes -p "$PROFILE" gateway status >/dev/null 2>&1 || fail "gateway:status-failed"
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
