#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-staffanydatabot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
DATA_GATEWAY_SERVICE="${DATA_GATEWAY_SERVICE:-hermes-gateway-staffanydatabot.service}"
LAUNCHBOT_GATEWAY_SERVICE="${LAUNCHBOT_GATEWAY_SERVICE:-hermes-gateway-launchbot.service}"
EXPECTED_BIGQUERY_MCP_TOOLS="${EXPECTED_BIGQUERY_MCP_TOOLS:-4}"
EXPECTED_SLACK_CONTEXT_MCP_TOOLS="${EXPECTED_SLACK_CONTEXT_MCP_TOOLS:-2}"
EXPECTED_C360_MCP_TOOLS="${EXPECTED_C360_MCP_TOOLS:-1}"
EXPECTED_ENABLED_CRON_COUNT="${EXPECTED_ENABLED_CRON_COUNT:-3}"
SLACK_CONTEXT_SMOKE_PERMALINK="${STAFFANY_DATA_BOT_SLACK_CONTEXT_SMOKE_PERMALINK:-https://staffany.slack.com/archives/C0A0V39AK44/p1778814810682959}"

PATH="$HOME/.local/bin:$HOME/.hermes/hermes-agent/venv/bin:$HOME/.hermes/hermes-agent:$PATH"
export PATH

if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -d "/run/user/$(id -u)" ]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

line() {
  printf '%s\n' "$1"
}

fail() {
  line "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

check_user_service() {
  local service_name="$1"
  local active enabled
  active="$(systemctl --user is-active "$service_name" 2>/dev/null || true)"
  enabled="$(systemctl --user is-enabled "$service_name" 2>/dev/null || true)"
  line "gateway_service:systemd:$service_name:active=$active:enabled=$enabled"
  [ "$active" = "active" ] || fail "gateway:not-active:$service_name"
  [ "$enabled" = "enabled" ] || fail "gateway:not-enabled:$service_name"
}

check_mcp_tools() {
  local server_name="$1"
  local expected_count="$2"
  local out
  out="$(mktemp)"
  if ! hermes -p "$PROFILE" mcp test "$server_name" >"$out" 2>&1; then
    rm -f "$out"
    fail "mcp:$server_name:test-failed"
  fi
  if ! grep -q "Tools discovered: $expected_count" "$out"; then
    rm -f "$out"
    fail "mcp:$server_name:tool-count-unexpected"
  fi
  rm -f "$out"
  line "mcp:$server_name:tools=$expected_count"
}

need_command systemctl
need_command python3
need_command hermes

line "staffanydatabot-cloud-doctor:profile=$PROFILE"
if [ -r "$PROFILE_DIR/VERSION" ]; then
  version_raw="$(tr '\n' ' ' <"$PROFILE_DIR/VERSION" | sed 's/[[:space:]]*$//')"
  line "version:$version_raw"
else
  line "version:missing"
fi

check_user_service "$DATA_GATEWAY_SERVICE"
check_user_service "$LAUNCHBOT_GATEWAY_SERVICE"

cron_json="$PROFILE_DIR/cron/jobs.json"
[ -r "$cron_json" ] || fail "cron:jobs-json-missing"
python3 - "$cron_json" "$EXPECTED_ENABLED_CRON_COUNT" <<'PY'
import json
import sys

jobs_path, expected_count = sys.argv[1:3]
try:
    with open(jobs_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
except Exception:
    print("cron:jobs-json-unreadable")
    raise SystemExit(1)

jobs = raw.get("jobs", raw) if isinstance(raw, dict) else raw
if not isinstance(jobs, list):
    print("cron:jobs-json-invalid")
    raise SystemExit(1)

enabled = [job for job in jobs if isinstance(job, dict) and job.get("enabled", True)]
deliver_null = sum(1 for job in jobs if isinstance(job, dict) and job.get("deliver", []) is None)
missing_timezone = sum(1 for job in enabled if not job.get("timezone"))
unsafe_send = sum(
    1
    for job in enabled
    if isinstance(job.get("prompt"), str) and "chat.postMessage" in job.get("prompt", "")
)
print(
    f"cron:enabled={len(enabled)}:expected={expected_count}:deliver_null={deliver_null}:"
    f"missing_timezone={missing_timezone}:unsafe_send_message={unsafe_send}"
)
if len(enabled) != int(expected_count) or deliver_null or unsafe_send:
    raise SystemExit(1)
PY

check_mcp_tools "staffany_bigquery" "$EXPECTED_BIGQUERY_MCP_TOOLS"
check_mcp_tools "staffany_slack_context" "$EXPECTED_SLACK_CONTEXT_MCP_TOOLS"
check_mcp_tools "staffany_c360" "$EXPECTED_C360_MCP_TOOLS"

python3 - "$PROFILE_DIR/.env" "$SLACK_CONTEXT_SMOKE_PERMALINK" <<'PY'
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

env_path = Path(sys.argv[1])
permalink = sys.argv[2]
values = {}
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

token = values.get("SLACK_BOT_TOKEN", "")
if not token:
    print("slack:selected-thread:blocked:missing-token")
    raise SystemExit(1)

match = re.search(r"/archives/([A-Z0-9]+)/p(\d{10})(\d{6})", permalink)
if not match:
    print("slack:selected-thread:blocked:bad-permalink")
    raise SystemExit(1)

channel = match.group(1)
thread_ts = f"{match.group(2)}.{match.group(3)}"
params = urllib.parse.urlencode({"channel": channel, "ts": thread_ts, "limit": "2"})
request = urllib.request.Request(
    f"https://slack.com/api/conversations.replies?{params}",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
)
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    print(f"slack:selected-thread:blocked:{exc.__class__.__name__}")
    raise SystemExit(1)

if not payload.get("ok"):
    error = str(payload.get("error") or "unknown_error")
    print(f"slack:selected-thread:blocked:{error}")
    raise SystemExit(1)

messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
print(f"slack:selected-thread:ok:channel={channel}:messages={len(messages)}")
PY
