"""Text normalization helpers shared by NurtureAny MCP adapters."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def clean_domain(domain: str) -> str:
    text = str(domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.split("/")[0].strip()


def email_domain(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized:
        return ""
    return clean_domain(normalized.rsplit("@", 1)[1])


def hash_email(email: str) -> str:
    normalized = normalize_email(email)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] if normalized else ""


def normalized_words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def unique_text(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output
