#!/usr/bin/env python3
"""Read-only Aircall call review MCP adapter for NurtureAny Sales Bot.

This server reads bounded Aircall call metadata and can transcribe one selected
recording through OpenAI. It can also produce a safe coaching review from one
selected recording. It never returns raw phone numbers, recording URLs, or audio
bytes, and downloaded audio is deleted before the tool returns.
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
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
TIMEOUT_SECONDS = 30
MAX_CALLS = 5
MAX_LOOKUP_CALLS = 50
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_AUDIO_SECONDS = 60 * 60
MAX_TRANSCRIPT_CHARS = 12000
MAX_SEGMENTS = 80
DEFAULT_MODEL = "gpt-4o-transcribe-diarize"
DEFAULT_CALL_COACH_PROVIDER = "openai"
DEFAULT_CALL_COACH_REASONING_MODEL = "gpt-5.5"
DEFAULT_CALL_COACH_ELEVENLABS_ENABLED = "false"
DEFAULT_MATCH_TIMESTAMP_TOLERANCE_SECONDS = 5 * 60
DEFAULT_MATCH_DURATION_TOLERANCE_SECONDS = 10
CALL_COACH_SCORE_DIMENSIONS = [
    "discovery",
    "I-C-BANT",
    "talk ratio",
    "interactivity",
    "patience",
    "monologue length",
    "objections",
    "next step",
    "CRM hygiene",
    "customer reaction moments",
    "StaffAny value framing",
]
QUESTION_RE = re.compile(
    r"\?|^\s*(who|what|when|where|why|how|can|could|would|do|does|did|is|are|will|should)\b",
    re.IGNORECASE,
)
NEXT_STEP_RE = re.compile(
    r"\b(next|follow(?: |-)?up|meeting|meet|demo|call|send|share|schedule|book|confirm|calendar|invite)\b",
    re.IGNORECASE,
)
DATE_TIME_RE = re.compile(
    r"\b(today|tomorrow|mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|"
    r"sat(?:urday)?|sun(?:day)?|next week|this week|\d{1,2}(?::\d{2})?\s?(?:am|pm)?|\d{1,2}[/-]\d{1,2})\b",
    re.IGNORECASE,
)
OBJECTION_PATTERNS = {
    "pricing": re.compile(r"\b(price|pricing|cost|expensive|budget|afford|roi)\b", re.IGNORECASE),
    "incumbent": re.compile(r"\b(already|using|current tool|incumbent|competitor|vendor)\b", re.IGNORECASE),
    "timing": re.compile(r"\b(not now|later|busy|no time|next quarter|timeline)\b", re.IGNORECASE),
    "authority": re.compile(r"\b(boss|management|director|owner|approval|approve|decision)\b", re.IGNORECASE),
    "fit": re.compile(r"\b(no need|not interested|custom|build ourselves|issue|problem|concern|risk)\b", re.IGNORECASE),
}
HIDDEN_EMOTION_REWRITES = [
    (re.compile(r"\b(angry|furious|mad)\b", re.IGNORECASE), "showed observable friction"),
    (re.compile(r"\b(frustrated|upset|annoyed|irritated)\b", re.IGNORECASE), "showed friction"),
    (re.compile(r"\b(confused|lost)\b", re.IGNORECASE), "asked for clarification"),
    (re.compile(r"\b(happy|excited|delighted)\b", re.IGNORECASE), "responded positively"),
    (re.compile(r"\b(anxious|worried|nervous)\b", re.IGNORECASE), "raised concern"),
]


mcp = FastMCP(
    "aircall_nurtureany",
    instructions=(
        "Read-only Aircall call review tools for NurtureAny. Fetch bounded call "
        "metadata, bounded selected-call matching, and selected-call "
        "transcription/coaching only. Never expose raw phone numbers, recording "
        "URLs, audio bytes, raw transcripts, or secrets."
    ),
)


class AircallError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _blocked(message: str, scope: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return blocked_response(message, "Aircall API / OpenAI audio transcription and coaching", scope, **extra)


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


def _call_coach_provider() -> str:
    return os.environ.get("NURTUREANY_CALL_COACH_PROVIDER", DEFAULT_CALL_COACH_PROVIDER).strip().lower() or "openai"


def _call_coach_transcribe_model() -> str:
    return os.environ.get("NURTUREANY_CALL_COACH_TRANSCRIBE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _call_coach_reasoning_model() -> str:
    return (
        os.environ.get("NURTUREANY_CALL_COACH_REASONING_MODEL", DEFAULT_CALL_COACH_REASONING_MODEL).strip()
        or DEFAULT_CALL_COACH_REASONING_MODEL
    )


def _call_coach_elevenlabs_enabled() -> bool:
    return (
        os.environ.get("NURTUREANY_CALL_COACH_ELEVENLABS_ENABLED", DEFAULT_CALL_COACH_ELEVENLABS_ENABLED)
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _segment_duration(segment: dict[str, Any]) -> float | None:
    start = _as_float(segment.get("start"))
    end = _as_float(segment.get("end"))
    if start is None or end is None or end < start:
        return None
    return end - start


def _format_timestamp(value: Any) -> str:
    seconds = _as_float(value)
    if seconds is None:
        return "call-level"
    rounded = int(round(seconds))
    minutes, second = divmod(rounded, 60)
    return f"{minutes:02d}:{second:02d}"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _safe_segments_for_analysis(payload: dict[str, Any], max_segments: int = MAX_SEGMENTS) -> list[dict[str, Any]]:
    raw_segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    safe_segments = _safe_transcript_payload(payload, True, max_segments).get("segments", [])
    segments: list[dict[str, Any]] = []
    for index, segment in enumerate(safe_segments):
        text = str(segment.get("text") or "")
        duration = _segment_duration(segment)
        segments.append(
            {
                "ref": f"seg_{index + 1}",
                "speaker": str(segment.get("speaker") or "speaker"),
                "start": segment.get("start"),
                "end": segment.get("end"),
                "timestamp": _format_timestamp(segment.get("start")),
                "duration_seconds": round(duration, 2) if duration is not None else None,
                "word_count": _word_count(text),
                "text": text,
            }
        )
    if not segments and payload.get("text"):
        segments.append(
            {
                "ref": "seg_1",
                "speaker": "speaker",
                "start": None,
                "end": None,
                "timestamp": "call-level",
                "duration_seconds": None,
                "word_count": _word_count(str(payload.get("text") or "")),
                "text": _redact(str(payload.get("text") or ""), MAX_TRANSCRIPT_CHARS),
            }
        )
    if len(raw_segments) > len(segments):
        return segments
    return segments


def _speaker_units(segment: dict[str, Any], basis: str) -> float:
    if basis == "seconds":
        duration = segment.get("duration_seconds")
        return float(duration) if isinstance(duration, (int, float)) else 0.0
    return float(segment.get("word_count") or 0)


def _find_objection_moments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    moments: list[dict[str, Any]] = []
    for segment in segments:
        text = str(segment.get("text") or "")
        categories = [name for name, pattern in OBJECTION_PATTERNS.items() if pattern.search(text)]
        if not categories:
            continue
        moments.append(
            {
                "timestamp": segment.get("timestamp") or "call-level",
                "segment_ref": segment.get("ref") or "",
                "speaker": segment.get("speaker") or "speaker",
                "categories": categories,
                "evidence": _redact(text, 180),
            }
        )
    return moments[:8]


def _detect_next_step(segments: list[dict[str, Any]]) -> dict[str, Any]:
    next_step_segments: list[dict[str, Any]] = []
    strong_segments: list[dict[str, Any]] = []
    for segment in segments:
        text = str(segment.get("text") or "")
        if not NEXT_STEP_RE.search(text):
            continue
        next_step_segments.append(segment)
        if DATE_TIME_RE.search(text):
            strong_segments.append(segment)
    chosen = strong_segments[0] if strong_segments else (next_step_segments[0] if next_step_segments else None)
    status = "strong" if strong_segments else ("partial" if next_step_segments else "missing")
    return {
        "status": status,
        "timestamp": chosen.get("timestamp") if chosen else "call-level",
        "segment_ref": chosen.get("ref") if chosen else "",
        "evidence": _redact(str(chosen.get("text") or ""), 180) if chosen else "No clear next step found in selected segments.",
    }


def _customer_reaction_moments(
    segments: list[dict[str, Any]],
    dominant_speaker: str,
    objection_moments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    moments: list[dict[str, Any]] = []
    for segment in segments:
        speaker = str(segment.get("speaker") or "speaker")
        text = str(segment.get("text") or "")
        if speaker == dominant_speaker:
            continue
        words = _word_count(text)
        if 0 < words <= 5:
            moments.append(
                {
                    "timestamp": segment.get("timestamp") or "call-level",
                    "segment_ref": segment.get("ref") or "",
                    "cue": "short answer",
                    "evidence": _redact(text, 120),
                }
            )
        if QUESTION_RE.search(text):
            moments.append(
                {
                    "timestamp": segment.get("timestamp") or "call-level",
                    "segment_ref": segment.get("ref") or "",
                    "cue": "follow-up question",
                    "evidence": _redact(text, 160),
                }
            )
    for previous, current in zip(segments, segments[1:]):
        previous_end = _as_float(previous.get("end"))
        current_start = _as_float(current.get("start"))
        if previous_end is None or current_start is None:
            continue
        gap = current_start - previous_end
        if gap >= 2.5:
            moments.append(
                {
                    "timestamp": _format_timestamp(previous_end),
                    "segment_ref": f"{previous.get('ref', '')}->{current.get('ref', '')}",
                    "cue": "silence gap",
                    "evidence": f"{round(gap, 1)}s gap before next turn",
                }
            )
    categories: dict[str, int] = {}
    for moment in objection_moments:
        for category in moment.get("categories", []):
            categories[category] = categories.get(category, 0) + 1
    for category, count in categories.items():
        if count > 1:
            moments.append(
                {
                    "timestamp": "call-level",
                    "segment_ref": "",
                    "cue": "repeated objection",
                    "evidence": f"{category} objection appeared {count} times",
                }
            )
    return moments[:10]


def _compute_interaction_metrics(segments: list[dict[str, Any]]) -> dict[str, Any]:
    has_timing = any(isinstance(segment.get("duration_seconds"), (int, float)) for segment in segments)
    basis = "seconds" if has_timing else "word_count"
    speaker_units: dict[str, float] = {}
    speaker_segments: dict[str, int] = {}
    turn_count = 0
    previous_speaker = ""
    overlap_count = 0
    for index, segment in enumerate(segments):
        speaker = str(segment.get("speaker") or "speaker")
        speaker_units[speaker] = speaker_units.get(speaker, 0.0) + _speaker_units(segment, basis)
        speaker_segments[speaker] = speaker_segments.get(speaker, 0) + 1
        if speaker != previous_speaker:
            turn_count += 1
            previous_speaker = speaker
        if index > 0:
            previous_end = _as_float(segments[index - 1].get("end"))
            current_start = _as_float(segment.get("start"))
            if previous_end is not None and current_start is not None and current_start < previous_end:
                overlap_count += 1

    total_units = sum(speaker_units.values())
    speaker_metrics = []
    for speaker, units in sorted(speaker_units.items(), key=lambda item: item[1], reverse=True):
        speaker_metrics.append(
            {
                "speaker": speaker,
                "talk_units": round(units, 2),
                "talk_ratio": round(units / total_units, 3) if total_units > 0 else 0,
                "segment_count": speaker_segments.get(speaker, 0),
            }
        )
    dominant_speaker = speaker_metrics[0]["speaker"] if speaker_metrics else "speaker"

    longest_run_speaker = ""
    longest_run_units = 0.0
    longest_run_refs: list[str] = []
    current_speaker = ""
    current_units = 0.0
    current_refs: list[str] = []
    for segment in segments:
        speaker = str(segment.get("speaker") or "speaker")
        units = _speaker_units(segment, basis)
        if speaker != current_speaker:
            if current_units > longest_run_units:
                longest_run_speaker = current_speaker
                longest_run_units = current_units
                longest_run_refs = current_refs
            current_speaker = speaker
            current_units = units
            current_refs = [str(segment.get("ref") or "")]
        else:
            current_units += units
            current_refs.append(str(segment.get("ref") or ""))
    if current_units > longest_run_units:
        longest_run_speaker = current_speaker
        longest_run_units = current_units
        longest_run_refs = current_refs

    question_segments = [
        {
            "timestamp": segment.get("timestamp") or "call-level",
            "segment_ref": segment.get("ref") or "",
            "speaker": segment.get("speaker") or "speaker",
            "evidence": _redact(str(segment.get("text") or ""), 160),
        }
        for segment in segments
        if QUESTION_RE.search(str(segment.get("text") or ""))
    ]
    objection_moments = _find_objection_moments(segments)
    next_step = _detect_next_step(segments)
    total_seconds = sum(float(segment.get("duration_seconds") or 0.0) for segment in segments)
    turns_per_minute = round(turn_count / (total_seconds / 60), 2) if total_seconds > 0 else None
    return {
        "analysis_basis": "redacted diarized transcript segments and timestamps",
        "interaction_cue_status": "Interaction cues checked from transcript/timing",
        "tone_audio_cues": "audio-native tone not checked",
        "talk_ratio_basis": basis,
        "duration_seconds_estimated": round(total_seconds, 2) if total_seconds > 0 else None,
        "speaker_metrics": speaker_metrics,
        "dominant_speaker": dominant_speaker,
        "turn_count": turn_count,
        "turns_per_minute": turns_per_minute,
        "interactivity": "high" if turn_count >= 18 else ("medium" if turn_count >= 8 else "low"),
        "question_count": len(question_segments),
        "question_examples": question_segments[:6],
        "objection_moments": objection_moments,
        "next_step_clarity": next_step,
        "longest_monologue": {
            "basis": basis,
            "speaker": longest_run_speaker or "speaker",
            "units": round(longest_run_units, 2),
            "segment_refs": [ref for ref in longest_run_refs if ref],
        },
        "patience_proxy": {
            "overlap_count": overlap_count,
            "status": "possible overlap detected" if overlap_count else "no timestamp overlap detected",
        },
        "customer_reaction_moments": _customer_reaction_moments(segments, dominant_speaker, objection_moments),
    }


def _json_schema_object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


CALL_COACHING_SCHEMA = _json_schema_object(
    {
        "answer": {"type": "string"},
        "scorecard": {
            "type": "array",
            "minItems": len(CALL_COACH_SCORE_DIMENSIONS),
            "maxItems": len(CALL_COACH_SCORE_DIMENSIONS),
            "items": _json_schema_object(
                {
                    "dimension": {"type": "string", "enum": CALL_COACH_SCORE_DIMENSIONS},
                    "score": {"type": "integer", "enum": [0, 1, 2]},
                    "evidence": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "segment_ref": {"type": "string"},
                },
                ["dimension", "score", "evidence", "timestamp", "segment_ref"],
            ),
        },
        "coachable_moments": {
            "type": "array",
            "maxItems": 6,
            "items": _json_schema_object(
                {
                    "timestamp": {"type": "string"},
                    "segment_ref": {"type": "string"},
                    "note": {"type": "string"},
                    "coaching_point": {"type": "string"},
                },
                ["timestamp", "segment_ref", "note", "coaching_point"],
            ),
        },
        "interaction_cues": _json_schema_object(
            {
                "status": {"type": "string"},
                "tone_audio_cues": {"type": "string"},
                "talk_ratio": {"type": "string"},
                "interactivity": {"type": "string"},
                "longest_monologue": {"type": "string"},
                "question_count": {"type": "string"},
                "objections": {"type": "string"},
                "next_step_clarity": {"type": "string"},
                "customer_reaction_moments": {"type": "string"},
            },
            [
                "status",
                "tone_audio_cues",
                "talk_ratio",
                "interactivity",
                "longest_monologue",
                "question_count",
                "objections",
                "next_step_clarity",
                "customer_reaction_moments",
            ],
        ),
        "manager_coaching_note": _json_schema_object(
            {
                "praise": {"type": "string"},
                "correction": {"type": "string"},
                "practice_assignment": {"type": "string"},
                "next_action": {"type": "string"},
            },
            ["praise", "correction", "practice_assignment", "next_action"],
        ),
        "next_action": {"type": "string"},
        "source": {"type": "string"},
        "scope": {"type": "string"},
        "confidence": {"type": "string", "enum": ["verified", "needs-check", "blocked"]},
        "caveat": {"type": "string"},
    },
    [
        "answer",
        "scorecard",
        "coachable_moments",
        "interaction_cues",
        "manager_coaching_note",
        "next_action",
        "source",
        "scope",
        "confidence",
        "caveat",
    ],
)


def _call_coaching_system_prompt() -> str:
    dimensions = ", ".join(CALL_COACH_SCORE_DIMENSIONS)
    return (
        "You are NurtureAny's StaffAny sales-call coach. Review one selected post-call Aircall artifact. "
        "Use HubSpot context as CRM truth when provided. Aircall/OpenAI are call-artifact enrichment only. "
        "Gong is product-pattern inspiration only; do not claim Gong integration, API use, data source, or parity. "
        "ElevenLabs is future/benchmark evidence only; do not claim ElevenLabs integration or source use. "
        "Return manager-quality coaching, not a transcript. Never include raw transcript blocks, phone numbers, emails, "
        "recording URLs, or audio references. Score exactly these dimensions using 0 missed, 1 partial, 2 strong: "
        f"{dimensions}. Evidence must cite timestamps or safe segment refs. Tone/audio: this run only has "
        "transcript/timing interaction evidence, so interaction_cues.tone_audio_cues must say 'audio-native tone not checked'. "
        "Do not infer hidden emotions as fact. Rewrite emotion claims into observable behavior such as shorter answers, "
        "follow-up questions, overlap, silence gaps, topic changes, repeated objections, or longer monologues. "
        "Manager coaching note must include one praise, one correction, one practice assignment, and one next action."
    )


def _extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for output in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        for content in output.get("content", []) if isinstance(output.get("content"), list) else []:
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
            elif isinstance(content.get("output_text"), str):
                chunks.append(content["output_text"])
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _openai_call_coach(
    transcript_text: str,
    segments: list[dict[str, Any]],
    metrics: dict[str, Any],
    context: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model or DEFAULT_CALL_COACH_REASONING_MODEL,
            "reasoning": {"effort": "medium"},
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": _call_coaching_system_prompt()}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "hubspot_context": context,
                                    "interaction_metrics": metrics,
                                    "redacted_transcript_text": transcript_text,
                                    "redacted_segments": segments,
                                },
                                ensure_ascii=True,
                            ),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "nurtureany_call_coaching",
                    "strict": True,
                    "schema": CALL_COACHING_SCHEMA,
                }
            },
        },
        ensure_ascii=True,
    ).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {_openai_key()}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AircallError(f"OpenAI coaching failed: {error.code} {safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise AircallError(f"OpenAI coaching timed out or failed: {reason}") from error

    response_text = _extract_response_text(payload)
    if not response_text:
        raise AircallError("OpenAI coaching returned no structured text.")
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as error:
        raise AircallError("OpenAI coaching returned invalid JSON.") from error


def _sanitize_observable_text(value: Any) -> Any:
    if isinstance(value, str):
        text = _redact(value, 2000)
        for pattern, replacement in HIDDEN_EMOTION_REWRITES:
            text = pattern.sub(replacement, text)
        return text
    if isinstance(value, list):
        return [_sanitize_observable_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_observable_text(item) for key, item in value.items()}
    return value


def _validate_coaching_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AircallError("OpenAI coaching payload must be an object.")
    required = [
        "answer",
        "scorecard",
        "coachable_moments",
        "interaction_cues",
        "manager_coaching_note",
        "next_action",
        "source",
        "scope",
        "confidence",
        "caveat",
    ]
    missing = [key for key in required if key not in payload]
    if missing:
        raise AircallError(f"OpenAI coaching payload missing fields: {', '.join(missing)}.")
    scorecard = payload.get("scorecard")
    if not isinstance(scorecard, list):
        raise AircallError("OpenAI coaching scorecard must be a list.")
    dimensions = [str(item.get("dimension") or "") for item in scorecard if isinstance(item, dict)]
    if sorted(dimensions) != sorted(CALL_COACH_SCORE_DIMENSIONS):
        raise AircallError("OpenAI coaching scorecard missing required dimensions.")
    for item in scorecard:
        if not isinstance(item, dict):
            raise AircallError("OpenAI coaching scorecard rows must be objects.")
        if item.get("score") not in (0, 1, 2):
            raise AircallError("OpenAI coaching scorecard scores must be 0, 1, or 2.")
        if not str(item.get("evidence") or "").strip():
            raise AircallError("OpenAI coaching scorecard evidence is required.")
        if not str(item.get("timestamp") or item.get("segment_ref") or "").strip():
            raise AircallError("OpenAI coaching scorecard evidence must cite a timestamp or safe segment ref.")
    for moment in payload.get("coachable_moments") or []:
        if not isinstance(moment, dict):
            raise AircallError("OpenAI coaching coachable moments must be objects.")
        if not str(moment.get("timestamp") or moment.get("segment_ref") or "").strip():
            raise AircallError("OpenAI coaching moments must cite a timestamp or safe segment ref.")
    cues = payload.get("interaction_cues")
    if not isinstance(cues, dict):
        raise AircallError("OpenAI coaching interaction_cues must be an object.")
    cues["status"] = "Interaction cues checked from transcript/timing"
    cues["tone_audio_cues"] = "audio-native tone not checked"
    if payload.get("confidence") not in ("verified", "needs-check", "blocked"):
        payload["confidence"] = "needs-check"
    return _sanitize_observable_text(payload)


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


@mcp.tool()
def analyze_aircall_call_coaching(
    slack_user_email: str,
    aircall_call_id: str,
    hubspot_company_id: str = "",
    hubspot_call_id: str = "",
    include_debug: bool = False,
) -> dict[str, Any]:
    """Analyze one selected Aircall recording into safe sales coaching JSON."""

    call_id = str(aircall_call_id or "").strip()
    transcribe_model = _call_coach_transcribe_model()
    reasoning_model = _call_coach_reasoning_model()
    provider = _call_coach_provider()
    scope = {
        "caller_email": slack_user_email,
        "aircall_call_id": call_id,
        "hubspot_company_id": _redact(str(hubspot_company_id or ""), 80),
        "hubspot_call_id": _redact(str(hubspot_call_id or ""), 80),
        "provider": provider,
        "transcribe_model": transcribe_model,
        "reasoning_model": reasoning_model,
        "max_audio_bytes": MAX_AUDIO_BYTES,
        "max_audio_seconds": MAX_AUDIO_SECONDS,
        "read_only": True,
        "selected_call_only": True,
        "raw_recording_url_returned": False,
        "raw_audio_retained": False,
        "raw_transcript_returned": False,
        "phone_numbers_returned": False,
        "will_mutate_aircall": False,
        "will_mutate_hubspot": False,
        "gong_integration": False,
        "elevenlabs_integration": False,
    }
    if provider != "openai":
        return _blocked("NurtureAny call coaching V1 supports provider=openai only.", scope)
    if _call_coach_elevenlabs_enabled():
        return _blocked(
            "ElevenLabs is documented as future/benchmark evidence only; no production adapter is enabled in V1.",
            scope,
        )
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
            return _blocked("Aircall call exceeds the 60-minute coaching cap.", {**scope, "duration_seconds": duration})
        recording_url = _call_url_value(call)
        if not recording_url:
            return _blocked("Selected Aircall call has no recording URL available.", scope, call=safe_call)

        temp_path, audio_bytes, content_type = _download_recording(recording_url)
        transcript = _openai_transcribe(temp_path, content_type, transcribe_model)
        safe_transcript = _safe_transcript_payload(transcript, True, MAX_SEGMENTS)
        segments = _safe_segments_for_analysis(transcript, MAX_SEGMENTS)
        metrics = _compute_interaction_metrics(segments)
        context = {
            "hubspot_company_id": _redact(str(hubspot_company_id or ""), 80),
            "hubspot_call_id": _redact(str(hubspot_call_id or ""), 80),
            "hubspot_source_of_truth": True,
            "aircall_call": safe_call,
            "raw_transcript_returned_to_user": False,
            "audio_native_tone_checked": False,
        }
        transcript_text = str(safe_transcript.get("transcript_text_redacted") or "")
        coaching = _openai_call_coach(transcript_text, segments, metrics, context, reasoning_model)
        safe_coaching = _validate_coaching_payload(coaching)
        safe_coaching["source"] = (
            "Aircall selected recording, OpenAI transcription/coaching analysis, and supplied HubSpot IDs/context. "
            "Gong is design inspiration only; ElevenLabs is not used."
        )
        safe_coaching["scope"] = (
            f"selected Aircall call {call_id}; HubSpot company {scope['hubspot_company_id'] or 'not supplied'}; "
            f"HubSpot call {scope['hubspot_call_id'] or 'not supplied'}"
        )
        safe_coaching["confidence"] = "verified"
        safe_coaching["caveat"] = (
            "Audio was downloaded transiently and deleted before return. Coaching used redacted transcript segments "
            "and timing metrics; audio-native tone was not checked. No raw transcript, recording URL, audio, phone "
            "number, Gong data, ElevenLabs data, or HubSpot mutation was returned."
        )
        answer: dict[str, Any] = {
            "coaching": safe_coaching,
            "call": safe_call,
            "audio_bytes_processed": audio_bytes,
            "recording_downloaded_temporarily": True,
            "raw_recording_url_returned": False,
            "raw_audio_retained": False,
            "raw_transcript_returned": False,
            "phone_numbers_returned": False,
            "will_mutate_aircall": False,
            "will_mutate_hubspot": False,
        }
        if include_debug:
            answer["debug"] = {
                "segment_count_total": safe_transcript.get("segment_count_total"),
                "segment_count_used": len(segments),
                "interaction_metrics": metrics,
                "models": {
                    "transcribe": transcribe_model,
                    "reasoning": reasoning_model,
                },
            }
        return {
            "answer": answer,
            "source": "Aircall selected recording plus OpenAI /v1/audio/transcriptions and /v1/responses",
            "scope": {**scope, "audio_bytes_processed": audio_bytes},
            "confidence": "verified",
            "caveat": safe_coaching["caveat"],
        }
    except AircallError as error:
        return _blocked(str(error), scope)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    mcp.run("stdio")
