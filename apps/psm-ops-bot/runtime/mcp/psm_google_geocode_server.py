#!/usr/bin/env python3
"""Google Geocoding MCP adapter for PSM Ops Bot."""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_GEOCODE_USER_AGENT = "StaffAny-PSMOps-Geocode/1.0 (+https://staffany.com)"
DEFAULT_CREDENTIALS_FILE = "~/.staffany/google-geocode/credentials.json"
MAX_ADDRESSES_PER_CALL = 25
MAX_ADDRESS_CHARS = 500
REQUEST_TIMEOUT_SECONDS = 15
TRANSIENT_STATUSES = {"OVER_QUERY_LIMIT", "UNKNOWN_ERROR"}
MAX_ATTEMPTS = 3


mcp = FastMCP(
    "psm_google_geocode",
    instructions=(
        "Google Geocoding API access for PSM Ops Bot. Use only explicit address "
        "text from the current Slack request, return latitude/longitude rows, and "
        "never expose API keys or store address data."
    ),
)


class GoogleGeocodeError(RuntimeError):
    pass


def _credentials_file() -> Path:
    value = (
        os.environ.get("PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE", "").strip()
        or os.environ.get("GEOCODE_CREDENTIALS_FILE", "").strip()
        or DEFAULT_CREDENTIALS_FILE
    )
    return Path(value).expanduser()


