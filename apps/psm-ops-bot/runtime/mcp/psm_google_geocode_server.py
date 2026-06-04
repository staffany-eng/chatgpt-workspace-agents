#!/usr/bin/env python3
"""Google Geocoding MCP adapter for PSM Ops Bot."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
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
SLACK_API_BASE_URL = "https://slack.com/api"
DEFAULT_CREDENTIALS_FILE = "~/.staffany/google-geocode/credentials.json"
MAX_ADDRESSES_PER_CALL = 25
MAX_ADDRESS_CHARS = 500
MAX_INPUT_FILE_BYTES = 256 * 1024
REQUEST_TIMEOUT_SECONDS = 15
TRANSIENT_STATUSES = {"OVER_QUERY_LIMIT", "UNKNOWN_ERROR"}
MAX_ATTEMPTS = 3
SUPPORTED_INPUT_EXTENSIONS = {".csv", ".tsv"}
SUPPORTED_INPUT_MIME_TYPES = {
    "application/csv",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
    "text/tab-separated-values",
}
TRUSTED_SLACK_FILE_HOSTS = {"files.slack.com"}
UNRESOLVED_PLACEHOLDER_RE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")
PHONE_ONLY_RE = re.compile(r"^[+\d\s().-]{7,}$")
POSTAL_CODE_RE = re.compile(r"\b\d{5,6}\b")
STREET_SIGNAL_RE = re.compile(
    r"\b("
    r"address|avenue|ave|block|blk|boulevard|blvd|building|bldg|close|"
    r"crescent|drive|dr|floor|fl|hospital|jalan|jln|lane|ln|lorong|lor|"
    r"mall|parkway|place|pl|road|rd|street|st|tower|unit|way|walk"
    r")\b",
    re.IGNORECASE,
)
VAGUE_LOCATION_PREFIX_RE = re.compile(r"^(near|nearby|around|beside|opposite|close to|somewhere near)\b", re.IGNORECASE)


mcp = FastMCP(
    "psm_google_geocode",
    instructions=(
        "Google Geocoding API access for PSM Ops Bot. Use only explicit address "
        "text from the current Slack request, upload latitude/longitude rows as a "
        ".tsv file, and never expose API keys or store address data."
    ),
)


class GoogleGeocodeError(RuntimeError):
    pass


def _env_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if UNRESOLVED_PLACEHOLDER_RE.fullmatch(value):
        return ""
    return value


def _credentials_file() -> Path:
    value = (
        _env_value("PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE")
        or _env_value("GEOCODE_CREDENTIALS_FILE")
        or DEFAULT_CREDENTIALS_FILE
    )
    return Path(value).expanduser()


def _load_api_key() -> tuple[str, str]:
    api_key = _env_value("GOOGLE_GEOCODING_API_KEY")
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


def _slack_token() -> str:
    token = _env_value("SLACK_BOT_TOKEN")
    if not token:
        raise GoogleGeocodeError("SLACK_BOT_TOKEN is not configured, so the TSV file cannot be uploaded.")
    return token


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


def _looks_like_explicit_address(address: str) -> bool:
    text = _clean_text(address)
    if not text:
        return False
    if PHONE_ONLY_RE.fullmatch(text) and sum(char.isdigit() for char in text) >= 7:
        return False
    if VAGUE_LOCATION_PREFIX_RE.search(text) and not POSTAL_CODE_RE.search(text):
        return False
    if POSTAL_CODE_RE.search(text):
        return True
    has_digit = any(char.isdigit() for char in text)
    has_street_signal = bool(STREET_SIGNAL_RE.search(text))
    return has_digit and has_street_signal


def _normalize_address_rows(addresses: list[Any] | None) -> list[dict[str, str]]:
    if not isinstance(addresses, list) or not addresses:
        raise GoogleGeocodeError("Pass explicit address rows extracted from the current Slack message.")
    if len(addresses) > MAX_ADDRESSES_PER_CALL:
        raise GoogleGeocodeError(f"Geocode at most {MAX_ADDRESSES_PER_CALL} addresses per Slack request.")

    rows: list[dict[str, str]] = []
    for item in addresses:
        row = _address_from_item(item)
        address = row["address"]
        if not address:
            continue
        if not _looks_like_explicit_address(address):
            continue
        rows.append(row)
    if not rows:
        raise GoogleGeocodeError(
            "No explicit postal address text was provided. Send full street addresses or postal-code rows, not customer names, phone numbers, or vague location hints."
        )
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


def _tsv_text(rows: list[dict[str, Any]]) -> str:
    headers = [
        "label",
        "source",
        "address",
        "latitude",
        "longitude",
        "geocode_status",
        "formatted_address",
        "place_id",
        "partial_match",
        "error",
    ]
    lines = ["\t".join(headers)]
    for row in rows:
        values = [
            str(row.get("label") or ""),
            str(row.get("source") or ""),
            str(row.get("address") or ""),
            "" if row.get("latitude") is None else str(row.get("latitude")),
            "" if row.get("longitude") is None else str(row.get("longitude")),
            str(row.get("geocode_status") or ""),
            str(row.get("formatted_address") or ""),
            str(row.get("place_id") or ""),
            "true" if row.get("partial_match") else "false",
            str(row.get("error") or ""),
        ]
        lines.append("\t".join(value.replace("\n", " ").replace("\t", " ") for value in values))
    return "\n".join(lines) + "\n"


def _slack_thread_target(slack_thread_url: str) -> tuple[str, str]:
    match = re.search(r"/archives/([A-Z0-9]+)/p(\d{10})(\d{6})", slack_thread_url or "")
    if not match:
        raise GoogleGeocodeError("A valid Slack thread permalink is required to upload the geocoded TSV file.")
    channel_id = match.group(1)
    thread_ts = f"{match.group(2)}.{match.group(3)}"
    return channel_id, thread_ts


def _slack_api_post(method: str, token: str, params: dict[str, str]) -> dict[str, Any]:
    data = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(
        f"{SLACK_API_BASE_URL}/{method}",
        data=data,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/x-www-form-urlencoded",
            "accept": "application/json",
            "user-agent": GOOGLE_GEOCODE_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleGeocodeError(f"Slack file upload API request timed out or failed: {reason}") from error
    if not payload.get("ok"):
        error = str(payload.get("error") or "unknown_error")
        if error == "missing_scope":
            raise GoogleGeocodeError("Slack file upload is missing the files:write bot scope.")
        raise GoogleGeocodeError(f"Slack file upload failed: {error}")
    return payload


def _slack_thread_messages(slack_thread_url: str) -> tuple[str, str, list[dict[str, Any]]]:
    channel_id, message_ts = _slack_thread_target(slack_thread_url)
    token = _slack_token()
    messages_by_ts: dict[str, dict[str, Any]] = {}

    history = _slack_api_post(
        "conversations.history",
        token,
        {
            "channel": channel_id,
            "oldest": message_ts,
            "inclusive": "true",
            "limit": "1",
        },
    )
    for entry in history.get("messages") or []:
        if isinstance(entry, dict) and str(entry.get("ts") or "") == message_ts:
            messages_by_ts[message_ts] = entry

    replies = _slack_api_post(
        "conversations.replies",
        token,
        {
            "channel": channel_id,
            "ts": message_ts,
            "inclusive": "true",
            "limit": "200",
        },
    )
    for entry in replies.get("messages") or []:
        if not isinstance(entry, dict):
            continue
        ts = str(entry.get("ts") or "")
        if ts:
            messages_by_ts[ts] = entry

    return channel_id, message_ts, list(messages_by_ts.values())


def _file_extension(filename: str) -> str:
    name = filename.lower().strip()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1]


def _is_supported_input_file(entry: dict[str, Any]) -> bool:
    filename = str(entry.get("name") or entry.get("title") or "").strip()
    extension = _file_extension(filename)
    if extension in SUPPORTED_INPUT_EXTENSIONS:
        return True
    mimetype = str(entry.get("mimetype") or "").lower().strip()
    filetype = str(entry.get("filetype") or "").lower().strip()
    return mimetype in SUPPORTED_INPUT_MIME_TYPES and filetype in {"csv", "tsv"}


def _extract_address_files(files: list[Any], *, message_ts: str = "") -> list[dict[str, str]]:
    address_files: list[dict[str, str]] = []
    for entry in files or []:
        if not isinstance(entry, dict) or not _is_supported_input_file(entry):
            continue
        url_private = str(entry.get("url_private_download") or entry.get("url_private") or "")
        if not url_private:
            continue
        name = str(entry.get("name") or entry.get("title") or "addresses").strip()
        address_files.append(
            {
                "id": str(entry.get("id") or ""),
                "name": name,
                "mimetype": str(entry.get("mimetype") or ""),
                "filetype": str(entry.get("filetype") or ""),
                "url_private": url_private,
                "message_ts": message_ts,
            }
        )
    return address_files


def _select_slack_address_file(
    slack_thread_url: str,
    *,
    file_id: str = "",
    filename: str = "",
) -> dict[str, str]:
    _channel_id, message_ts, messages = _slack_thread_messages(slack_thread_url)
    all_files: list[dict[str, str]] = []
    all_file_count = 0
    for message in messages:
        files = message.get("files") or []
        if isinstance(files, list):
            all_file_count += len(files)
        all_files.extend(_extract_address_files(files, message_ts=str(message.get("ts") or "")))

    if not all_files:
        hint = "Attach a .csv or .tsv file with an address column."
        if all_file_count:
            hint = "Attached files were found, but none were supported .csv or .tsv address files."
        raise GoogleGeocodeError(hint)

    normalized_file_id = _clean_text(file_id, max_chars=80)
    normalized_filename = _clean_text(filename, max_chars=240).lower()
    if normalized_file_id or normalized_filename:
        for entry in all_files:
            if normalized_file_id and entry["id"] == normalized_file_id:
                return entry
            if normalized_filename and entry["name"].lower() == normalized_filename:
                return entry
        raise GoogleGeocodeError("The requested CSV/TSV attachment was not found in the current Slack thread.")

    for entry in all_files:
        if entry["message_ts"] == message_ts:
            return entry

    return sorted(all_files, key=lambda item: float(item.get("message_ts") or 0.0), reverse=True)[0]


def _download_slack_file(url_private: str) -> bytes:
    parsed = urllib.parse.urlparse(url_private)
    host = parsed.netloc.lower()
    if parsed.scheme != "https" or host not in TRUSTED_SLACK_FILE_HOSTS:
        raise GoogleGeocodeError("Slack file download URL must use a trusted Slack file host over https.")
    token = _slack_token()
    request = urllib.request.Request(
        url_private,
        headers={
            "authorization": f"Bearer {token}",
            "user-agent": GOOGLE_GEOCODE_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            content = response.read(MAX_INPUT_FILE_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            raise GoogleGeocodeError("Slack file download is missing access to read the attached file; check files:read.") from error
        raise GoogleGeocodeError(f"Slack file download failed: HTTP {error.code}") from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleGeocodeError(f"Slack file download timed out or failed: {reason}") from error
    if len(content) > MAX_INPUT_FILE_BYTES:
        raise GoogleGeocodeError("Address CSV/TSV files must be 256KB or smaller.")
    if not content:
        raise GoogleGeocodeError("The attached CSV/TSV file is empty.")
    return content


def _decode_input_file(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise GoogleGeocodeError("Address CSV/TSV files must be UTF-8 encoded.")


def _input_file_delimiter(filename: str, mimetype: str, sample: str) -> str:
    extension = _file_extension(filename)
    if extension == ".tsv" or "tab-separated" in mimetype.lower():
        return "\t"
    if extension == ".csv":
        return ","
    try:
        return csv.Sniffer().sniff(sample[:4096], delimiters=",\t").delimiter
    except csv.Error:
        return ","


def _header_lookup(fieldnames: list[str] | None) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field in fieldnames or []:
        normalized = _clean_text(field, max_chars=80).lower().replace(" ", "_")
        if normalized:
            lookup[normalized] = field
    return lookup


def _first_present(row: dict[str, Any], lookup: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        source_key = lookup.get(key)
        if source_key is not None:
            value = _clean_text(row.get(source_key), max_chars=240)
            if value:
                return value
    return ""


def _parse_address_file(content: bytes, *, filename: str, mimetype: str = "") -> list[dict[str, str]]:
    text = _decode_input_file(content)
    delimiter = _input_file_delimiter(filename, mimetype, text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    lookup = _header_lookup(reader.fieldnames)
    address_key = lookup.get("address")
    if not address_key:
        raise GoogleGeocodeError("CSV/TSV address files must include an address column.")

    rows: list[dict[str, str]] = []
    for index, raw_row in enumerate(reader, start=2):
        address = _clean_text(raw_row.get(address_key))
        if not address:
            raise GoogleGeocodeError(
                f"CSV/TSV address files must not contain an empty address row ({filename}: row {index})."
            )
        label = _first_present(raw_row, lookup, ["label", "customer", "outlet", "name"])
        source = _first_present(raw_row, lookup, ["source", "source_line"])
        if not source:
            source = f"{filename}: row {index}"
        rows.append({"address": address, "label": label, "source": source})
    return _normalize_address_rows(rows)


def _geocode_rows_and_upload(
    rows: list[dict[str, str]],
    *,
    region_bias: str,
    country_restriction: str,
    language: str,
    slack_thread_url: str,
) -> dict[str, Any]:
    api_key, key_source = _load_api_key()
    _preflight_slack_upload(slack_thread_url)
    cleaned_region_bias = _clean_text(region_bias, max_chars=8)
    cleaned_country_restriction = _clean_text(country_restriction, max_chars=4)
    cleaned_language = _clean_text(language, max_chars=8)
    geocoded_rows = [
        _geocode_one(
            row,
            api_key,
            region_bias=cleaned_region_bias,
            country_restriction=cleaned_country_restriction,
            language=cleaned_language,
        )
        for row in rows
    ]
    ok_count = sum(1 for row in geocoded_rows if _is_reviewable_ok(row))
    upload = _upload_tsv_to_slack(geocoded_rows, slack_thread_url, ok_count=ok_count)
    return {
        "key_source": key_source,
        "geocoded_rows": geocoded_rows,
        "ok_count": ok_count,
        "upload": upload,
        "region_bias": cleaned_region_bias,
        "country_restriction": cleaned_country_restriction,
        "language": cleaned_language,
    }


def _require_https_upload_url(upload_url: str) -> None:
    parsed = urllib.parse.urlparse(upload_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise GoogleGeocodeError("Slack file upload URL must use https.")


def _request_slack_upload_target(token: str, filename: str, content_length: int) -> tuple[str, str]:
    upload = _slack_api_post(
        "files.getUploadURLExternal",
        token,
        {"filename": filename, "length": str(content_length)},
    )
    upload_url = str(upload.get("upload_url") or "")
    file_id = str(upload.get("file_id") or "")
    if not upload_url or not file_id:
        raise GoogleGeocodeError("Slack file upload did not return upload_url and file_id.")
    _require_https_upload_url(upload_url)
    return upload_url, file_id


def _preflight_slack_upload(slack_thread_url: str) -> None:
    _slack_thread_target(slack_thread_url)
    token = _slack_token()
    _request_slack_upload_target(token, "psm-ops-geocode-upload-preflight.tsv", 1)


def _upload_bytes(upload_url: str, content: bytes) -> None:
    _require_https_upload_url(upload_url)
    request = urllib.request.Request(
        upload_url,
        data=content,
        headers={
            "content-type": "text/tab-separated-values; charset=utf-8",
            "content-length": str(len(content)),
            "user-agent": GOOGLE_GEOCODE_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status >= 400:
                raise GoogleGeocodeError(f"Slack file upload URL failed: HTTP {response.status}")
    except urllib.error.HTTPError as error:
        raise GoogleGeocodeError(f"Slack file upload URL failed: HTTP {error.code}") from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleGeocodeError(f"Slack file upload URL timed out or failed: {reason}") from error


def _upload_tsv_to_slack(rows: list[dict[str, Any]], slack_thread_url: str, *, ok_count: int) -> dict[str, str]:
    channel_id, thread_ts = _slack_thread_target(slack_thread_url)
    token = _slack_token()
    content = _tsv_text(rows).encode("utf-8")
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    filename = f"psm-ops-geocoded-addresses-{timestamp}.tsv"
    upload_url, file_id = _request_slack_upload_target(token, filename, len(content))
    _upload_bytes(upload_url, content)
    complete = _slack_api_post(
        "files.completeUploadExternal",
        token,
        {
            "files": json.dumps([{"id": file_id, "title": filename}]),
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "initial_comment": f"Geocoded {ok_count}/{len(rows)} address rows. See attached TSV.",
        },
    )
    return {
        "file_id": file_id,
        "filename": filename,
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "permalink": str((complete.get("file") or {}).get("permalink") or ""),
    }


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("geocode_status") or "UNKNOWN_ERROR")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _is_valid_coordinate(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _is_reviewable_ok(row: dict[str, Any]) -> bool:
    return (
        row.get("geocode_status") == "OK"
        and not row.get("partial_match")
        and _is_valid_coordinate(row.get("latitude"))
        and _is_valid_coordinate(row.get("longitude"))
    )


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
        result = _geocode_rows_and_upload(
            rows,
            region_bias=region_bias,
            country_restriction=country_restriction,
            language=language,
            slack_thread_url=slack_thread_url,
        )
    except GoogleGeocodeError as error:
        return _blocked(str(error), {"slack_thread_url": slack_thread_url})

    geocoded_rows = result["geocoded_rows"]
    ok_count = result["ok_count"]
    upload = result["upload"]
    all_rows_ok = ok_count == len(geocoded_rows)
    confidence = "verified" if all_rows_ok else "needs-check"
    return {
        "answer": {
            "status": "ok" if all_rows_ok else "needs-check",
            "ok_count": ok_count,
            "total_count": len(geocoded_rows),
            "status_counts": _status_counts(geocoded_rows),
            "file": upload,
            "slack_reply": (
                f"Uploaded geocoded TSV file: {upload['filename']} "
                f"({ok_count}/{len(geocoded_rows)} OK)."
            ),
        },
        "source": "Google Geocoding API",
        "scope": {
            "address_count": len(geocoded_rows),
            "region_bias": result["region_bias"],
            "country_restriction": result["country_restriction"],
            "language": result["language"],
            "slack_thread_url": slack_thread_url,
            "key_source": result["key_source"],
        },
        "confidence": confidence,
        "caveat": "Rows with non-OK geocode_status or partial_match=true need manual address review.",
    }


@mcp.tool()
def geocode_slack_address_file(
    slack_thread_url: str,
    file_id: str = "",
    filename: str = "",
    region_bias: str = "sg",
    country_restriction: str = "",
    language: str = "en",
) -> dict[str, Any]:
    """Geocode address rows from a CSV/TSV attachment in the current Slack thread."""
    try:
        selected_file = _select_slack_address_file(slack_thread_url, file_id=file_id, filename=filename)
        content = _download_slack_file(selected_file["url_private"])
        rows = _parse_address_file(
            content,
            filename=selected_file["name"],
            mimetype=selected_file.get("mimetype", ""),
        )
        result = _geocode_rows_and_upload(
            rows,
            region_bias=region_bias,
            country_restriction=country_restriction,
            language=language,
            slack_thread_url=slack_thread_url,
        )
    except GoogleGeocodeError as error:
        return _blocked(str(error), {"slack_thread_url": slack_thread_url, "file_id": file_id, "filename": filename})

    geocoded_rows = result["geocoded_rows"]
    ok_count = result["ok_count"]
    upload = result["upload"]
    all_rows_ok = ok_count == len(geocoded_rows)
    confidence = "verified" if all_rows_ok else "needs-check"
    return {
        "answer": {
            "status": "ok" if all_rows_ok else "needs-check",
            "ok_count": ok_count,
            "total_count": len(geocoded_rows),
            "status_counts": _status_counts(geocoded_rows),
            "file": upload,
            "input_file": {
                "id": selected_file["id"],
                "name": selected_file["name"],
                "message_ts": selected_file["message_ts"],
            },
            "slack_reply": (
                f"Uploaded geocoded TSV file: {upload['filename']} "
                f"({ok_count}/{len(geocoded_rows)} OK)."
            ),
        },
        "source": "Google Geocoding API",
        "scope": {
            "address_count": len(geocoded_rows),
            "input_file": selected_file["name"],
            "region_bias": result["region_bias"],
            "country_restriction": result["country_restriction"],
            "language": result["language"],
            "slack_thread_url": slack_thread_url,
            "key_source": result["key_source"],
        },
        "confidence": confidence,
        "caveat": "Rows with non-OK geocode_status or partial_match=true need manual address review.",
    }


if __name__ == "__main__":
    mcp.run()
