#!/usr/bin/env python3
"""Read-only demo transcript evidence MCP adapter for NurtureAny Sales Bot.

This server extracts bounded, redacted caption evidence from selected demo
sources. V1 supports Loom share pages with captions/VTT only. It never returns
raw transcript dumps, signed Loom media URLs, video/audio bytes, phone numbers,
or full emails.
"""

from __future__ import annotations

import html
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.responses import blocked_response, safe_detail


USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
TIMEOUT_SECONDS = 20
MAX_FETCH_BYTES = 1_000_000
MAX_SAFE_SEGMENTS = 24
MAX_SEGMENT_CHARS = 220
SUPPORTED_SOURCE_TYPES = ("auto", "loom")
DEMO_GRADE_SCORE_VALUES = (0, 1, 2)
DEMO_GRADE_DIMENSIONS = [
    "Control and conversational opening",
    "Discovery and I-C-BANT",
    "Consultative/contextual demo",
    "Before/after value framing",
    "Benefits over features",
    "Product knowledge accuracy",
    "Objection and negotiation handling",
    "Customer engagement and interaction cues",
    "Next step and post-demo follow-up quality",
]
DEMO_GRADE_OUTPUT_FIELDS = [
    "Answer",
    "Overall grade",
    "Scorecard",
    "Coachable moments",
    "Better talk tracks",
    "Manager coaching note",
    "Next practice",
    "Source",
    "Scope",
    "Confidence",
    "Caveat",
]
TIMESTAMP_RE = re.compile(
    r"^(?P<start>(?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{2}:)?\d{2}:\d{2}\.\d{3})(?:\s+.*)?$"
)


mcp = FastMCP(
    "demo_sources_nurtureany",
    instructions=(
        "Read-only selected demo transcript evidence for NurtureAny. Fetch "
        "Loom captions/VTT only, return bounded redacted cue evidence, and "
        "never expose raw transcripts, signed media URLs, video/audio bytes, "
        "phone numbers, full emails, or source mutations."
    ),
)


class DemoSourceError(RuntimeError):
    pass


def _blocked(message: str, scope: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return blocked_response(message, "Loom captions/VTT selected demo source", scope, **extra)


def _redact(value: str, max_chars: int = MAX_SEGMENT_CHARS) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"<@[A-Z0-9]+>", "@user", text)
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[phone]", text)
    text = re.sub(r"https?://\S+", "[url]", text)
    text = re.sub(r"\b(?:Signature|Expires|Policy|Key-Pair-Id|X-Amz-[A-Za-z0-9-]+)=\S+", "[signed-param]", text)
    text = re.sub(r"\b[A-Za-z0-9_-]{48,}\b", "[token]", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}..."


def _canonical_loom_url(source_url: str) -> str:
    raw = str(source_url or "").strip()
    if not raw:
        raise DemoSourceError("source_url is required.")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise DemoSourceError("source_url must be a valid Loom share URL.")
    host = parsed.netloc.lower()
    if host not in ("loom.com", "www.loom.com"):
        raise DemoSourceError("V1 supports Loom share URLs only.")
    match = re.fullmatch(r"/share/([A-Za-z0-9_-]+)", parsed.path.rstrip("/"))
    if not match:
        raise DemoSourceError("source_url must be a Loom /share/<id> URL.")
    return f"https://www.loom.com/share/{match.group(1)}"