def _load_api_key() -> tuple[str, str]:
    api_key = os.environ.get("GOOGLE_GEOCODING_API_KEY", "").strip()
    if api_key:
        return api_key, "env:GOOGLE_GEOCODING_API_KEY"

    path = _credentials_file()
    if not path.exists():
        raise GoogleGeocodeError(
            "Google Geocoding credentials are not configured. Set GOOGLE_GEOCODING_API_KEY "
            "or make PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE point to credentials.json."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GoogleGeocodeError(f"Invalid JSON in Google Geocoding credentials file: {path}") from exc
    except OSError as exc:
        raise GoogleGeocodeError(f"Unable to read Google Geocoding credentials file: {path}") from exc

    api_key = str(payload.get("google_geocoding_api_key") or "").strip()
    if not api_key:
        raise GoogleGeocodeError(
            f"Google Geocoding credentials file is missing google_geocoding_api_key: {path}"
        )
    return api_key, f"file:{path}"


def _clean_text(value: Any, *, max_chars: int = MAX_ADDRESS_CHARS) -> str:
    text = " ".join(str(value or "").replace("\t", " ").split())
    return text[:max_chars]


def _address_from_item(item: Any) -> dict[str, str]:
    if isinstance(item, dict):
        address = ""
        for key in ("address", "full_address", "outlet_address", "location", "text"):
            address = _clean_text(item.get(key))
            if address:
                break
        label = _clean_text(item.get("label") or item.get("name") or item.get("customer"), max_chars=160)
        source = _clean_text(item.get("source") or item.get("source_line"), max_chars=240)
        return {"address": address, "label": label, "source": source}
    return {"address": _clean_text(item), "label": "", "source": ""}


def _normalize_address_rows(addresses: list[Any] | None) -> list[dict[str, str]]:
    if not isinstance(addresses, list) or not addresses:
        raise GoogleGeocodeError("Pass explicit address rows extracted from the current Slack message.")
    if len(addresses) > MAX_ADDRESSES_PER_CALL:
        raise GoogleGeocodeError(f"Geocode at most {MAX_ADDRESSES_PER_CALL} addresses per Slack request.")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in addresses:
        row = _address_from_item(item)
        address = row["address"]
        key = address.lower()
        if not address:
            continue
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if not rows:
        raise GoogleGeocodeError("No explicit address text was provided.")
    return rows


def _geocode_request(
    address: str,
    api_key: str,
    *,
    region_bias: str,
    country_restriction: str,
    language: str,
) -> dict[str, Any]:
    params: dict[str, str] = {
        "address": address,
        "key": api_key,
    }
    if region_bias:
        params["region"] = region_bias.lower()
    if language:
        params["language"] = language.lower()
    if country_restriction:
        params["components"] = f"country:{country_restriction.upper()}"

    request = urllib.request.Request(
        f"{GOOGLE_GEOCODE_URL}?{urllib.parse.urlencode(params)}",
        headers={
            "accept": "application/json",
            "user-agent": GOOGLE_GEOCODE_USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise GoogleGeocodeError(f"Google Geocoding API failed: HTTP {error.code} {detail[:180]}") from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleGeocodeError(f"Google Geocoding API request timed out or failed: {reason}") from error


def _geocode_one(
    row: dict[str, str],
    api_key: str,
    *,
    region_bias: str,
    country_restriction: str,
    language: str,
) -> dict[str, Any]:
    last_payload: dict[str, Any] = {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        payload = _geocode_request(
            row["address"],
            api_key,
            region_bias=region_bias,
            country_restriction=country_restriction,
            language=language,
        )
        last_payload = payload
        status = str(payload.get("status") or "UNKNOWN_ERROR")
        if status not in TRANSIENT_STATUSES or attempt == MAX_ATTEMPTS:
            break
        time.sleep(min(2 ** (attempt - 1), 4))

    status = str(last_payload.get("status") or "UNKNOWN_ERROR")
    result = (last_payload.get("results") or [{}])[0] if isinstance(last_payload.get("results"), list) else {}
    geometry = result.get("geometry") if isinstance(result, dict) else {}
    location = geometry.get("location") if isinstance(geometry, dict) else {}
    lat = location.get("lat") if isinstance(location, dict) else None
    lng = location.get("lng") if isinstance(location, dict) else None
    geocoded = status == "OK" and isinstance(lat, (int, float)) and isinstance(lng, (int, float))

    return {
        "label": row.get("label", ""),
        "address": row["address"],
        "latitude": lat if geocoded else None,
        "longitude": lng if geocoded else None,
        "geocode_status": status,
        "formatted_address": _clean_text(result.get("formatted_address"), max_chars=500) if geocoded else "",
        "place_id": _clean_text(result.get("place_id"), max_chars=160) if geocoded else "",
        "partial_match": bool(result.get("partial_match")) if isinstance(result, dict) else False,
        "source": row.get("source", ""),
        "error": _clean_text(last_payload.get("error_message"), max_chars=240),
    }


def _format_rows_for_slack(rows: list[dict[str, Any]]) -> str:
    headers = ["address", "latitude", "longitude", "geocode_status", "formatted_address"]
    lines = ["\t".join(headers)]
    for row in rows:
        values = [
            str(row.get("address") or ""),
            "" if row.get("latitude") is None else str(row.get("latitude")),
            "" if row.get("longitude") is None else str(row.get("longitude")),
            str(row.get("geocode_status") or ""),
            str(row.get("formatted_address") or ""),
        ]
        lines.append("\t".join(value.replace("\n", " ").replace("\t", " ") for value in values))
    return "Geocoded address rows:\n```" + "\n".join(lines) + "```"


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": {"status": "blocked", "message": message},
        "source": "Google Geocoding API",
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }


@mcp.tool()
def check_google_geocode_access() -> dict[str, Any]:
    """Check local Google Geocoding key availability without printing or validating the key."""
    try:
        _api_key, key_source = _load_api_key()
    except GoogleGeocodeError as error:
        return _blocked(str(error), {"credentials_file": str(_credentials_file())})
    return {
        "answer": {"status": "ok", "message": "Google Geocoding credentials are configured."},
        "source": "Google Geocoding credentials",
        "scope": {"key_source": key_source, "api_validation": "not_called"},
        "confidence": "verified",
        "caveat": "Credential check does not call the Google Geocoding API and never prints the key.",
    }


@mcp.tool()
def geocode_slack_addresses(
    addresses: list[Any] | None,
    region_bias: str = "sg",
    country_restriction: str = "",
    language: str = "en",
    slack_thread_url: str = "",
) -> dict[str, Any]:
    """Geocode explicit address rows extracted from the current Slack message."""
    try:
        rows = _normalize_address_rows(addresses)
        api_key, key_source = _load_api_key()
        geocoded_rows = [
            _geocode_one(
                row,
                api_key,
                region_bias=_clean_text(region_bias, max_chars=8),
                country_restriction=_clean_text(country_restriction, max_chars=4),
                language=_clean_text(language, max_chars=8),
            )
            for row in rows
        ]
    except GoogleGeocodeError as error:
        return _blocked(str(error), {"slack_thread_url": slack_thread_url})

    ok_count = sum(1 for row in geocoded_rows if row.get("geocode_status") == "OK")
    confidence = "verified" if ok_count == len(geocoded_rows) else "needs-check"
    return {
        "answer": {
            "status": "ok" if ok_count else "needs-check",
            "ok_count": ok_count,
            "total_count": len(geocoded_rows),
            "rows": geocoded_rows,
            "slack_reply": _format_rows_for_slack(geocoded_rows),
        },
        "source": "Google Geocoding API",
        "scope": {
            "address_count": len(geocoded_rows),
            "region_bias": _clean_text(region_bias, max_chars=8),
            "country_restriction": _clean_text(country_restriction, max_chars=4),
            "language": _clean_text(language, max_chars=8),
            "slack_thread_url": slack_thread_url,
            "key_source": key_source,
        },
        "confidence": confidence,
        "caveat": "Rows with non-OK geocode_status need manual address review.",
    }


if __name__ == "__main__":
    mcp.run()
