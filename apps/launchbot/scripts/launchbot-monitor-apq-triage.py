#!/usr/bin/env python3
"""No-agent poller: scan #all-product-questions (CF8PK6V4J) for new top-level messages.

Outputs JSON of new messages to stdout when found (triggers agent triage delivery).
Silent (empty stdout) when nothing new to process.

State file: ~/.hermes/profiles/launchbot/runtime/apq-triage-state.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHANNEL_ID = os.environ.get("LAUNCHBOT_APQ_TRIAGE_CHANNEL_ID", "CF8PK6V4J")
PROFILE_DIR = Path(os.environ.get("HERMES_PROFILE_DIR", "/home/leekaiyi/.hermes/profiles/launchbot"))
STATE_PATH = Path(os.environ.get(
    "LAUNCHBOT_APQ_TRIAGE_STATE_PATH",
    str(PROFILE_DIR / "runtime" / "apq-triage-state.json"),
))
SLACK_API_BASE = "https://slack.com/api/"
SLACK_TIMEOUT = 15
DEFAULT_SINCE_SECONDS = 120  # fallback lookback when no prior state
OVERLAP_SECONDS = int(os.environ.get("LAUNCHBOT_APQ_TRIAGE_OVERLAP_SECONDS", "120"))


def _env_token() -> str:
    for name in ("SLACK_BOT_TOKEN", "SLACK_USER_TOKEN"):
        val = os.environ.get(name, "")
        if val:
            return val
    # Try loading from .env file
    env_file = PROFILE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("SLACK_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("SLACK_BOT_TOKEN not found in env or .env file")


def _slack_get(method: str, params: dict[str, Any]) -> dict[str, Any]:
    token = _env_token()
    url = SLACK_API_BASE + method + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=SLACK_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Slack API error: {exc}") from exc
    if not payload.get("ok"):
        raise RuntimeError(f"Slack error: {payload.get('error', 'unknown')}")
    return payload


def _load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "last_seen_ts": ""}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _ts_float(ts: str | float | None) -> float:
    try:
        return float(ts) if ts else 0.0
    except (TypeError, ValueError):
        return 0.0


def _is_bot_message(msg: dict[str, Any]) -> bool:
    return bool(msg.get("bot_id") or msg.get("subtype") == "bot_message")


def _is_thread_reply(msg: dict[str, Any]) -> bool:
    """True if this message is a reply inside a thread (not the root)."""
    ts = str(msg.get("ts") or "")
    thread_ts = str(msg.get("thread_ts") or "")
    return bool(thread_ts and thread_ts != ts)


def main() -> int:
    state = _load_state()
    last_seen_ts = _ts_float(state.get("last_seen_ts"))

    oldest: float
    if last_seen_ts > 0:
        oldest = max(0.0, last_seen_ts - OVERLAP_SECONDS)
    else:
        oldest = time.time() - DEFAULT_SINCE_SECONDS

    try:
        payload = _slack_get("conversations.history", {
            "channel": CHANNEL_ID,
            "oldest": f"{oldest:.6f}",
            "limit": 50,
            "inclusive": "false",
        })
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    messages = [m for m in payload.get("messages", []) if isinstance(m, dict)]
    messages.sort(key=lambda m: _ts_float(m.get("ts")))

    new_messages = []
    latest_ts = last_seen_ts

    for msg in messages:
        msg_ts = _ts_float(msg.get("ts"))
        if msg_ts <= last_seen_ts:
            continue
        if _is_bot_message(msg):
            # Still advance cursor past bot messages
            if msg_ts > latest_ts:
                latest_ts = msg_ts
            continue
        if _is_thread_reply(msg):
            # Only triage top-level posts (root messages)
            if msg_ts > latest_ts:
                latest_ts = msg_ts
            continue

        text = str(msg.get("text") or "").strip()
        if not text:
            if msg_ts > latest_ts:
                latest_ts = msg_ts
            continue

        new_messages.append({
            "channel_id": CHANNEL_ID,
            "ts": str(msg.get("ts") or ""),
            "thread_ts": str(msg.get("thread_ts") or msg.get("ts") or ""),
            "user": str(msg.get("user") or ""),
            "text": text,
        })
        if msg_ts > latest_ts:
            latest_ts = msg_ts

    if latest_ts > last_seen_ts:
        state["last_seen_ts"] = f"{latest_ts:.6f}"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

    if not new_messages:
        # Silent — nothing for agent to do
        return 0

    output = {
        "channel_id": CHANNEL_ID,
        "new_messages": new_messages,
        "count": len(new_messages),
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
