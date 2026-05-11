#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: update-slack-allowlist.sh [--profile staffanydatabot] [--restart] USER_ID [USER_ID ...]

Adds Slack user IDs to the live Hermes profile SLACK_ALLOWED_USERS value.
The script creates a timestamped .env backup, dedupes IDs, and never prints
the full allowlist value.

Examples:
  apps/hermes-data-bot/runtime/update-slack-allowlist.sh U02RQTX3U0H
  apps/hermes-data-bot/runtime/update-slack-allowlist.sh --restart U0A6RLTV5EG UBMV40UUF
USAGE
}

profile="${HERMES_PROFILE:-staffanydatabot}"
restart=0
ids=()

while (($#)); do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --profile)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "missing value for --profile" >&2
        exit 2
      fi
      profile="$2"
      shift 2
      ;;
    --restart)
      restart=1
      shift
      ;;
    --)
      shift
      while (($#)); do
        ids+=("$1")
        shift
      done
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      ids+=("$1")
      shift
      ;;
  esac
done

if ((${#ids[@]} == 0)); then
  echo "provide at least one Slack user ID" >&2
  usage >&2
  exit 2
fi

for id in "${ids[@]}"; do
  if [[ ! "$id" =~ ^[UW][A-Z0-9]+$ ]]; then
    echo "invalid Slack user ID: $id" >&2
    exit 2
  fi
done

profile_home="${HERMES_PROFILE_HOME:-$HOME/.hermes/profiles/$profile}"
env_file="${HERMES_ENV_FILE:-$profile_home/.env}"

if [[ ! -f "$env_file" ]]; then
  echo "profile env file not found: $env_file" >&2
  exit 1
fi

current=""
if current_line="$(grep -E '^SLACK_ALLOWED_USERS=' "$env_file" || true)"; then
  current="${current_line#SLACK_ALLOWED_USERS=}"
fi

combined=()

add_id() {
  local candidate="$1"
  local existing
  candidate="${candidate//[[:space:]]/}"
  if [[ -z "$candidate" ]]; then
    return
  fi
  if ((${#combined[@]} > 0)); then
    for existing in "${combined[@]}"; do
      if [[ "$existing" == "$candidate" ]]; then
        return
      fi
    done
  fi
  combined+=("$candidate")
}

IFS=',' read -r -a current_ids <<< "$current"
for id in "${current_ids[@]}"; do
  add_id "$id"
done
for id in "${ids[@]}"; do
  add_id "$id"
done

new_value="$(IFS=,; echo "${combined[*]}")"
backup="${env_file}.backup-$(date +%Y%m%d%H%M%S)-slack-allowlist"
tmp="$(mktemp "${env_file}.tmp.XXXXXX")"

cp "$env_file" "$backup"
if mode="$(stat -f %Lp "$env_file" 2>/dev/null)"; then
  :
elif mode="$(stat -c %a "$env_file" 2>/dev/null)"; then
  :
else
  echo "could not read file mode for $env_file" >&2
  exit 1
fi

awk -v value="$new_value" '
  BEGIN { replaced = 0 }
  /^SLACK_ALLOWED_USERS=/ {
    if (!replaced) {
      print "SLACK_ALLOWED_USERS=" value
      replaced = 1
    }
    next
  }
  { print }
  END {
    if (!replaced) {
      print "SLACK_ALLOWED_USERS=" value
    }
  }
' "$env_file" > "$tmp"

chmod "$mode" "$tmp"
mv "$tmp" "$env_file"

echo "slack-allowlist-updated:${#combined[@]} users"
echo "backup:$backup"

if ((restart)); then
  hermes_bin="${HERMES_BIN:-}"
  if [[ -z "$hermes_bin" ]]; then
    if command -v hermes >/dev/null 2>&1; then
      hermes_bin="$(command -v hermes)"
    elif [[ -x "$HOME/.local/bin/hermes" ]]; then
      hermes_bin="$HOME/.local/bin/hermes"
    else
      echo "hermes command not found; restart the gateway manually" >&2
      exit 1
    fi
  fi
  "$hermes_bin" -p "$profile" gateway restart
fi
