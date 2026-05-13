#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-psmopsbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
GATEWAY_SERVICE_NAME="${PSM_OPS_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

if [ -r "$PROFILE_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$PROFILE_DIR/.env"
  set +a
fi

fail() {
  printf '%s\n' "$1"
  exit 1
}

if command -v systemctl >/dev/null 2>&1; then
  active="$(systemctl --user is-active "$GATEWAY_SERVICE_NAME" 2>/dev/null || true)"
  [ "$active" = "active" ] || fail "gateway_service:not-active:$GATEWAY_SERVICE_NAME"
fi

if command -v hermes >/dev/null 2>&1; then
  for server in psm_jira psm_c360; do
    out="$(hermes -p "$PROFILE" mcp test "$server" 2>&1 || true)"
    case "$server" in
      psm_jira) expected=13 ;;
      psm_c360) expected=3 ;;
    esac
    count="$(printf '%s\n' "$out" | sed -nE 's/.*Tools discovered: ([0-9]+).*/\1/p' | tail -1)"
    [ "$count" = "$expected" ] || fail "mcp:$server:tools=${count:-unavailable}:expected=$expected"
  done
else
  fail "hermes:not-found"
fi

config_path="$(hermes -p "$PROFILE" config path 2>/dev/null || true)"
if [ -n "$config_path" ] && [ -r "$config_path" ]; then
  grep -Eq 'provider: *"?anthropic"?' "$config_path" || fail "model:provider-not-anthropic"
  grep -q 'claude-sonnet-4-6' "$config_path" || fail "model:default-not-claude-sonnet-4-6"
  grep -q 'require_mention: *true' "$config_path" || fail "slack:require-mention-not-enabled"
  if [ -n "${SLACK_ALLOWED_CHANNELS:-}" ]; then
    fail "slack:allowed-channels-should-be-empty-for-open-channel-mode"
  fi
  grep -q 'max_parallel_jobs: *1' "$config_path" || fail "cron:max_parallel_jobs-not-1"
fi

for key in \
  JIRA_BASE_URL \
  JIRA_EMAIL \
  JIRA_API_TOKEN \
  PSM_OPS_JIRA_SERVICE_DESK_ID \
  CUSTOMER360_INTERNAL_API_TOKEN; do
  value="${!key:-}"
  [ -n "$value" ] || fail "env:$key:missing"
done

if [ "${PSM_OPS_JIRA_MODE:-}" != "thin_poc" ]; then
  for key in \
    PSM_OPS_ACCESS_POLICY_PATH \
    PSM_OPS_JIRA_FIELD_REMINDER_AT; do
    value="${!key:-}"
    [ -n "$value" ] || fail "env:$key:missing"
  done
fi

cron_jobs="$PROFILE_DIR/cron/jobs.json"
if [ -r "$cron_jobs" ] && command -v python3 >/dev/null 2>&1; then
  python3 - "$cron_jobs" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
jobs = payload.get("jobs") if isinstance(payload, dict) else payload
enabled = [job for job in jobs if isinstance(job, dict) and job.get("enabled") is True]
names = {str(job.get("name") or "") for job in enabled}
missing = [
    name
    for name in ["psmopsbot due-date reminders"]
    if name not in names
]
if missing:
    print(f"cron:missing:{','.join(missing)}")
    sys.exit(1)
PY
fi
