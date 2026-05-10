"""Response and error-detail helpers shared by NurtureAny MCP adapters."""

from __future__ import annotations

from typing import Any


def safe_detail(detail: str, max_chars: int = 300) -> str:
    return str(detail or "").replace("\n", " ")[:max_chars]


def blocked_response(
    message: str,
    source: str,
    scope: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    response = {
        "answer": message,
        "source": source,
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }
    response.update(extra)
    return response