def _fetch_text(url: str, max_bytes: int = MAX_FETCH_BYTES) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise DemoSourceError("Demo source response exceeded the 1 MB V1 safety cap.")
            charset = response.headers.get_content_charset() if response.headers else None
            return raw.decode(charset or "utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise DemoSourceError(f"Demo source fetch failed: HTTP {error.code} {safe_detail(detail)}") from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise DemoSourceError(f"Demo source fetch timed out or failed: {safe_detail(str(reason))}") from error


def _extract_title(page_html: str) -> str:
    for pattern in (
        r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:title["\']',
        r"<title[^>]*>(.*?)</title>",
    ):
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            title = html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())
            return _redact(title, 160)
    return "Untitled Loom demo"


def _extract_vtt_url(page_html: str) -> str:
    normalized = html.unescape(page_html)
    normalized = normalized.replace("\\u0026", "&").replace("\\/", "/")
    absolute = re.search(r"https://[^\"'<>\\\s]+?\.vtt(?:\?[^\"'<>\\\s]*)?", normalized)
    if absolute:
        return absolute.group(0)
    protocol_relative = re.search(r"//[^\"'<>\\\s]+?\.vtt(?:\?[^\"'<>\\\s]*)?", normalized)
    if protocol_relative:
        return f"https:{protocol_relative.group(0)}"
    relative = re.search(r"(/[^\"'<>\\\s]+?\.vtt(?:\?[^\"'<>\\\s]*)?)", normalized)
    if relative:
        return urllib.parse.urljoin("https://www.loom.com", relative.group(1))
    return ""


def _strip_vtt_markup(text: str) -> str:
    cleaned = html.unescape(text)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _timestamp_to_seconds(timestamp: str) -> float:
    parts = timestamp.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    else:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    return hours * 3600 + minutes * 60 + seconds


def _parse_vtt(vtt_text: str) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    text_lines: list[str] = []
    for raw_line in vtt_text.splitlines() + [""]:
        line = raw_line.strip("\ufeff").strip()
        timestamp = TIMESTAMP_RE.match(line)
        if timestamp:
            if current is not None:
                text = _strip_vtt_markup(" ".join(text_lines))
                if text:
                    current["text"] = text
                    cues.append(current)
            current = {
                "start": timestamp.group("start"),
                "end": timestamp.group("end"),
                "start_seconds": _timestamp_to_seconds(timestamp.group("start")),
                "end_seconds": _timestamp_to_seconds(timestamp.group("end")),
            }
            text_lines = []
            continue
        if current is None:
            continue
        if not line:
            text = _strip_vtt_markup(" ".join(text_lines))
            if text:
                current["text"] = text
                cues.append(current)
            current = None
            text_lines = []
            continue
        if line.upper().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        text_lines.append(line)
    return cues


def _safe_segments(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for index, cue in enumerate(cues[:MAX_SAFE_SEGMENTS], start=1):
        safe.append(
            {
                "ref": f"demo_seg_{index}",
                "start": cue.get("start", ""),
                "end": cue.get("end", ""),
                "text": _redact(str(cue.get("text") or ""), MAX_SEGMENT_CHARS),
            }
        )
    return safe


def _word_count(cues: list[dict[str, Any]]) -> int:
    return sum(len(re.findall(r"\b[\w']+\b", str(cue.get("text") or ""))) for cue in cues)


def _leak_free_result_text(result: dict[str, Any]) -> str:
    return str(result)


@mcp.tool()
def extract_demo_transcript_evidence(
    slack_user_email: str,
    source_url: str,
    source_type: str = "auto",
) -> dict[str, Any]:
    """Extract bounded redacted transcript/timing evidence from a selected demo source."""

    requested_source_type = str(source_type or "auto").strip().lower()
    scope = {
        "caller_email": _redact(str(slack_user_email or ""), 120),
        "source_type_input": requested_source_type,
        "read_only": True,
        "selected_source_only": True,
        "loom_captions_vtt_first": True,
        "max_fetch_bytes": MAX_FETCH_BYTES,
        "max_safe_segments": MAX_SAFE_SEGMENTS,
        "raw_transcript_returned": False,
        "signed_loom_media_urls_returned": False,
        "video_audio_bytes_returned": False,
        "phone_numbers_returned": False,
        "full_emails_returned": False,
        "will_mutate_source": False,
    }
    if requested_source_type not in SUPPORTED_SOURCE_TYPES:
        return _blocked(
            "V1 supports source_type=auto or source_type=loom only. Ask for Loom captions or paste a transcript in a future supported flow.",
            scope,
            blocker_reason="unsupported_source_type",
        )
    try:
        permalink = _canonical_loom_url(source_url)
        scope["source_permalink"] = permalink
        page_html = _fetch_text(permalink)
        title = _extract_title(page_html)
        vtt_url = _extract_vtt_url(page_html)
        if not vtt_url:
            return _blocked(
                "No Loom captions/VTT were found. The demo may be private, blocked, or captions may be disabled; ask for captions or a pasted transcript.",
                scope,
                blocker_reason="captions_unavailable",
                answer_details={
                    "title": title,
                    "source_type": "loom",
                    "source_permalink": permalink,
                    "caption_available": False,
                    "raw_transcript_returned": False,
                    "signed_loom_media_urls_returned": False,
                    "video_audio_bytes_returned": False,
                },
            )
        vtt_text = _fetch_text(vtt_url)
        cues = _parse_vtt(vtt_text)
        if not cues:
            return _blocked(
                "Loom captions were found but no parseable VTT cues were available. Ask for a transcript/captions export.",
                scope,
                blocker_reason="captions_parse_failed",
            )
        duration_seconds = max((float(cue.get("end_seconds") or 0) for cue in cues), default=0.0)
        result = {
            "answer": {
                "title": title,
                "source_type": "loom",
                "source_permalink": permalink,
                "caption_available": True,
                "cue_count": len(cues),
                "word_count": _word_count(cues),
                "timing_metadata": {
                    "duration_seconds": round(duration_seconds, 3),
                    "first_start": cues[0].get("start", ""),
                    "last_end": cues[-1].get("end", ""),
                },
                "segments": _safe_segments(cues),
                "segment_count_returned": min(len(cues), MAX_SAFE_SEGMENTS),
                "segments_truncated": len(cues) > MAX_SAFE_SEGMENTS,
                "demo_grade_dimensions": DEMO_GRADE_DIMENSIONS,
                "demo_grade_score_values": list(DEMO_GRADE_SCORE_VALUES),
                "demo_grade_output_fields": DEMO_GRADE_OUTPUT_FIELDS,
                "raw_transcript_returned": False,
                "signed_loom_media_urls_returned": False,
                "video_audio_bytes_returned": False,
                "phone_numbers_returned": False,
                "full_emails_returned": False,
                "will_mutate_source": False,
            },
            "source": "Loom share page captions/VTT selected demo source",
            "scope": {**scope, "source_type": "loom", "cue_count": len(cues)},
            "confidence": "verified",
            "caveat": (
                "Caption/timing evidence only. No raw transcript dump, signed Loom media URL, video/audio bytes, "
                "phone numbers, full emails, or source mutation was returned."
            ),
        }
        result_text = _leak_free_result_text(result)
        if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", result_text, flags=re.IGNORECASE):
            raise DemoSourceError("Safety check blocked full-email output.")
        if re.search(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", result_text):
            raise DemoSourceError("Safety check blocked phone-number output.")
        if ".vtt" in result_text or "Signature=" in result_text or "Key-Pair-Id=" in result_text:
            raise DemoSourceError("Safety check blocked signed media URL output.")
        return result
    except DemoSourceError as error:
        return _blocked(str(error), scope, blocker_reason="source_fetch_or_parse_failed")


if __name__ == "__main__":
    mcp.run("stdio")
