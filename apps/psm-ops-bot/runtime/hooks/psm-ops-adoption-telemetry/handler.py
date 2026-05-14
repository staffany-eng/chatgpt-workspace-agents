"""Hermes gateway hook for PSM Ops adoption telemetry."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]+)\b"),
    re.compile(r"\b(xapp-[A-Za-z0-9-]+)\b"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{12,})\b"),
    re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{10,}"),
    re.compile(r"(?i)(['\"]?[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Z0-9_]*['\"]?\s*[:=]\s*)['\"]?[^'\"\s,}]+['\"]?"),
]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _metrics_path() -> Path:
    configured = _env("PSM_OPS_ADOPTION_METRICS_PATH")
    if configured:
        return Path(configured).expanduser()
    profile_home = Path(_env("HERMES_HOME") or Path.home() / ".hermes" / "profiles" / "psmopsbot")
    return profile_home / "metrics" / "psm-ops-adoption.jsonl"


def _redact(value: Any) -> str:
    text = "" if value is None else str(value)
    for pattern in SECRET_PATTERNS:
        if "(?:TOKEN|SECRET|PASSWORD|API_KEY)" in pattern.pattern:
            text = pattern.sub(lambda match: f"{match.group(1)}[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text


def _preview(value: Any, limit: int = 500) -> str:
    text = _redact(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + " ...[truncated]"


def _confidence_from_response(response: str) -> str:
    normalized = response.lower()
    for value in ("blocked", "needs-check", "verified"):
        if f"confidence: {value}" in normalized or f'"confidence": "{value}"' in normalized:
            return value
    return ""


async def handle(event_type: str, context: dict[str, Any]):
    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "platform": context.get("platform", ""),
        "user_id": context.get("user_id", ""),
        "session_id": context.get("session_id", ""),
        "session_key": context.get("session_key", ""),
    }
    if "message" in context:
        message = context.get("message") or ""
        entry["message_chars"] = len(str(message))
        entry["message_preview"] = _preview(message)
    if "response" in context:
        response = context.get("response") or ""
        entry["response_chars"] = len(str(response))
        entry["response_preview"] = _preview(response)
        confidence = _confidence_from_response(str(response))
        if confidence:
            entry["response_confidence"] = confidence
            entry["blocked"] = confidence == "blocked"
    if "tool_names" in context:
        names = [str(name) for name in context.get("tool_names") or [] if str(name)]
        entry["tool_names"] = names
        entry["psm_tool_names"] = [
            name for name in names
            if "pco" in name or "ps_wee" in name or "c360" in name or name.startswith("psm_")
        ]
    if "iteration" in context:
        entry["iteration"] = context.get("iteration")

    path = _metrics_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle_file:
            handle_file.write(json.dumps(entry, ensure_ascii=True, default=str) + "\n")
    except OSError:
        return
