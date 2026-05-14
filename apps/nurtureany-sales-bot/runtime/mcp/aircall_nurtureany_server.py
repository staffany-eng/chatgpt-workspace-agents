#!/usr/bin/env python3
"""Read-only Aircall call review MCP adapter for NurtureAny Sales Bot.

This server reads bounded Aircall call metadata and can transcribe one selected
recording through OpenAI. It never returns raw phone numbers, recording URLs, or
audio bytes, and downloaded audio is deleted before the tool returns.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import socket
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.responses import blocked_response, safe_detail


AIRCALL_BASE_URL = "https://api.aircall.io/v1"
OPENAI_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"
USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
TIMEOUT_SECONDS = 30
MAX_CALLS = 5
MAX_LOOKUP_CALLS = 50
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_AUDIO_SECONDS = 60 * 60
MAX_TRANSCRIPT_CHARS = 12000
MAX_SEGMENTS = 80
DEFAULT_MODEL = "gpt-4o-transcribe-diarize"
DEFAULT_MATCH_TIMESTAMP_TOLERANCE_SECONDS = 5 * 60
DEFAULT_MATCH_DURATION_TOLERANCE_SECONDS = 10


mcp = FastMCP(
    "aircall_nurtureany",
    instructions=(
        "Read-only Aircall call review tools for NurtureAny. Fetch bounded call "
        "metadata, bounded selected-call matching, and selected-call "
        "transcription only. Never expose raw phone numbers, recording URLs, "
        "audio bytes, or secrets."
    ),
)


class AircallError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _blocked(message: str, scope: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return blocked_response(message, "Aircall API / OpenAI audio transcription", scope, **extra)


def _aircall_credentials() -> tuple[str, str]:
    api_id = os.environ.get("AIRCALL_API_ID", "").strip()
    api_token = os.environ.get("AIRCALL_API_TOKEN", "").strip()
    if not api_id or not api_token:
        raise AircallError("Missing AIRCALL_API_ID or AIRCALL_API_TOKEN.")
    return api_id, api_token


def _openai_key() -> str:
    token = os.environ.get("OPENAI_API_KEY", "").strip()
    if not token:
        raise AircallError("Missing OPENAI_API_KEY.")
    return token


def _auth_header() -> str:
    api_id, api_token = _aircall_credentials()
    encoded = base64.b64encode(f"{api_id}:{api_token}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _redact(value: str, max_chars: int = 500) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[phone]", text)
    text = re.sub(r"https?://\S+", "[url]", text)
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


def _bounded_int(value: int | str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _optional_int(value: int | str | None, field_name: str, minimum: int, maximum: int) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise AircallError(f"{field_name} must be an integer.") from error
    return max(minimum, min(parsed, maximum))


def _normalize_aircall_timestamp(value: str | int | float | None, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{10}", text):
        return text
    if re.fullmatch(r"\d{13}", text):
        return str(int(text) // 1000)
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        parsed = float(text)
        if parsed <= 0:
            raise AircallError(f"{field_name} must be a positive UNIX timestamp or ISO datetime.")
        return str(int(parsed))
    normalized = text.replace("Z", "+00:00")
    try:
        parsed_dt = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise AircallError(f"{field_name} must be a UNIX timestamp or ISO datetime.") from error
    if parsed_dt.tzinfo is None:
        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
    return str(int(parsed_dt.astimezone(timezone.utc).timestamp()))


def _timestamp_int(value: str | int | float | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(_normalize_aircall_timestamp(value, "timestamp"))
    except AircallError:
        return None


def _call_started_unix(call: dict[str, Any]) -> int | None:
    return _timestamp_int(call.get("started_at") or call.get("answered_at") or call.get("created_at"))


def _call_duration_seconds(call: dict[str, Any]) -> int | None:
    duration = call.get("duration")
    if isinstance(duration, (int, float)):
        return int(duration)
    try:
        return int(str(duration))
    except (TypeError, ValueError):
        return None


def _call_user_text(call: dict[str, Any]) -> str:
    user = call.get("user") if isinstance(call.get("user"), dict) else {}
    values = [user.get("name"), user.get("email"), user.get("id")]
    return " ".join(str(value or "") for value in values).lower()


def _filter_selected_call_matches(
    calls: list[dict[str, Any]],
    match_started_at_unix: str,
    match_user_name: str,
    match_duration_seconds: int | None,
    timestamp_tolerance_seconds: int,
    duration_tolerance_seconds: int,
) -> list[dict[str, Any]]:
    user_query = str(match_user_name or "").strip().lower()
    target_started_at = _timestamp_int(match_started_at_unix)
    matched: list[dict[str, Any]] = []
    for call in calls:
        if user_query and user_query not in _call_user_text(call):
            continue
        if target_started_at is not None:
            started_at = _call_started_unix(call)
            if started_at is None or abs(started_at - target_started_at) > timestamp_tolerance_seconds:
                continue
        if match_duration_seconds is not None:
            duration = _call_duration_seconds(call)
            if duration is None or abs(duration - match_duration_seconds) > duration_tolerance_seconds:
                continue
        matched.append(call)
    return matched


def _aircall_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    url = f"{AIRCALL_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={"Authorization": _auth_header(), "Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AircallError(f"Aircall API failed: {error.code} {safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise AircallError(f"Aircall API request timed out or failed: {reason}") from error


def _call_url_value(call: dict[str, Any]) -> str:
    for key in ("recording", "recording_short_url", "asset"):
        value = call.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
        if isinstance(value, dict):
            for nested in ("url", "link", "download_url"):
                nested_value = value.get(nested)
                if isinstance(nested_value, str) and nested_value.startswith("http"):
                    return nested_value
    return ""


def _safe_call(call: dict[str, Any]) -> dict[str, Any]:
    user = call.get("user") if isinstance(call.get("user"), dict) else {}
    number = call.get("number") if isinstance(call.get("number"), dict) else {}
    duration = call.get("duration")
    recording_url = _call_url_value(call)
    return {
        "aircall_call_id": str(call.get("id") or ""),
        "started_at": call.get("started_at") or call.get("answered_at") or call.get("created_at") or "",
        "answered_at": call.get("answered_at") or "",
        "ended_at": call.get("ended_at") or "",
        "duration_seconds": duration if isinstance(duration, (int, float)) else None,
        "direction": call.get("direction") or "",
        "status": call.get("status") or "",
        "missed_call_reason": call.get("missed_call_reason") or "",
        "user_id": str(user.get("id") or ""),
        "user_name": _redact(" ".join([str(user.get("name") or ""), str(user.get("email") or "")]).strip(), 120),
        "number_name": _redact(str(number.get("name") or ""), 120),
        "recording_available": bool(recording_url),
        "raw_recording_url_returned": False,
        "phone_numbers_returned": False,
    }


def _download_recording(recording_url: str) -> tuple[Path, int, str]:
    suffix = Path(urllib.parse.urlparse(recording_url).path).suffix or ".mp3"
    fd, temp_path = tempfile.mkstemp(prefix="nurtureany-aircall-", suffix=suffix)
    os.close(fd)
    path = Path(temp_path)
    size = 0
    request = urllib.request.Request(recording_url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response, path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_AUDIO_BYTES:
                    raise AircallError("Aircall recording exceeds the 25 MB transcription cap.")
                handle.write(chunk)
            content_type = response.headers.get("content-type") or mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, size, content_type


def _multipart_body(fields: dict[str, str], file_field: str, file_path: Path, content_type: str) -> tuple[bytes, str]:
    boundary = f"----nurtureany{int(time.time() * 1000)}"
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        chunks.append(str(value).encode())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode()
    )
    chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    chunks.append(file_path.read_bytes())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def _openai_transcribe(file_path: Path, content_type: str, model: str) -> dict[str, Any]:
    fields = {
        "model": model or DEFAULT_MODEL,
        "response_format": "diarized_json" if (model or DEFAULT_MODEL) == DEFAULT_MODEL else "json",
    }
    if (model or DEFAULT_MODEL) == DEFAULT_MODEL:
        fields["chunking_strategy"] = "auto"
    body, boundary = _multipart_body(fields, "file", file_path, content_type)
    request = urllib.request.Request(
        OPENAI_TRANSCRIPTIONS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {_openai_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AircallError(f"OpenAI transcription failed: {error.code} {safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise AircallError(f"OpenAI transcription timed out or failed: {reason}") from error


def _safe_transcript_payload(payload: dict[str, Any], include_segments: bool, max_segments: int) -> dict[str, Any]:
    raw_segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    segment_limit = _bounded_int(max_segments, 20, 1, MAX_SEGMENTS)
    safe_segments = []
    for segment in raw_segments[:segment_limit]:
        safe_segments.append(
            {
                "speaker": str(segment.get("speaker") or "speaker"),
                "start": segment.get("start"),
                "end": segment.get("end"),
                "text": _redact(str(segment.get("text") or ""), 500),
            }
        )
    text = str(payload.get("text") or "")
    if not text and raw_segments:
        text = " ".join(str(segment.get("text") or "") for segment in raw_segments)
    redacted_text = _redact(text, MAX_TRANSCRIPT_CHARS)
    return {
        "transcript_text_redacted": redacted_text if include_segments else "",
        "segments": safe_segments if include_segments else [],
        "segment_count_returned": len(safe_segments) if include_segments else 0,
        "segment_count_total": len(raw_segments),
        "text_char_count_redacted": len(redacted_text),
        "raw_transcript_returned": bool(include_segments),
        "raw_audio_retained": False,
    }


@mcp.tool()
def find_aircall_calls(
    slack_user_email: str,
    limit: int = 5,
    from_timestamp: str = "",
    to_timestamp: str = "",
    order: str = "desc",
    match_started_at: str = "",
    match_user_name: str = "",
    match_duration_seconds: int | str | None = None,
    timestamp_tolerance_seconds: int = DEFAULT_MATCH_TIMESTAMP_TOLERANCE_SECONDS,
    duration_tolerance_seconds: int = DEFAULT_MATCH_DURATION_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    """Find recent Aircall calls and return safe metadata only.

    Optional match_* fields perform a bounded selected-call lookup over safe
    metadata when HubSpot has no Aircall external ID.
    """

    safe_limit = _bounded_int(limit, 5, 1, MAX_CALLS)
    safe_timestamp_tolerance = _bounded_int(
        timestamp_tolerance_seconds,
        DEFAULT_MATCH_TIMESTAMP_TOLERANCE_SECONDS,
        0,
        60 * 60,
    )
    safe_duration_tolerance = _bounded_int(
        duration_tolerance_seconds,
        DEFAULT_MATCH_DURATION_TOLERANCE_SECONDS,
        0,
        10 * 60,
    )
    selected_match_mode = bool(match_started_at or match_user_name or str(match_duration_seconds or "").strip())
    scope = {
        "caller_email": slack_user_email,
        "requested_limit": safe_limit,
        "from_timestamp_input": str(from_timestamp or "").strip(),
        "to_timestamp_input": str(to_timestamp or "").strip(),
        "from_timestamp": "",
        "to_timestamp": "",
        "order": "asc" if str(order).lower() == "asc" else "desc",
        "selected_call_match": selected_match_mode,
        "match_started_at_input": str(match_started_at or "").strip(),
        "match_started_at": "",
        "match_user_name": _redact(str(match_user_name or ""), 120),
        "match_duration_seconds": None,
        "timestamp_tolerance_seconds": safe_timestamp_tolerance,
        "duration_tolerance_seconds": safe_duration_tolerance,
        "read_only": True,
        "raw_recording_urls_returned": False,
        "phone_numbers_returned": False,
    }
    try:
        if from_timestamp:
            scope["from_timestamp"] = _normalize_aircall_timestamp(from_timestamp, "from_timestamp")
        if to_timestamp:
            scope["to_timestamp"] = _normalize_aircall_timestamp(to_timestamp, "to_timestamp")
        if match_started_at:
            scope["match_started_at"] = _normalize_aircall_timestamp(match_started_at, "match_started_at")
        scope["match_duration_seconds"] = _optional_int(
            match_duration_seconds,
            "match_duration_seconds",
            0,
            24 * 60 * 60,
        )

        if selected_match_mode and scope["match_started_at"] and not scope["from_timestamp"] and not scope["to_timestamp"]:
            target_dt = datetime.fromtimestamp(int(scope["match_started_at"]), timezone.utc)
            scope["from_timestamp"] = str(int((target_dt - timedelta(seconds=safe_timestamp_tolerance)).timestamp()))
            scope["to_timestamp"] = str(int((target_dt + timedelta(seconds=safe_timestamp_tolerance)).timestamp()))
            scope["order"] = "asc"

        params: dict[str, Any] = {
            "per_page": MAX_LOOKUP_CALLS if selected_match_mode else safe_limit,
            "order": scope["order"],
        }
        if scope["from_timestamp"]:
            params["from"] = scope["from_timestamp"]
        if scope["to_timestamp"]:
            params["to"] = scope["to_timestamp"]
        payload = _aircall_get("/calls", params)
        calls = payload.get("calls") if isinstance(payload.get("calls"), list) else []
        candidate_count = len(calls)
        if selected_match_mode:
            calls = _filter_selected_call_matches(
                calls,
                scope["match_started_at"],
                match_user_name,
                scope["match_duration_seconds"],
                safe_timestamp_tolerance,
                safe_duration_tolerance,
            )
        safe_calls = [_safe_call(call) for call in calls[:safe_limit]]
        return {
            "answer": {
                "calls": safe_calls,
                "call_count": len(safe_calls),
                "candidate_call_count": candidate_count,
                "recording_available_count": sum(1 for call in safe_calls if call.get("recording_available")),
                "selected_call_match": selected_match_mode,
                "will_mutate_aircall": False,
            },
            "source": "Aircall Public API /v1/calls",
            "scope": scope,
            "confidence": "verified" if safe_calls else "needs-check",
            "caveat": "Safe metadata only. Timestamps sent to Aircall use UNIX seconds. Raw phone numbers, recording URLs, audio bytes, and transcripts were not returned.",
        }
    except AircallError as error:
        return _blocked(str(error), scope)


@mcp.tool()
def transcribe_aircall_recording(
    slack_user_email: str,
    aircall_call_id: str,
    include_segments: bool = False,
    max_segments: int = 20,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Transcribe one selected Aircall recording through OpenAI, then delete audio."""

    call_id = str(aircall_call_id or "").strip()
    scope = {
        "caller_email": slack_user_email,
        "aircall_call_id": call_id,
        "model": model or DEFAULT_MODEL,
        "max_audio_bytes": MAX_AUDIO_BYTES,
        "max_audio_seconds": MAX_AUDIO_SECONDS,
        "include_segments": include_segments,
        "read_only": True,
        "raw_recording_url_returned": False,
        "raw_audio_retained": False,
    }
    if not re.fullmatch(r"\d+", call_id):
        return _blocked("aircall_call_id must be a numeric Aircall call ID.", scope)
    temp_path: Path | None = None
    try:
        payload = _aircall_get(f"/calls/{call_id}")
        call = payload.get("call") if isinstance(payload.get("call"), dict) else payload
        if not isinstance(call, dict):
            return _blocked("Aircall call lookup returned an unexpected payload.", scope)
        safe_call = _safe_call(call)
        duration = safe_call.get("duration_seconds")
        if isinstance(duration, (int, float)) and duration > MAX_AUDIO_SECONDS:
            return _blocked("Aircall call exceeds the 60-minute transcription cap.", {**scope, "duration_seconds": duration})
        recording_url = _call_url_value(call)
        if not recording_url:
            return _blocked("Selected Aircall call has no recording URL available.", scope, call=safe_call)
        temp_path, audio_bytes, content_type = _download_recording(recording_url)
        transcript = _openai_transcribe(temp_path, content_type, model or DEFAULT_MODEL)
        safe_transcript = _safe_transcript_payload(transcript, include_segments, max_segments)
        return {
            "answer": {
                "call": safe_call,
                "transcription": safe_transcript,
                "audio_bytes_processed": audio_bytes,
                "recording_downloaded_temporarily": True,
                "raw_recording_url_returned": False,
                "raw_audio_retained": False,
                "will_mutate_aircall": False,
            },
            "source": "Aircall selected recording plus OpenAI /v1/audio/transcriptions",
            "scope": {**scope, "audio_bytes_processed": audio_bytes},
            "confidence": "verified",
            "caveat": "Audio was downloaded transiently and deleted before return. Transcript text is redacted and bounded; do not paste raw call transcripts into Slack or HubSpot.",
        }
    except AircallError as error:
        return _blocked(str(error), scope)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    mcp.run("stdio")
