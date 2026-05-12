#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-nurtureanysalesbot}"
if [ -z "${HERMES_HOME:-}" ] && [ -d "$HOME/.hermes/profiles/$PROFILE" ]; then
  export HERMES_HOME="$HOME/.hermes/profiles/$PROFILE"
fi

PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
LOG_FILE="${NURTUREANY_SLACK_SOCKET_LOG:-$PROFILE_DIR/logs/agent.log}"
STATE_DIR="${NURTUREANY_SLACK_SOCKET_STATE_DIR:-$PROFILE_DIR/state}"
STATE_FILE="${NURTUREANY_SLACK_SOCKET_STATE_FILE:-$STATE_DIR/slack-socket-watchdog.state}"
WATCHDOG_LOG="${NURTUREANY_SLACK_SOCKET_WATCHDOG_LOG:-$PROFILE_DIR/logs/slack-socket-watchdog.log}"
THRESHOLD_SECONDS="${NURTUREANY_SLACK_SOCKET_THRESHOLD_SECONDS:-300}"
COOLDOWN_SECONDS="${NURTUREANY_SLACK_SOCKET_RESTART_COOLDOWN_SECONDS:-300}"
RESTART_CMD="${NURTUREANY_SLACK_SOCKET_RESTART_CMD:-systemctl --user restart hermes-gateway-$PROFILE.service}"
DRY_RUN="${NURTUREANY_SLACK_SOCKET_DRY_RUN:-0}"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

timestamp_epoch() {
  local raw="$1"
  local normalized="${raw%%,*}"
  date -d "$normalized" '+%s' 2>/dev/null || date -j -f '%Y-%m-%d %H:%M:%S' "$normalized" '+%s' 2>/dev/null
}

last_matching_timestamp() {
  local pattern="$1"
  awk -v pattern="$pattern" '
    BEGIN { IGNORECASE = 1 }
    $0 ~ pattern { ts = $1 " " $2 }
    END { if (ts != "") print ts }
  ' "$LOG_FILE"
}

now_epoch() {
  if [ -n "${NURTUREANY_SLACK_SOCKET_NOW_EPOCH:-}" ]; then
    printf '%s\n' "$NURTUREANY_SLACK_SOCKET_NOW_EPOCH"
  else
    date '+%s'
  fi
}

state_value() {
  local key="$1"
  [ -r "$STATE_FILE" ] || return 0
  awk -F= -v key="$key" '$1 == key { value = $2 } END { if (value != "") print value }' "$STATE_FILE"
}

write_state() {
  local stale_epoch="$1"
  local restart_epoch="$2"
  mkdir -p "$STATE_DIR"
  {
    printf 'last_stale_epoch=%s\n' "$stale_epoch"
    printf 'last_restart_epoch=%s\n' "$restart_epoch"
  } >"$STATE_FILE"
}

append_watchdog_log() {
  mkdir -p "$(dirname "$WATCHDOG_LOG")"
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" >>"$WATCHDOG_LOG"
}

[ "$THRESHOLD_SECONDS" -ge 1 ] 2>/dev/null || fail "slack-socket:bad-threshold"
[ "$COOLDOWN_SECONDS" -ge 1 ] 2>/dev/null || fail "slack-socket:bad-cooldown"

if [ ! -r "$LOG_FILE" ]; then
  exit 0
fi

stale_ts="$(last_matching_timestamp 'seems to be stale|Failed to check current session|stale\. Reconnecting')"
[ -n "$stale_ts" ] || exit 0

good_ts="$(last_matching_timestamp 'A new session .* has been established|Socket Mode connected|✓ slack connected')"
stale_epoch="$(timestamp_epoch "$stale_ts")" || fail "slack-socket:stale-timestamp-parse-failed"
good_epoch=0
if [ -n "$good_ts" ]; then
  good_epoch="$(timestamp_epoch "$good_ts")" || fail "slack-socket:good-timestamp-parse-failed"
fi

if [ "$good_epoch" -ge "$stale_epoch" ]; then
  exit 0
fi

current_epoch="$(now_epoch)"
age_seconds=$((current_epoch - stale_epoch))
if [ "$age_seconds" -lt "$THRESHOLD_SECONDS" ]; then
  exit 0
fi

last_restart_stale_epoch="$(state_value last_stale_epoch || true)"
last_restart_epoch="$(state_value last_restart_epoch || true)"
if [ "$last_restart_stale_epoch" = "$stale_epoch" ] && [ -n "$last_restart_epoch" ]; then
  since_restart=$((current_epoch - last_restart_epoch))
  if [ "$since_restart" -lt "$COOLDOWN_SECONDS" ]; then
    exit 0
  fi
fi

if [ "$DRY_RUN" = "1" ]; then
  printf 'slack-socket:restart-needed stale_age_seconds=%s\n' "$age_seconds"
  exit 0
fi

append_watchdog_log "restart profile=$PROFILE stale_age_seconds=$age_seconds"
if ! sh -c "$RESTART_CMD" >/dev/null 2>&1; then
  append_watchdog_log "restart-failed profile=$PROFILE"
  fail "slack-socket:restart-failed"
fi
write_state "$stale_epoch" "$current_epoch"
