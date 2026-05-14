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
LOG_TZ="${NURTUREANY_SLACK_SOCKET_LOG_TZ:-Asia/Singapore}"
INGRESS_CHECK_ENABLED="${NURTUREANY_SLACK_INGRESS_CHECK_ENABLED:-1}"
INGRESS_CHANNEL_ID="${NURTUREANY_SLACK_INGRESS_CHANNEL_ID:-${SLACK_HOME_CHANNEL:-}}"
INGRESS_LOOKBACK_SECONDS="${NURTUREANY_SLACK_INGRESS_LOOKBACK_SECONDS:-600}"
INGRESS_GRACE_SECONDS="${NURTUREANY_SLACK_INGRESS_GRACE_SECONDS:-60}"
INGRESS_LOG_TZ="${NURTUREANY_SLACK_INGRESS_LOG_TZ:-UTC}"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

timestamp_epoch() {
  local raw="$1"
  local normalized="${raw%%,*}"
  TZ="$LOG_TZ" date -d "$normalized" '+%s' 2>/dev/null || TZ="$LOG_TZ" date -j -f '%Y-%m-%d %H:%M:%S' "$normalized" '+%s' 2>/dev/null
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

restart_gateway() {
  local reason="$1"
  local detail="$2"

  if [ "$DRY_RUN" = "1" ]; then
    printf 'slack-socket:restart-needed %s %s\n' "$reason" "$detail"
    exit 0
  fi

  append_watchdog_log "restart profile=$PROFILE reason=$reason $detail"
  if ! sh -c "$RESTART_CMD" >/dev/null 2>&1; then
    append_watchdog_log "restart-failed profile=$PROFILE reason=$reason"
    fail "slack-socket:restart-failed"
  fi
}

check_recent_slack_ingress() {
  [ "$INGRESS_CHECK_ENABLED" = "1" ] || return 0
  [ -n "${SLACK_BOT_TOKEN:-}" ] || return 0
  [ -n "$INGRESS_CHANNEL_ID" ] || return 0
  [ -r "$LOG_FILE" ] || return 0

  python3 - "$LOG_FILE" "$INGRESS_CHANNEL_ID" "$INGRESS_LOOKBACK_SECONDS" "$INGRESS_GRACE_SECONDS" "$INGRESS_LOG_TZ" <<'PY'
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

log_file, channel_id, lookback_seconds, grace_seconds, log_tz = sys.argv[1:6]
lookback_seconds = int(lookback_seconds)
grace_seconds = int(grace_seconds)
token = os.environ.get("SLACK_BOT_TOKEN", "")
if not token:
    raise SystemExit(0)


def api(method, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"https://slack.com/api/{method}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fail_probe(reason):
    print(f"slack-ingress:probe-failed:{reason}")
    raise SystemExit(0)


auth = api("auth.test", {})
if not auth.get("ok"):
    fail_probe(auth.get("error") or "auth-test")
bot_user_id = auth.get("user_id")
if not bot_user_id:
    fail_probe("bot-user-missing")

now_epoch = int(os.environ.get("NURTUREANY_SLACK_SOCKET_NOW_EPOCH") or dt.datetime.now(dt.timezone.utc).timestamp())
oldest = max(0, now_epoch - lookback_seconds)
history = api(
    "conversations.history",
    {
        "channel": channel_id,
        "oldest": str(oldest),
        "latest": str(now_epoch),
        "inclusive": "true",
        "limit": "50",
    },
)
if not history.get("ok"):
    fail_probe(history.get("error") or "history")

mention_token = f"<@{bot_user_id}>"
latest_mention = None
for message in history.get("messages") or []:
    if message.get("bot_id") or message.get("subtype"):
        continue
    if message.get("user") == bot_user_id:
        continue
    text = message.get("text") or ""
    if mention_token not in text:
        continue
    try:
        message_epoch = int(float(message.get("ts") or "0"))
    except ValueError:
        continue
    if not latest_mention or message_epoch > latest_mention["epoch"]:
        latest_mention = {"epoch": message_epoch, "ts": message.get("ts") or ""}

if not latest_mention:
    raise SystemExit(0)

age = now_epoch - latest_mention["epoch"]
if age < grace_seconds:
    raise SystemExit(0)

replies = api("conversations.replies", {"channel": channel_id, "ts": latest_mention["ts"], "limit": "20"})
if replies.get("ok"):
    for reply in replies.get("messages") or []:
        try:
            reply_epoch = int(float(reply.get("ts") or "0"))
        except ValueError:
            continue
        if reply_epoch <= latest_mention["epoch"]:
            continue
        if reply.get("user") == bot_user_id or reply.get("bot_id"):
            raise SystemExit(0)

tzinfo = dt.timezone.utc
if log_tz != "UTC":
    try:
        from zoneinfo import ZoneInfo

        tzinfo = ZoneInfo(log_tz)
    except Exception:
        tzinfo = dt.timezone.utc

inbound_after_mention = False
timestamp_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
with open(log_file, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        if "inbound message: platform=slack" not in line:
            continue
        match = timestamp_pattern.match(line)
        if not match:
            continue
        try:
            log_epoch = int(dt.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=tzinfo).timestamp())
        except ValueError:
            continue
        if log_epoch >= latest_mention["epoch"]:
            inbound_after_mention = True

if inbound_after_mention:
    raise SystemExit(0)

print(f"slack-ingress:missed-mention message_ts={latest_mention['ts']} age_seconds={age}")
raise SystemExit(2)
PY
}

[ "$THRESHOLD_SECONDS" -ge 1 ] 2>/dev/null || fail "slack-socket:bad-threshold"
[ "$COOLDOWN_SECONDS" -ge 1 ] 2>/dev/null || fail "slack-socket:bad-cooldown"
[ "$INGRESS_LOOKBACK_SECONDS" -ge 1 ] 2>/dev/null || fail "slack-ingress:bad-lookback"
[ "$INGRESS_GRACE_SECONDS" -ge 1 ] 2>/dev/null || fail "slack-ingress:bad-grace"

if [ ! -r "$LOG_FILE" ]; then
  exit 0
fi

set +e
ingress_out="$(check_recent_slack_ingress)"
ingress_status="$?"
set -e
if [ "$ingress_status" -eq 2 ]; then
  current_epoch="$(now_epoch)"
  last_restart_stale_epoch="$(state_value last_stale_epoch || true)"
  last_restart_epoch="$(state_value last_restart_epoch || true)"
  ingress_epoch="$(printf '%s\n' "$ingress_out" | sed -nE 's/.*message_ts=([0-9]+)\..*/\1/p' | tail -1)"
  if [ -n "$ingress_epoch" ] && [ "$last_restart_stale_epoch" = "$ingress_epoch" ] && [ -n "$last_restart_epoch" ]; then
    since_restart=$((current_epoch - last_restart_epoch))
    if [ "$since_restart" -lt "$COOLDOWN_SECONDS" ]; then
      exit 0
    fi
  fi
  restart_gateway "missed-mention" "$ingress_out"
  if [ -n "$ingress_epoch" ]; then
    write_state "$ingress_epoch" "$current_epoch"
  fi
  exit 0
elif [ "$ingress_status" -ne 0 ]; then
  fail "slack-ingress:probe-error"
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

restart_gateway "stale-socket" "stale_age_seconds=$age_seconds"
write_state "$stale_epoch" "$current_epoch"
