#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-nurtureanysalesbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
GATEWAY_SERVICE_NAME="${NURTUREANY_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"
GATEWAY_LAUNCHD_LABEL="${NURTUREANY_GATEWAY_LAUNCHD_LABEL:-ai.hermes.gateway-$PROFILE}"
NURTUREANY_DUPLICATE_PROFILE="${NURTUREANY_DUPLICATE_PROFILE:-nae2e}"
NURTUREANY_DUPLICATE_LAUNCHD_LABEL="${NURTUREANY_DUPLICATE_LAUNCHD_LABEL:-ai.hermes.gateway-$NURTUREANY_DUPLICATE_PROFILE}"
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATH="$HOME/.local/bin:$HERMES_AGENT_DIR:$PATH"
export PATH

line() {
  printf '%s\n' "$1"
}

status_value() {
  local value="$1"
  if [ -n "$value" ]; then
    printf '%s' "$value"
  else
    printf 'unknown'
  fi
}

process_commands() {
  if [ "$(uname -s)" = "Darwin" ]; then
    ps -axo command= 2>/dev/null || true
  else
    ps -eo command= 2>/dev/null || true
  fi
}

count_gateway_processes() {
  local profile="$1"
  process_commands | awk -v profile="$profile" '
    index($0, "hermes_cli.main") &&
    index($0, "--profile " profile " gateway run") {
      count += 1
    }
    END { print count + 0 }
  '
}

line "nurtureany-cloud-doctor:profile=$PROFILE"
line "host:$(hostname 2>/dev/null || printf 'unknown')"
line "kernel:$(uname -srm 2>/dev/null || printf 'unknown')"
line "profile_dir:$PROFILE_DIR"

case "$(uname -s)" in
  Linux)
    if command -v systemctl >/dev/null 2>&1; then
      active="$(systemctl --user is-active "$GATEWAY_SERVICE_NAME" 2>/dev/null || true)"
      substate="$(systemctl --user show "$GATEWAY_SERVICE_NAME" --property=SubState --value 2>/dev/null || true)"
      line "gateway_service:systemd:$GATEWAY_SERVICE_NAME:active=$(status_value "$active"):substate=$(status_value "$substate")"
    else
      line "gateway_service:systemd:systemctl-not-found"
    fi
    ;;
  Darwin)
    if command -v launchctl >/dev/null 2>&1 && launchctl print "gui/$(id -u)/$GATEWAY_LAUNCHD_LABEL" >/dev/null 2>&1; then
      line "gateway_service:launchctl:$GATEWAY_LAUNCHD_LABEL:loaded"
    else
      line "gateway_service:launchctl:$GATEWAY_LAUNCHD_LABEL:not-loaded"
    fi
    ;;
  *)
    line "gateway_service:unsupported-os"
    ;;
esac

if command -v pgrep >/dev/null 2>&1; then
  pids="$(pgrep -af "hermes.*gateway.*$PROFILE" 2>/dev/null | sed -E 's/(SLACK|HUBSPOT|EAZYBE|LUSHA|PROSPEO|EXA|TAVILY|GOOGLE)_[A-Z0-9_]*=[^ ]+/\1_[redacted]/g' | head -20 || true)"
  if [ -n "$pids" ]; then
    line "gateway_pids:"
    printf '%s\n' "$pids"
  else
    line "gateway_pids:none"
  fi
else
  line "gateway_pids:pgrep-not-found"
fi

nurtureany_gateway_count="$(count_gateway_processes "nurtureanysalesbot")"
duplicate_gateway_count="$(count_gateway_processes "$NURTUREANY_DUPLICATE_PROFILE")"
line "gateway_duplicate_check:nurtureanysalesbot_processes=$nurtureany_gateway_count:$NURTUREANY_DUPLICATE_PROFILE=$duplicate_gateway_count"
if [ "$(uname -s)" = "Darwin" ] && command -v launchctl >/dev/null 2>&1; then
  if launchctl print "gui/$(id -u)/$NURTUREANY_DUPLICATE_LAUNCHD_LABEL" >/dev/null 2>&1; then
    line "gateway_duplicate_launchd:$NURTUREANY_DUPLICATE_LAUNCHD_LABEL:loaded"
  else
    line "gateway_duplicate_launchd:$NURTUREANY_DUPLICATE_LAUNCHD_LABEL:not-loaded"
  fi
fi

if command -v hermes >/dev/null 2>&1; then
  for server in staffany_bigquery hubspot_nurtureany aircall_nurtureany google_calendar_nurtureany google_drive_nurtureany eazybe_nurtureany luma_nurtureany public_research_nurtureany lusha_nurtureany prospeo_nurtureany exa_nurtureany near_me_nurtureany; do
    out="$(hermes -p "$PROFILE" mcp test "$server" 2>&1 || true)"
    count="$(printf '%s\n' "$out" | sed -nE 's/.*Tools discovered: ([0-9]+).*/\1/p' | tail -1)"
    if [ -n "$count" ]; then
      line "mcp:$server:tools=$count"
    else
      line "mcp:$server:unavailable"
    fi
  done
else
  line "hermes:not-found"
fi

cron_jobs="$PROFILE_DIR/cron/jobs.json"
if [ -r "$cron_jobs" ] && command -v python3 >/dev/null 2>&1; then
  python3 - "$cron_jobs" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
jobs = payload.get("jobs") if isinstance(payload, dict) else payload
enabled = [job for job in jobs if isinstance(job, dict) and job.get("enabled") is True]
missing_tz = [str(job.get("name") or "") for job in enabled if not job.get("timezone")]
event_roi_enabled = [str(job.get("name") or "") for job in enabled if str(job.get("name") or "").startswith("event-roi-")]
unsafe_send = [str(job.get("name") or "") for job in enabled if "send_message" in str(job.get("prompt") or "")]
print(f"cron:enabled={len(enabled)}:missing_timezone={len(missing_tz)}:event_roi_enabled={len(event_roi_enabled)}:unsafe_send_message={len(unsafe_send)}")
for label, values in [("cron_missing_timezone", missing_tz), ("cron_event_roi_enabled", event_roi_enabled), ("cron_unsafe_send_message", unsafe_send)]:
    if values:
        print(f"{label}:{','.join(values[:10])}")
PY
else
  line "cron:jobs-json-unavailable"
fi

if [ -r "$PROFILE_DIR/operation-ledger" ] || [ -d "$PROFILE_DIR/operation-ledger" ]; then
  count="$(find "$PROFILE_DIR/operation-ledger" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
  line "operation_ledger:files=$count"
else
  line "operation_ledger:not-found"
fi

if [ -r "$PROFILE_DIR/lesson-candidates" ] || [ -d "$PROFILE_DIR/lesson-candidates" ]; then
  count="$(find "$PROFILE_DIR/lesson-candidates" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
  line "lesson_candidates:files=$count"
else
  line "lesson_candidates:not-found"
fi
