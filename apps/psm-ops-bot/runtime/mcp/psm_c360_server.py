#!/usr/bin/env python3
"""Customer 360 MCP adapter for PSM Ops Bot."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

DEFAULT_C360_BASE_URL = "https://customer-360-qv4r5xkisq-as.a.run.app"

mcp = FastMCP(
    "psm_c360",
    instructions=(
        "Customer 360 internal API access for PSM Ops Bot. "
        "Use bearer auth only; never use personal Customer 360 session cookies."
    ),
)


class C360Error(RuntimeError):
    pass


def _base_url() -> str:
    return os.environ.get("CUSTOMER360_BASE_URL", DEFAULT_C360_BASE_URL).strip().rstrip("/")


def _token() -> str:
    token = (
        os.environ.get("CUSTOMER360_INTERNAL_API_TOKEN", "").strip()
        or os.environ.get("CUSTOMER_360_INTERNAL_API_TOKEN", "").strip()
    )
    if not token:
        raise C360Error("CUSTOMER360_INTERNAL_API_TOKEN is not configured.")
    return token


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/markdown",
        "Authorization": f"Bearer {_token()}",
        "X-Customer360-Internal-Token": _token(),
        "Content-Type": "application/json",
    }


def _blocked(message: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": {"status": "blocked", "message": message},
        "source": "Customer 360 internal API",
        "scope": scope,
        "confidence": "blocked",
        "caveat": message,
    }


def _http_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = f"{_base_url()}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return json.loads(payload)
            return {"status": "ok", "data": payload}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise C360Error(f"Customer 360 API failed: HTTP {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise C360Error(f"Customer 360 API unavailable: {error.reason}") from error


@mcp.tool()
def search_c360_customers(query: str, limit: int = 8) -> dict[str, Any]:
    """Search Customer 360 customers by company, owner, org, or customer key."""

    normalized_query = (query or "").strip()
    scope = {"query": normalized_query, "limit": max(1, min(int(limit or 8), 20))}
    if not normalized_query:
        return _blocked("Customer search query is required.", scope)

    try:
        encoded = urllib.parse.urlencode({"q": normalized_query})
        payload = _http_json("GET", f"/api/companies?{encoded}")
    except C360Error as error:
        return _blocked(str(error), scope)

    groups = payload.get("search", {}).get("groups", []) if isinstance(payload, dict) else []
    return {
        "answer": groups[: scope["limit"]],
        "source": "Customer 360 /api/companies",
        "scope": scope,
        "confidence": "verified",
        "caveat": "All-customer C360 access is enabled for V1; task writes still stay Jira-scoped.",
    }


@mcp.tool()
def get_c360_account_context(customer_key: str, format: str = "markdown") -> dict[str, Any]:
    """Fetch compact Customer 360 account context for one customer key."""

    key = (customer_key or "").strip()
    output_format = "json" if str(format).lower() == "json" else "markdown"
    scope = {"customer_key": key, "format": output_format}
    if not key:
        return _blocked("Customer key is required.", scope)

    try:
        encoded_key = urllib.parse.quote(key, safe="")
        query = "?format=markdown" if output_format == "markdown" else ""
        payload = _http_json("GET", f"/api/companies/{encoded_key}/context{query}")
    except C360Error as error:
        return _blocked(str(error), scope)

    return {
        "answer": payload.get("data", payload) if isinstance(payload, dict) else payload,
        "source": f"Customer 360 /api/companies/{key}/context",
        "scope": scope,
        "confidence": "verified",
        "caveat": "Context is compact and cited; raw source packs are not exposed.",
    }


@mcp.tool()
def ask_c360_customer_context(customer_key: str, question: str) -> dict[str, Any]:
    """Ask Customer 360 compiled wiki and account context about one customer."""

    key = (customer_key or "").strip()
    normalized_question = (question or "").strip()
    scope = {"customer_key": key, "question_chars": len(normalized_question)}
    if not key:
        return _blocked("Customer key is required.", scope)
    if not normalized_question:
        return _blocked("Question is required.", scope)

    try:
        encoded_key = urllib.parse.quote(key, safe="")
        payload = _http_json(
            "POST",
            f"/api/companies/{encoded_key}/ask",
            {"question": normalized_question},
        )
    except C360Error as error:
        return _blocked(str(error), scope)

    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    confidence = "verified"
    caveat = "Answer is constrained to compiled Customer 360 wiki and cited account context."
    if isinstance(data, dict) and data.get("citationRefs") == []:
        confidence = "needs-check"
        caveat = "Customer 360 returned no supporting citation refs for this question."

    return {
        "answer": data,
        "source": f"Customer 360 /api/companies/{key}/ask",
        "scope": scope,
        "confidence": confidence,
        "caveat": caveat,
    }


if __name__ == "__main__":
    mcp.run("stdio")
