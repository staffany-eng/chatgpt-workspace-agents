#!/usr/bin/env python3
"""Read-only Customer 360 MCP adapter for StaffAny Data Bot."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

CUSTOMER360_BASE_URL_ENV = "CUSTOMER360_BASE_URL"
CUSTOMER360_TOKEN_ENV = "CUSTOMER360_INTERNAL_API_TOKEN"
CUSTOMER360_TIMEOUT_SECONDS = 20
DEFAULT_LIMIT = 1000
MAX_LIMIT = 5000
USER_AGENT = "StaffAny-DataBot/1.0 (+https://staffany.com)"

mcp = FastMCP(
    "staffany_c360",
    instructions=(
        "Read-only Customer 360 adapter for StaffAny Data Bot. It uses the "
        "CUSTOMER360_BASE_URL and CUSTOMER360_INTERNAL_API_TOKEN environment "
        "variables, calls only compact internal source routes with "
        "X-Customer360-Internal-Token, and never uses browser cookies or "
        "personal customer360_session credentials."
    ),
)


class StaffAnyC360Error(RuntimeError):
    pass


def _clamp_int(value: int, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _scope(as_of_date: str, country: str, limit: int) -> dict[str, Any]:
    return {
        "as_of_date": as_of_date,
        "country": country or "all",
        "requested_limit": limit,
        "max_limit": MAX_LIMIT,
        "base_url_env": CUSTOMER360_BASE_URL_ENV,
        "token_source": CUSTOMER360_TOKEN_ENV,
        "route": "/api/current-customer-orgs",
        "read_only": True,
        "uses_custom_internal_header": True,
        "uses_authorization_header": False,
        "uses_browser_cookie": False,
        "uses_personal_customer360_session": False,
    }


def _blocked(message: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": message,
        "source": "Customer 360 internal API",
        "scope": scope,
        "confidence": "blocked",
        "caveat": "No browser cookies, personal sessions, bearer Authorization header, or write operations were used.",
    }


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise StaffAnyC360Error(f"Missing {name}.")
    return value


def _safe_error(message: str) -> str:
    token = os.environ.get(CUSTOMER360_TOKEN_ENV, "").strip()
    safe = str(message).replace(token, "[REDACTED_CUSTOMER360_INTERNAL_API_TOKEN]") if token else str(message)
    return safe[:500]


def _request_current_customer_orgs(as_of_date: str, country: str, limit: int) -> dict[str, Any]:
    base_url = _env(CUSTOMER360_BASE_URL_ENV).rstrip("/")
    token = _env(CUSTOMER360_TOKEN_ENV)
    query = urllib.parse.urlencode(
        {
            "asOf": as_of_date,
            "country": country,
            "limit": limit,
        }
    )
    url = f"{base_url}/api/current-customer-orgs?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "X-Customer360-Internal-Token": token,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=CUSTOMER360_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise StaffAnyC360Error(_safe_error(f"Customer 360 API failed: HTTP {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise StaffAnyC360Error(_safe_error(f"Customer 360 API request failed: {reason}")) from error
    except json.JSONDecodeError as error:
        raise StaffAnyC360Error("Customer 360 API returned invalid JSON.") from error


def _compact_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    compact: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        compact.append(
            {
                "customerKey": str(row.get("customerKey") or ""),
                "hubspotCompanyId": str(row.get("hubspotCompanyId") or ""),
                "companyName": str(row.get("companyName") or ""),
                "country": str(row.get("country") or ""),
                "renewalBucket": str(row.get("renewalBucket") or ""),
                "renewalAssessment": str(row.get("renewalAssessment") or ""),
                "renewalDate": str(row.get("renewalDate") or ""),
                "linkedStaffAnyOrgId": str(row.get("linkedStaffAnyOrgId") or ""),
                "linkedStaffAnyOrgName": str(row.get("linkedStaffAnyOrgName") or ""),
                "mappingStatus": str(row.get("mappingStatus") or ""),
                "c360Url": str(row.get("c360Url") or ""),
            }
        )
    return compact


@mcp.tool()
def list_current_customer_orgs(as_of_date: str, country: str = "", limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """List compact Customer 360 current-customer company/org rows."""

    safe_as_of_date = str(as_of_date or "").strip()
    safe_country = str(country or "").strip()
    safe_limit = _clamp_int(limit, DEFAULT_LIMIT, 1, MAX_LIMIT)
    scope = _scope(safe_as_of_date, safe_country, safe_limit)
    if not safe_as_of_date:
        return _blocked("as_of_date is required in YYYY-MM-DD format.", scope)
    if not safe_as_of_date or len(safe_as_of_date) != 10:
        return _blocked("as_of_date must be YYYY-MM-DD.", scope)

    try:
        payload = _request_current_customer_orgs(safe_as_of_date, safe_country, safe_limit)
    except StaffAnyC360Error as error:
        return _blocked(str(error), scope)

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or payload.get("status") != "ok":
        return _blocked("Customer 360 API returned an unexpected response shape.", scope)

    rows = _compact_rows(data.get("rows"))
    return {
        "answer": {
            "asOfDate": str(data.get("asOfDate") or safe_as_of_date),
            "country": str(data.get("country") or safe_country or "all"),
            "definition": str(
                data.get("definition")
                or "Current customer means active C360 renewal cycle or active billing main deal on asOf, excluding Closed Not Renewing."
            ),
            "row_count": len(rows),
            "rows": rows,
            "staffany_org_ids": sorted(
                {
                    row["linkedStaffAnyOrgId"]
                    for row in rows
                    if row.get("linkedStaffAnyOrgId") and row.get("mappingStatus") == "linked"
                }
            ),
            "mapping_gap_count": sum(1 for row in rows if row.get("mappingStatus") == "mapping_gap"),
        },
        "source": "Customer 360 /api/current-customer-orgs via X-Customer360-Internal-Token",
        "scope": scope,
        "confidence": "verified" if rows else "needs-check",
        "caveat": "Use this as the current-customer universe before product/app BigQuery metric checks; mapping gaps cannot be safely joined to org-level warehouse metrics.",
    }


if __name__ == "__main__":
    mcp.run()
