"""Luma tag and country normalization shared by NurtureAny adapters."""

from __future__ import annotations

from typing import Any

from .text import normalized_words, unique_text

EVENT_TYPE_TAGS = (
    "Sports",
    "Appreciation Afternoon",
    "HR Happy Hour",
    "Leaders Lounge",
)
EVENT_TYPE_ALIASES = {
    "sports": "Sports",
    "sport": "Sports",
    "appreciation afternoon": "Appreciation Afternoon",
    "appreciation": "Appreciation Afternoon",
    "hr happy hour": "HR Happy Hour",
    "hhh": "HR Happy Hour",
    "happy hour": "HR Happy Hour",
    "leaders lounge": "Leaders Lounge",
    "leader lounge": "Leaders Lounge",
    "ll": "Leaders Lounge",
}
COUNTRY_TAGS = ("Singapore", "Malaysia", "Indonesia")
LOCATION_TAGS = ("Singapore", "Jakarta", "Bali", "Kuala Lumpur")
LOCATION_ALIASES = {
    "singapore": "Singapore",
    "sg": "Singapore",
    "jakarta": "Jakarta",
    "jkt": "Jakarta",
    "bali": "Bali",
    "kuala lumpur": "Kuala Lumpur",
    "kl": "Kuala Lumpur",
}
LOCATION_COUNTRY_MAP = {
    "Singapore": "Singapore",
    "Jakarta": "Indonesia",
    "Bali": "Indonesia",
    "Kuala Lumpur": "Malaysia",
}


def canonical_event_type(value: str) -> str:
    words = normalized_words(value)
    if not words:
        return ""
    for alias, display in EVENT_TYPE_ALIASES.items():
        if words == alias or alias in words:
            return display
    return ""


def canonical_location(value: str) -> str:
    words = normalized_words(value)
    if not words:
        return ""
    for alias, display in LOCATION_ALIASES.items():
        if words == alias or alias in words:
            return display
    return ""


def canonical_country(value: str) -> str:
    words = normalized_words(value)
    tokens = set(words.split())
    if not words:
        return ""
    if "singapore" in words or "sg" in tokens or "asia singapore" in words:
        return "Singapore"
    if (
        "indonesia" in words
        or "jakarta" in words
        or "bali" in words
        or "jkt" in tokens
        or "id" in tokens
        or "asia jakarta" in words
    ):
        return "Indonesia"
    if (
        "malaysia" in words
        or "kuala lumpur" in words
        or "kl" in tokens
        or "my" in tokens
        or "asia kuala lumpur" in words
    ):
        return "Malaysia"
    return ""


def resolved_event_filters(country: str, event_type: str, location: str) -> dict[str, str]:
    location_filter = canonical_location(location)
    event_type_filter = canonical_event_type(event_type)
    country_filter = canonical_country(country)

    if not location_filter:
        location_filter = canonical_location(event_type)
    if not location_filter:
        location_filter = canonical_location(country)
    if not country_filter and location_filter:
        country_filter = LOCATION_COUNTRY_MAP.get(location_filter, "")

    return {
        "country": country_filter,
        "event_type": event_type_filter,
        "location": location_filter,
    }


def event_tag_filters(event_tags: Any, country: str = "", event_type: str = "", location: str = "") -> list[str]:
    raw: list[Any] = []
    if isinstance(event_tags, str):
        raw.extend(part.strip() for part in event_tags.replace(";", ",").split(",") if part.strip())
    elif isinstance(event_tags, list):
        raw.extend(event_tags)

    tags: list[str] = []
    for value in raw:
        text = str(value or "").strip()
        if text:
            tags.append(canonical_location(text) or canonical_event_type(text) or canonical_country(text) or text)

    filters = resolved_event_filters(country, event_type, location)
    if filters["location"]:
        tags.append(filters["location"])
    if filters["event_type"]:
        tags.append(filters["event_type"])
    return unique_text(tags)
