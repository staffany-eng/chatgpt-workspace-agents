#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${HERMES_PYTHON:-$HOME/.hermes/hermes-agent/venv/bin/python}"
HONCHO_BASE_URL="${HONCHO_BASE_URL:-http://127.0.0.1:8000}"
HONCHO_WORKSPACE="${HONCHO_WORKSPACE:-staffany-hermes-data-bot}"
HONCHO_AI_PEER="${HONCHO_AI_PEER:-staffanydatabot}"
HONCHO_USER_PEER="${HONCHO_USER_PEER:-kaiyi}"
LIMIT="${LIMIT:-20}"
IDS_ONLY=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ids-only)
      IDS_ONLY=1
      shift
      ;;
    --limit)
      [ "$#" -ge 2 ] || {
        printf '%s\n' "usage: $0 [--ids-only] [--limit N]" >&2
        exit 2
      }
      LIMIT="$2"
      shift 2
      ;;
    *)
      printf '%s\n' "usage: $0 [--ids-only] [--limit N]" >&2
      exit 2
      ;;
  esac
done

[ -x "$PYTHON_BIN" ] || {
  printf '%s\n' "dependency:python:not-found at $PYTHON_BIN" >&2
  exit 1
}

"$PYTHON_BIN" - "$HONCHO_BASE_URL" "$HONCHO_WORKSPACE" "$HONCHO_AI_PEER" "$HONCHO_USER_PEER" "$LIMIT" "$IDS_ONLY" <<'PY'
import sys
from honcho import Honcho

base_url, workspace_name, ai_peer_name, user_peer_name, raw_limit, raw_ids_only = sys.argv[1:]
limit = int(raw_limit)
ids_only = raw_ids_only == "1"

client = Honcho(
    environment="local",
    base_url=base_url,
    api_key="local",
    workspace_id=workspace_name,
)
ai_peer = client.peer(ai_peer_name)

items = list(ai_peer.conclusions_of(user_peer_name).list(size=limit, reverse=True))

print(f"workspace={workspace_name}")
print(f"ai_peer={ai_peer_name}")
print(f"user_peer={user_peer_name}")
print(f"count={len(items)}")
if not ids_only:
    print("note=local review only; do not redirect raw memory output into the repo")

for item in items:
    if ids_only:
        print(item.id)
    else:
        content = getattr(item, "content", "")
        print(f"- id: {item.id}")
        print(f"  content: {content}")
PY
