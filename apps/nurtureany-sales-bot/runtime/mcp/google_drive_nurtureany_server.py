#!/usr/bin/env python3
"""Read-only Google Drive MCP adapter for NurtureAny Sales Bot.

This server lists bounded image metadata from the StaffAny team@staffany.com
Drive account, can transiently inspect Drive images for OCR/vision clues, and
can read safe bounded rows from the Indonesia Rev event registration Sheet and
presentation decks explicitly shared to the same account. It never asks for
public link sharing, mutates Drive/Sheets, returns phone numbers/full emails, or
stores raw file or image bytes.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.google_oauth import (
    access_token as _google_access_token,
    account_email as _google_account_email,
    client_credentials as _google_client_credentials,
    load_json as _google_load_json,
    profile_file as _google_profile_file,
    refresh_access_token as _google_refresh_access_token,
    request_json as _google_request_json,
    token_scopes as _google_token_scopes,
    validate_scope as _google_validate_scope,
    write_json as _google_write_json,
)
from nurtureany_common.responses import blocked_response, safe_detail as _safe_detail


GOOGLE_DRIVE_API_BASE_URL = "https://www.googleapis.com/drive/v3"
GOOGLE_SHEETS_API_BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"
GOOGLE_DRIVE_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_SLIDES_MIME_TYPE = "application/vnd.google-apps.presentation"
GOOGLE_SLIDES_EXPORT_MIME_TYPE = "text/plain"
POWERPOINT_MIME_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
DEFAULT_ACCOUNT_EMAIL = "team@staffany.com"
DEFAULT_DRIVE_FOLDER_ID = "1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-"
ID_REV_EVENTS_SPREADSHEET_ID = "1mXixAVJGk0Uy0u1LtOmDFxU3XuW8DRfedB69E1f-drc"
ID_REV_EVENTS_SPREADSHEET_TITLE = "ID REV - LL & HHH EVENTS"
ID_REV_EVENTS_SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{ID_REV_EVENTS_SPREADSHEET_ID}/edit"
GOOGLE_DRIVE_TIMEOUT_SECONDS = 15
MAX_DRIVE_FILES = 100
MAX_VISION_FILES = 5
MAX_IMAGE_BYTES = 7_500_000
MAX_REGISTRATION_ROWS = 250
MAX_REGISTRATION_ROW_SAMPLE = 5
DEFAULT_REGISTRATION_ROW_SAMPLE = 0
MAX_SLIDES_TEXT_CHARS = 30_000
MAX_PRESENTATION_BYTES = 25_000_000
MATERIAL_REGISTRY_SPREADSHEET_ID_ENV = "NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID"
MATERIAL_REGISTRY_SPREADSHEET_URL_TEMPLATE = "https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
MATERIAL_REGISTRY_TABS = (
    "Materials",
    "Playbooks",
    "Peer Intros",
    "Speaker/Venue Opportunities",
    "Events",
    "Review Log",
)
MATERIAL_REGISTRY_FIELDS = (
    "material_id",
    "category",
    "title",
    "url",
    "status",
    "country_scope",
    "industry_tags",
    "concept_tags",
    "persona_tags",
    "valid_from",
    "valid_until",
    "template_name",
    "template_params_schema",
    "message_hook",
    "owner",
)
MATERIAL_REGISTRY_REQUIRED_FIELDS = ("material_id", "status", "title", "message_hook", "owner")
MATERIAL_REGISTRY_FIELD_ALIASES = {
    "url": ("url", "asset_url", "source_evidence_url"),
    "country_scope": ("country_scope", "match_country"),
    "industry_tags": ("industry_tags", "match_industry"),
    "concept_tags": ("concept_tags", "match_concept"),
    "persona_tags": ("persona_tags", "match_persona"),
}
MATERIAL_REGISTRY_EXTRA_FIELDS = (
    "kns_pillar",
    "pillar_summary",
    "buyer_value",
    "ae_use_case",
    "whatsapp_script",
    "source_evidence_url",
    "asset_url",
    "talk_track",
)
MATERIAL_REGISTRY_DEFAULT_TEMPLATE_NAME = "nurture_material_share_v1"
MATERIAL_REGISTRY_DEFAULT_TEMPLATE_SCHEMA = "first_name,company_name,message_hook,material_url"
MAX_MATERIAL_REGISTRY_ROWS_PER_TAB = 500
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_VISION_MODEL = "claude-sonnet-4-6"
SUPPORTED_VISION_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}
REGISTRATION_COLUMN_ALIASES = {
    "name": ("name",),
    "email": ("email",),
    "approval_status": ("approvalstatus", "approval"),
    "job_role": ("jobrole",),
    "job_title": ("jobtitle", "title"),
    "company_name": ("companyname", "company"),
    "industry": ("industry",),
    "total_employees": ("totalemployees", "employees", "headcount"),
    "invited_by": ("whoinvitedyoutothisevent", "invitedby"),
    "account_mapping": ("accountmapping",),
    "rsvp_confirmation": ("rsvpsconfirmation", "rsvpconfirmation", "rsvp"),
    "wa_confirm": ("waconfirm", "whatsappconfirm"),
    "attend_the_event": ("attendtheevent", "attended", "attendance"),
    "qo_set": ("qoset",),
    "remarks": ("remarks",),
}
SLACK_API_BASE_URL = "https://slack.com/api"
SLACK_BOT_TOKEN_ENV = "SLACK_BOT_TOKEN"
SLACK_USER_ID_PATTERN = re.compile(r"^[UW][A-Z0-9]+$")
SLACK_EXPORT_FILENAME_PATTERN = re.compile(
    r"^(?P<source_timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)-(?P<slack_user_id>[UW][A-Z0-9]+)-(?P<original_filename>.+)$"
)
GOOGLE_SLIDES_URL_ID_PATTERN = re.compile(r"/presentation/(?:u/\d+/)?d/([A-Za-z0-9_-]{20,})")
GOOGLE_SLIDES_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,}$")
_SLACK_USER_CACHE: dict[str, dict[str, str]] = {}


mcp = FastMCP(
    "google_drive_nurtureany",
    instructions=(
        "Read-only Google Drive and Slides access for NurtureAny. Use only the "
        "team@staffany.com account, list bounded image metadata, read selected Google Slides decks, "
        "extract transient vision/OCR clues, and never ask for public link sharing, store raw images, "
        "or mutate Drive files."
    ),
)


class GoogleDriveError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _account_email() -> str:
    return _google_account_email("GOOGLE_DRIVE_ACCOUNT_EMAIL", DEFAULT_ACCOUNT_EMAIL)


def _token_file():
    return _google_profile_file("GOOGLE_DRIVE_TOKEN_FILE", "google-drive-token.json")


def _client_secret_file():
    return _google_profile_file("GOOGLE_DRIVE_CLIENT_SECRET_FILE", "google-drive-client-secret.json")


def _load_json(path) -> dict[str, Any]:
    return _google_load_json(path, "Google Drive", GoogleDriveError)


def _write_json(path, payload: dict[str, Any]) -> None:
    _google_write_json(path, payload)


def _scope(slack_user_email: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {
        "caller_email": (slack_user_email or "").strip().lower(),
        "drive_account_email": _account_email(),
        "read_only": True,
    }
    if extra:
        scope.update(extra)
    return scope


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(message, "Google Drive", scope)


def _token_scopes(payload: dict[str, Any]) -> set[str]:
    return _google_token_scopes(payload)


def _validate_scope(payload: dict[str, Any]) -> None:
    _google_validate_scope(payload, {DRIVE_READONLY_SCOPE}, "Google Drive", GoogleDriveError)


def _client_credentials(payload: dict[str, Any]) -> tuple[str, str]:
    return _google_client_credentials(payload, _client_secret_file(), "Google Drive", GoogleDriveError)


def _refresh_access_token(payload: dict[str, Any], token_path) -> str:
    return _google_refresh_access_token(
        payload,
        token_path,
        _client_secret_file(),
        GOOGLE_DRIVE_USER_AGENT,
        GOOGLE_DRIVE_TIMEOUT_SECONDS,
        "Google Drive",
        GoogleDriveError,
    )


def _access_token() -> str:
    return _google_access_token(
        _token_file(),
        _client_secret_file(),
        {DRIVE_READONLY_SCOPE},
        GOOGLE_DRIVE_USER_AGENT,
        GOOGLE_DRIVE_TIMEOUT_SECONDS,
        "Google Drive",
        GoogleDriveError,
    )


def _parse_drive_photo_name(name: str) -> dict[str, str]:
    match = SLACK_EXPORT_FILENAME_PATTERN.match(name or "")
    if not match:
        return {"source_timestamp": "", "slack_user_id": "", "original_filename": name or ""}
    return match.groupdict()


def _slack_bot_token() -> str:
    return os.environ.get(SLACK_BOT_TOKEN_ENV, "").strip()


def _slack_user_profile(user_id: str) -> dict[str, str]:
    selected_user_id = (user_id or "").strip()
    if not SLACK_USER_ID_PATTERN.match(selected_user_id):
        return {}
    if selected_user_id in _SLACK_USER_CACHE:
        return dict(_SLACK_USER_CACHE[selected_user_id])
    token = _slack_bot_token()
    if not token:
        return {}
    query = urllib.parse.urlencode({"user": selected_user_id})
    request = urllib.request.Request(
        f"{SLACK_API_BASE_URL}/users.info?{query}",
        headers={"authorization": f"Bearer {token}", "accept": "application/json", "user-agent": GOOGLE_DRIVE_USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_DRIVE_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, TimeoutError, json.JSONDecodeError):
        return {}
    if not payload.get("ok"):
        return {}
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    profile = user.get("profile") if isinstance(user.get("profile"), dict) else {}
    display_name = str(profile.get("display_name") or profile.get("real_name") or user.get("real_name") or user.get("name") or "").strip()
    if not display_name:
        return {}
    result = {"id": selected_user_id, "name": display_name, "profile_source": "slack_users_info"}
    _SLACK_USER_CACHE[selected_user_id] = result
    return dict(result)


def _request_json(path: str, params: dict[str, Any], access_token: str) -> dict[str, Any]:
    return _google_request_json(
        GOOGLE_DRIVE_API_BASE_URL,
        path,
        params,
        access_token,
        GOOGLE_DRIVE_USER_AGENT,
        GOOGLE_DRIVE_TIMEOUT_SECONDS,
        "Google Drive",
        GoogleDriveError,
    )


def _request_bytes(path: str, params: dict[str, Any], access_token: str, max_bytes: int) -> tuple[bytes, str]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = f"{GOOGLE_DRIVE_API_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "authorization": f"Bearer {access_token}",
            "accept": "*/*",
            "user-agent": GOOGLE_DRIVE_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_DRIVE_TIMEOUT_SECONDS) as response:
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                raise GoogleDriveError("Drive image exceeds transient vision byte cap.", 413)
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise GoogleDriveError("Drive image exceeds transient vision byte cap.", 413)
            media_type = response.headers.get_content_type() or ""
            return data, media_type
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise GoogleDriveError(f"Google Drive API failed: {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleDriveError(f"Google Drive API request timed out or failed: {reason}") from error


def _request_export_text(file_id: str, access_token: str, max_bytes: int = MAX_SLIDES_TEXT_CHARS * 4) -> str:
    file_path = f"/files/{urllib.parse.quote(file_id, safe='')}/export"
    data, _media_type = _request_bytes(
        file_path,
        {"mimeType": GOOGLE_SLIDES_EXPORT_MIME_TYPE},
        access_token,
        max_bytes,
    )
    return data.decode("utf-8", errors="replace")


def _request_sheets_json(spreadsheet_id: str, path: str, params: dict[str, Any], access_token: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    quoted_id = urllib.parse.quote(spreadsheet_id, safe="")
    url = f"{GOOGLE_SHEETS_API_BASE_URL}/{quoted_id}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "authorization": f"Bearer {access_token}",
            "accept": "application/json",
            "user-agent": GOOGLE_DRIVE_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_DRIVE_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise GoogleDriveError(f"Google Sheets API failed: {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleDriveError(f"Google Sheets API request timed out or failed: {reason}") from error


def _drive_query(folder_id: str, include_trashed: bool) -> str:
    safe_folder_id = (folder_id or DEFAULT_DRIVE_FOLDER_ID).replace("'", "\\'")
    parts = [f"'{safe_folder_id}' in parents", "mimeType contains 'image/'"]
    if not include_trashed:
        parts.append("trashed = false")
    return " and ".join(parts)


def _safe_file(file: dict[str, Any], folder_id: str, include_uploader_profile: bool = True) -> dict[str, Any]:
    name = file.get("name") or ""
    parsed = _parse_drive_photo_name(name)
    result = {
        "id": file.get("id") or "",
        "name": name,
        "mimeType": file.get("mimeType") or "",
        "createdTime": file.get("createdTime") or "",
        "modifiedTime": file.get("modifiedTime") or "",
        "webViewLink": file.get("webViewLink") or "",
        "md5Checksum": file.get("md5Checksum") or "",
        "size": file.get("size") or "",
        "folder_id": folder_id,
        "source_timestamp": parsed.get("source_timestamp") or "",
        "slack_user_id": parsed.get("slack_user_id") or "",
        "original_filename": parsed.get("original_filename") or name,
    }
    if include_uploader_profile and result["slack_user_id"]:
        uploader = _slack_user_profile(result["slack_user_id"])
        if uploader:
            result["slack_uploader_name"] = uploader["name"]
            result["slack_uploader_profile_source"] = uploader["profile_source"]
    return result


def _safe_folder(folder: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": folder.get("id") or "",
        "name": folder.get("name") or "",
        "mimeType": folder.get("mimeType") or "",
        "webViewLink": folder.get("webViewLink") or "",
        "driveId": folder.get("driveId") or "",
        "trashed": bool(folder.get("trashed")),
    }


def _safe_presentation(file: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": file.get("id") or "",
        "name": file.get("name") or "",
        "mimeType": file.get("mimeType") or "",
        "webViewLink": file.get("webViewLink") or "",
        "driveId": file.get("driveId") or "",
        "trashed": bool(file.get("trashed")),
        "modifiedTime": file.get("modifiedTime") or "",
        "size": file.get("size") or "",
    }


def _extract_presentation_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if GOOGLE_SLIDES_ID_PATTERN.match(text):
        return text
    parsed = urllib.parse.urlparse(text)
    match = GOOGLE_SLIDES_URL_ID_PATTERN.search(parsed.path or "")
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([A-Za-z0-9_-]{20,})", text)
    if match:
        return match.group(1)
    return ""


def _normalize_slides_text(raw_text: str, max_chars: int) -> tuple[str, bool, int]:
    text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compact_lines.append(line)
        previous_blank = blank
    normalized = "\n".join(compact_lines).strip()
    total_chars = len(normalized)
    if total_chars > max_chars:
        return normalized[:max_chars].rstrip(), True, total_chars
    return normalized, False, total_chars


def _slide_sort_key(path: str) -> tuple[int, str]:
    match = re.search(r"slide(\d+)\.xml$", path)
    if match:
        return int(match.group(1)), path
    return 10**9, path


def _extract_pptx_slide_texts(slide_xml: bytes) -> list[str]:
    try:
        root = ET.fromstring(slide_xml)
        return [
            str(node.text or "").strip()
            for node in root.iter()
            if node.tag.endswith("}t") and str(node.text or "").strip()
        ]
    except (ET.ParseError, ImportError):
        xml_text = slide_xml.decode("utf-8", errors="ignore")
        texts = []
        for match in re.finditer(r"<(?:[A-Za-z0-9_]+:)?t(?:\s[^>]*)?>(.*?)</(?:[A-Za-z0-9_]+:)?t>", xml_text, flags=re.DOTALL):
            text = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
            if text:
                texts.append(text)
        return texts


def _extract_pptx_text(pptx_bytes: bytes, max_chars: int) -> tuple[str, bool, int]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(pptx_bytes))
    except zipfile.BadZipFile as error:
        raise GoogleDriveError("PowerPoint file could not be parsed as a PPTX archive.", 422) from error
    with archive:
        slide_paths = sorted(
            [
                name
                for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ],
            key=_slide_sort_key,
        )
        chunks: list[str] = []
        for index, slide_path in enumerate(slide_paths, start=1):
            texts = _extract_pptx_slide_texts(archive.read(slide_path))
            if texts:
                chunks.append(f"Slide {index}\n" + "\n".join(texts))
    return _normalize_slides_text("\n\n".join(chunks), max_chars)


def _media_type_for_image(metadata: dict[str, Any], downloaded_media_type: str = "") -> str:
    media_type = (downloaded_media_type or metadata.get("mimeType") or metadata.get("mime_type") or "").strip().lower()
    if media_type == "image/jpg":
        return "image/jpeg"
    return media_type


def _normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _column_index(headers: list[Any], aliases: tuple[str, ...]) -> int | None:
    normalized = [_normalize_header(header) for header in headers]
    for alias in aliases:
        try:
            return normalized.index(alias)
        except ValueError:
            continue
    return None


def _cell(row: list[Any], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index] or "").strip()


def _truthy_sheet_value(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"true", "yes", "y", "attended", "attend", "came", "present", "1"}


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _email_hash(value: str) -> str:
    email = _normalize_email(value)
    if not email:
        return ""
    return hashlib.sha256(email.encode("utf-8")).hexdigest()


def _email_domain(value: str) -> str:
    email = _normalize_email(value)
    if "@" not in email:
        return ""
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if "." not in domain or domain in PERSONAL_EMAIL_DOMAINS:
        return ""
    return domain


def _clean_company_name(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:160]


def _unique_limited(values: list[str], limit: int = 250) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        unique.append(text)
        if len(unique) >= limit:
            break
    return unique


def _event_sheet_tokens(event_name: str, event_date: str, event_tags: list[str] | None) -> list[str]:
    if isinstance(event_tags, str):
        event_tags = [event_tags]
    raw_tokens = [event_name or "", event_date or ""]
    raw_tokens.extend(event_tags or [])
    joined = " ".join(raw_tokens).lower()
    tokens = []
    if "bali" in joined:
        tokens.append("bali")
    if "jakarta" in joined or "jkt" in joined:
        tokens.extend(["jakarta", "jkt"])
    if "happy hr" in joined or "hr happy" in joined or "hhh" in joined:
        tokens.append("hhh")
    if "leaders lounge" in joined or re.search(r"\bll\b", joined):
        tokens.append("ll")
    iso_match = re.search(r"\b\d{4}-(\d{1,2})-(\d{1,2})\b", event_date or "")
    date_match = iso_match or re.search(r"(?:^|\D)(\d{1,2})[/-](\d{1,2})(?:[/-]\d{2,4})?", event_date or "")
    if date_match:
        if iso_match:
            month, day = int(date_match.group(1)), int(date_match.group(2))
        else:
            day, month = int(date_match.group(1)), int(date_match.group(2))
        month_names = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        if 1 <= month <= 12:
            tokens.extend([str(day), month_names[month - 1]])
    for month in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"):
        if month in joined:
            tokens.append(month)
    for number in re.findall(r"\b\d{1,2}\b", event_date or event_name or ""):
        tokens.append(str(int(number)))
    return _unique_limited(tokens, 20)


def _sheet_title_score(title: str, tokens: list[str]) -> int:
    normalized = title.lower()
    score = 0
    if "rsvp" in normalized:
        score += 5
    if "feedback" in normalized or "laundry" in normalized or "summary" in normalized:
        score -= 4
    for token in tokens:
        if token and token.lower() in normalized:
            score += 3
    return score


def _select_registration_sheet(sheets: list[dict[str, Any]], sheet_name: str, event_name: str, event_date: str, event_tags: list[str] | None) -> dict[str, Any] | None:
    if sheet_name:
        for sheet in sheets:
            props = sheet.get("properties") if isinstance(sheet.get("properties"), dict) else {}
            if str(props.get("title") or "").strip().lower() == sheet_name.strip().lower():
                return sheet
        return None

    tokens = _event_sheet_tokens(event_name, event_date, event_tags)
    candidates = []
    for sheet in sheets:
        props = sheet.get("properties") if isinstance(sheet.get("properties"), dict) else {}
        title = str(props.get("title") or "")
        if not title:
            continue
        score = _sheet_title_score(title, tokens)
        if score > 0:
            candidates.append((score, int(props.get("index") or 0), sheet))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _material_registry_spreadsheet_id() -> str:
    return os.environ.get(MATERIAL_REGISTRY_SPREADSHEET_ID_ENV, "").strip()


def _material_registry_contract() -> dict[str, Any]:
    return {
        "spreadsheet_id_env_var": MATERIAL_REGISTRY_SPREADSHEET_ID_ENV,
        "tabs": list(MATERIAL_REGISTRY_TABS),
        "minimum_fields": list(MATERIAL_REGISTRY_FIELDS),
        "required_fields": list(MATERIAL_REGISTRY_REQUIRED_FIELDS),
        "accepted_aliases": MATERIAL_REGISTRY_FIELD_ALIASES,
        "read_only": True,
    }


def _material_field_map(headers: list[Any]) -> dict[str, int | None]:
    normalized = [_normalize_header(header) for header in headers]
    mapping: dict[str, int | None] = {}
    for field in MATERIAL_REGISTRY_FIELDS:
        aliases = MATERIAL_REGISTRY_FIELD_ALIASES.get(field, (field,))
        mapping[field] = None
        for alias in aliases:
            key = _normalize_header(alias)
            try:
                mapping[field] = normalized.index(key)
                break
            except ValueError:
                continue
    for field in MATERIAL_REGISTRY_EXTRA_FIELDS:
        key = _normalize_header(field)
        try:
            mapping[field] = normalized.index(key)
        except ValueError:
            mapping[field] = None
    return mapping


def _safe_material_registry_row(row: list[Any], row_number: int, columns: dict[str, int | None], tab_name: str) -> dict[str, Any]:
    safe = {
        field: _cell(row, columns.get(field))[:1000]
        for field in MATERIAL_REGISTRY_FIELDS
    }
    if not safe["category"]:
        safe["category"] = "case_study" if safe["material_id"].startswith("case-study:") else "kns_material"
    if not safe["template_name"]:
        safe["template_name"] = MATERIAL_REGISTRY_DEFAULT_TEMPLATE_NAME
    if not safe["template_params_schema"]:
        safe["template_params_schema"] = MATERIAL_REGISTRY_DEFAULT_TEMPLATE_SCHEMA
    for field in MATERIAL_REGISTRY_EXTRA_FIELDS:
        value = _cell(row, columns.get(field))[:1000]
        if value:
            safe[field] = value
    safe["source_tab"] = tab_name
    safe["row_number"] = row_number
    return safe


def _download_drive_file_bytes(file_id: str, access_token: str, max_bytes: int = MAX_IMAGE_BYTES) -> tuple[bytes, str]:
    file_path = f"/files/{urllib.parse.quote(file_id, safe='')}"
    return _request_bytes(file_path, {"alt": "media", "supportsAllDrives": "true"}, access_token, max_bytes)


def _vision_model() -> str:
    return (
        os.environ.get("NURTUREANY_DRIVE_VISION_MODEL", "").strip()
        or os.environ.get("ANTHROPIC_VISION_MODEL", "").strip()
        or DEFAULT_VISION_MODEL
    )


def _anthropic_api_key() -> str:
    return os.environ.get(ANTHROPIC_API_KEY_ENV, "").strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    if not match:
        return {}
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_message_text(message: Any) -> str:
    parts = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", "")
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _normalize_vision_clues(payload: dict[str, Any], fallback_text: str = "") -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    list_keys = (
        "company_names",
        "contact_names",
        "person_names",
        "roles",
        "event_names",
        "countries",
        "locations",
        "badge_text",
        "signage",
    )
    for key in list_keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = [value.strip()]
        elif isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if cleaned:
                normalized[key] = cleaned[:10]
    for key in ("ocr_text", "visual_context", "confidence"):
        value = str(payload.get(key) or "").strip()
        if value:
            normalized[key] = value[:1500]
    if "needs_human_clue" in payload:
        normalized["needs_human_clue"] = bool(payload.get("needs_human_clue"))
    if not normalized and fallback_text:
        normalized["text"] = _safe_detail(fallback_text)
        normalized["needs_human_clue"] = True
    return normalized


def _run_anthropic_vision(image_bytes: bytes, media_type: str, filename: str, context_text: str = "") -> dict[str, Any]:
    api_key = _anthropic_api_key()
    if not api_key:
        raise GoogleDriveError(f"Missing {ANTHROPIC_API_KEY_ENV} for Drive vision/OCR.")
    try:
        import anthropic
    except ImportError as error:
        raise GoogleDriveError("Anthropic SDK is unavailable for Drive vision/OCR.") from error

    prompt = (
        "Extract CRM matching clues from this StaffAny event photo. Do not identify anyone by face "
        "recognition. Use only visible text, badges, lanyards, signage, logos, captions, and non-sensitive "
        "scene context. Return strict JSON only with keys: company_names, contact_names, roles, event_names, "
        "countries, locations, ocr_text, visual_context, confidence, needs_human_clue. Use empty arrays when "
        "nothing is visible. Set needs_human_clue=true when company/contact clues are not visible."
    )
    if filename:
        prompt += f"\nFilename: {filename}"
    if context_text:
        prompt += f"\nSlack/Drive context: {context_text[:500]}"

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=_vision_model(),
        max_tokens=800,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    text = _extract_message_text(message)
    return _normalize_vision_clues(_parse_json_object(text), text)


@mcp.tool()
def list_drive_folder_images(
    slack_user_email: str,
    folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
    limit: int = 20,
    include_trashed: bool = False,
    account_email: str = DEFAULT_ACCOUNT_EMAIL,
    include_uploader_profile: bool = True,
) -> dict[str, Any]:
    """List bounded read-only image metadata from the team@staffany.com Drive folder."""

    configured_account = _account_email()
    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    selected_folder_id = (folder_id or DEFAULT_DRIVE_FOLDER_ID).strip()
    capped_limit = max(1, min(int(limit or 20), MAX_DRIVE_FILES))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "drive_access_mode": "team_oauth_drive_readonly",
            "folder_id": selected_folder_id,
            "max_files": capped_limit,
            "include_trashed": bool(include_trashed),
            "include_uploader_profile": bool(include_uploader_profile),
            "safety": "Metadata only. No image bytes, Drive mutations, exports, or raw image copies.",
        },
    )

    if requested_account != configured_account:
        return _blocked("Google Drive connector is restricted to team@staffany.com.", scope)

    try:
        access_token = _access_token()
        folder_path = f"/files/{urllib.parse.quote(selected_folder_id, safe='')}"
        folder_params = {
            "fields": "id,name,mimeType,webViewLink,trashed,driveId",
            "supportsAllDrives": "true",
        }
        try:
            folder_payload = _request_json(folder_path, folder_params, access_token)
        except GoogleDriveError as error:
            if error.status_code != 401:
                raise
            access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
            folder_payload = _request_json(folder_path, folder_params, access_token)
        folder = _safe_folder(folder_payload)
        if folder.get("mimeType") != "application/vnd.google-apps.folder":
            return _blocked("Google Drive target is not a folder.", {**scope, "folder": folder})
        if folder.get("trashed"):
            return _blocked("Google Drive target folder is trashed.", {**scope, "folder": folder})
        scope["folder"] = folder
        params = {
            "q": _drive_query(selected_folder_id, bool(include_trashed)),
            "pageSize": capped_limit,
            "orderBy": "modifiedTime desc",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "nextPageToken,files(id,name,mimeType,createdTime,modifiedTime,webViewLink,md5Checksum,size)",
        }
        try:
            payload = _request_json("/files", params, access_token)
        except GoogleDriveError as error:
            if error.status_code != 401:
                raise
            access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
            payload = _request_json("/files", params, access_token)
    except GoogleDriveError as error:
        return _blocked(str(error), scope)

    files = [
        _safe_file(file, selected_folder_id, include_uploader_profile=bool(include_uploader_profile))
        for file in payload.get("files", [])
        if isinstance(file, dict)
    ]
    return {
        "answer": files,
        "source": "Google Drive",
        "scope": scope,
        "total": len(files),
        "requested_limit": capped_limit,
        "returned_count": len(files),
        "has_more": bool(payload.get("nextPageToken")),
        "truncated": bool(payload.get("nextPageToken")),
        "confidence": "needs-check",
        "caveat": "Drive output is metadata only. Pass these file records to scan_drive_event_photos; download images only transiently for vision/OCR.",
    }


@mcp.tool()
def read_google_slides_deck(
    slack_user_email: str,
    presentation_url_or_id: str,
    account_email: str = DEFAULT_ACCOUNT_EMAIL,
    max_text_chars: int = MAX_SLIDES_TEXT_CHARS,
) -> dict[str, Any]:
    """Read text from a selected Google Slides or Drive-hosted PPTX deck through team@staffany.com.

    The deck must already be accessible to the configured team OAuth account.
    If access is blocked, ask for viewer access to team@staffany.com instead of
    public-link sharing. Native Slides are exported as text; PPTX files are
    downloaded transiently for ZIP/XML text extraction and discarded. The output
    is bounded text only and does not mutate or publish the deck.
    """

    configured_account = _account_email()
    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    presentation_id = _extract_presentation_id(presentation_url_or_id)
    capped_chars = max(1, min(int(max_text_chars or MAX_SLIDES_TEXT_CHARS), MAX_SLIDES_TEXT_CHARS))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "drive_access_mode": "team_oauth_drive_readonly",
            "presentation_id": presentation_id,
            "max_text_chars": capped_chars,
            "safety": "Text-only presentation extraction through Drive API. No public link sharing, Drive mutations, comments, edits, persistent file download, or raw file bytes returned.",
        },
    )

    if requested_account != configured_account:
        return _blocked("Google Drive connector is restricted to team@staffany.com.", scope)
    if not presentation_id:
        return _blocked("Could not parse a Google Slides presentation ID from the supplied URL or ID.", scope)

    try:
        access_token = _access_token()
        file_path = f"/files/{urllib.parse.quote(presentation_id, safe='')}"
        metadata_params = {
            "fields": "id,name,mimeType,webViewLink,trashed,driveId,modifiedTime,size",
            "supportsAllDrives": "true",
        }
        try:
            file_payload = _request_json(file_path, metadata_params, access_token)
        except GoogleDriveError as error:
            if error.status_code != 401:
                raise
            access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
            file_payload = _request_json(file_path, metadata_params, access_token)
        presentation = _safe_presentation(file_payload)
        if presentation.get("trashed"):
            return _blocked("Google Slides deck is trashed.", {**scope, "presentation": presentation})
        mime_type = presentation.get("mimeType")
        if mime_type == GOOGLE_SLIDES_MIME_TYPE:
            try:
                exported_text = _request_export_text(presentation_id, access_token)
            except GoogleDriveError as error:
                if error.status_code != 401:
                    raise
                access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
                exported_text = _request_export_text(presentation_id, access_token)
            slide_text, text_truncated, text_char_count = _normalize_slides_text(exported_text, capped_chars)
            extraction_method = "google_slides_export_text"
        elif mime_type == POWERPOINT_MIME_TYPE:
            try:
                pptx_bytes, _downloaded_media_type = _download_drive_file_bytes(
                    presentation_id,
                    access_token,
                    MAX_PRESENTATION_BYTES,
                )
            except GoogleDriveError as error:
                if error.status_code != 401:
                    raise
                access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
                pptx_bytes, _downloaded_media_type = _download_drive_file_bytes(
                    presentation_id,
                    access_token,
                    MAX_PRESENTATION_BYTES,
                )
            slide_text, text_truncated, text_char_count = _extract_pptx_text(pptx_bytes, capped_chars)
            del pptx_bytes
            extraction_method = "pptx_transient_zip_xml_text"
        else:
            return _blocked("Google Drive file is not a supported presentation type. Supported: Google Slides or .pptx.", {**scope, "presentation": presentation})
    except GoogleDriveError as error:
        if error.status_code in (403, 404):
            return _blocked(
                "Google Slides deck is not accessible to team@staffany.com. Ask the owner to share viewer access with team@staffany.com or an approved StaffAny group that includes it; do not request public link sharing.",
                scope,
            )
        return _blocked(str(error), scope)

    return {
        "answer": {
            "presentation": presentation,
            "slide_text": slide_text,
            "text_char_count": text_char_count,
            "text_truncated": text_truncated,
            "extraction_method": extraction_method,
            "raw_file_retained": False,
            "next_step": "Use the extracted slide_text to ground the requested nurture/cadence work; do not paste the full deck text back unless explicitly asked.",
        },
        "source": "Google Drive presentation text extraction",
        "scope": {**scope, "presentation": presentation},
        "total": 1,
        "requested_limit": capped_chars,
        "returned_count": len(slide_text),
        "has_more": text_truncated,
        "truncated": text_truncated,
        "confidence": "needs-check" if text_truncated else "verified",
        "caveat": "Text-only presentation extraction. Share the deck with team@staffany.com if access is blocked; do not make private decks public for the bot.",
    }


@mcp.tool()
def extract_drive_image_clues(
    slack_user_email: str,
    drive_files: list[dict[str, Any]],
    folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
    limit: int = MAX_VISION_FILES,
    context_text: str = "",
    account_email: str = DEFAULT_ACCOUNT_EMAIL,
    max_image_bytes: int = MAX_IMAGE_BYTES,
) -> dict[str, Any]:
    """Download Drive images transiently and return LLM vision/OCR clues only."""

    configured_account = _account_email()
    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    selected_folder_id = (folder_id or DEFAULT_DRIVE_FOLDER_ID).strip()
    capped_limit = max(1, min(int(limit or MAX_VISION_FILES), MAX_VISION_FILES))
    capped_bytes = max(1, min(int(max_image_bytes or MAX_IMAGE_BYTES), MAX_IMAGE_BYTES))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "drive_access_mode": "team_oauth_drive_readonly",
            "folder_id": selected_folder_id,
            "max_files": capped_limit,
            "max_image_bytes": capped_bytes,
            "vision_model": _vision_model(),
            "safety": "Transient download for OCR/vision only. Raw image bytes are discarded and never returned.",
        },
    )

    if requested_account != configured_account:
        return _blocked("Google Drive connector is restricted to team@staffany.com.", scope)
    if not isinstance(drive_files, list):
        return _blocked("drive_files must be a list of Drive file metadata records.", scope)
    if not _anthropic_api_key():
        return _blocked(f"Missing {ANTHROPIC_API_KEY_ENV} for Drive vision/OCR.", scope)

    clues = []
    skipped = []
    try:
        access_token = _access_token()
        for raw_file in drive_files[:capped_limit]:
            if not isinstance(raw_file, dict):
                skipped.append({"reason": "invalid_file_metadata"})
                continue
            metadata = {**raw_file, "folder_id": selected_folder_id}
            file_id = str(metadata.get("id") or metadata.get("file_id") or metadata.get("fileId") or "").strip()
            filename = str(metadata.get("name") or metadata.get("filename") or metadata.get("title") or "").strip()
            media_type = _media_type_for_image(metadata)
            if not file_id:
                skipped.append({"name": filename, "reason": "missing_file_id"})
                continue
            if media_type and media_type not in SUPPORTED_VISION_MEDIA_TYPES:
                skipped.append({"file_id": file_id, "name": filename, "mime_type": media_type, "reason": "unsupported_image_type"})
                continue
            try:
                try:
                    image_bytes, downloaded_media_type = _download_drive_file_bytes(file_id, access_token, capped_bytes)
                except GoogleDriveError as error:
                    if error.status_code != 401:
                        raise
                    access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
                    image_bytes, downloaded_media_type = _download_drive_file_bytes(file_id, access_token, capped_bytes)
                media_type = _media_type_for_image(metadata, downloaded_media_type)
                if media_type not in SUPPORTED_VISION_MEDIA_TYPES:
                    skipped.append({"file_id": file_id, "name": filename, "mime_type": media_type, "reason": "unsupported_image_type"})
                    continue
                vision_clues = _run_anthropic_vision(image_bytes, media_type, filename, context_text)
                del image_bytes
                clues.append(
                    {
                        "file_id": file_id,
                        "name": filename,
                        "mime_type": media_type,
                        "folder_id": selected_folder_id,
                        "vision_clues": vision_clues,
                        "raw_image_retained": False,
                        "next_tool": "propose_photo_people_matches",
                    }
                )
            except GoogleDriveError as error:
                skipped.append({"file_id": file_id, "name": filename, "reason": str(error)})
    except GoogleDriveError as error:
        return _blocked(str(error), scope)

    return {
        "answer": {
            "image_clues": clues,
            "processed_count": len(clues),
            "skipped": skipped,
            "raw_image_retained": False,
            "next_tool": "propose_photo_people_matches",
        },
        "source": "Google Drive transient image download plus Anthropic vision/OCR",
        "scope": scope,
        "total": len(drive_files),
        "requested_limit": capped_limit,
        "returned_count": len(clues),
        "has_more": len(drive_files) > capped_limit,
        "truncated": len(drive_files) > capped_limit,
        "confidence": "needs-check",
        "caveat": "Only extracted text/clues are returned. Raw image bytes are discarded and no Drive or HubSpot mutation is performed.",
    }


def _registration_column_map(headers: list[Any]) -> dict[str, int | None]:
    return {key: _column_index(headers, aliases) for key, aliases in REGISTRATION_COLUMN_ALIASES.items()}


def _safe_registration_row(row: list[Any], row_number: int, columns: dict[str, int | None]) -> dict[str, Any]:
    email = _normalize_email(_cell(row, columns.get("email")))
    company_name = _clean_company_name(_cell(row, columns.get("company_name")))
    safe = {
        "row_number": row_number,
        "company_name": company_name,
        "approval_status": _cell(row, columns.get("approval_status")),
        "job_role": _cell(row, columns.get("job_role")),
        "job_title": _cell(row, columns.get("job_title")),
        "industry": _cell(row, columns.get("industry")),
        "employee_band": _cell(row, columns.get("total_employees")),
        "invited_by": _cell(row, columns.get("invited_by")),
        "account_mapping": _cell(row, columns.get("account_mapping")),
        "rsvp_confirmation": _cell(row, columns.get("rsvp_confirmation")),
        "wa_confirm": _cell(row, columns.get("wa_confirm")),
        "attended": _truthy_sheet_value(_cell(row, columns.get("attend_the_event"))),
        "qo_set": _cell(row, columns.get("qo_set")),
        "remarks": _cell(row, columns.get("remarks")),
        "email_domain": _email_domain(email),
        "email_hash": _email_hash(email),
    }
    return {key: value for key, value in safe.items() if value not in ("", None)}


@mcp.tool()
def read_nurture_material_registry(
    slack_user_email: str,
    spreadsheet_id: str = "",
    tabs: list[str] | None = None,
    limit_per_tab: int = MAX_MATERIAL_REGISTRY_ROWS_PER_TAB,
    account_email: str = DEFAULT_ACCOUNT_EMAIL,
) -> dict[str, Any]:
    """Read the one-sheet NurtureAny nurture material registry."""

    configured_account = _account_email()
    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    selected_spreadsheet_id = (spreadsheet_id or _material_registry_spreadsheet_id()).strip()
    selected_tabs = [str(tab or "").strip() for tab in (tabs or list(MATERIAL_REGISTRY_TABS)) if str(tab or "").strip()]
    capped_limit = max(1, min(int(limit_per_tab or MAX_MATERIAL_REGISTRY_ROWS_PER_TAB), MAX_MATERIAL_REGISTRY_ROWS_PER_TAB))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "drive_access_mode": "team_oauth_drive_readonly",
            "spreadsheet_id": selected_spreadsheet_id,
            "registry_contract": _material_registry_contract(),
            "safety": "Read-only material registry rows only. No phone numbers, full emails, raw exports, or Drive mutations.",
        },
    )

    if requested_account != configured_account:
        return _blocked("Google Drive connector is restricted to team@staffany.com.", scope)
    if not selected_spreadsheet_id:
        return _blocked(f"Missing {MATERIAL_REGISTRY_SPREADSHEET_ID_ENV} or explicit spreadsheet_id.", scope)

    try:
        access_token = _access_token()
        metadata_params = {"fields": "properties(title),sheets(properties(sheetId,title,index,hidden))"}
        try:
            metadata = _request_sheets_json(selected_spreadsheet_id, "", metadata_params, access_token)
        except GoogleDriveError as error:
            if error.status_code != 401:
                raise
            access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
            metadata = _request_sheets_json(selected_spreadsheet_id, "", metadata_params, access_token)
    except GoogleDriveError as error:
        return _blocked(str(error), scope)

    sheets = metadata.get("sheets") if isinstance(metadata.get("sheets"), list) else []
    available_tabs = {
        str((sheet.get("properties") if isinstance(sheet.get("properties"), dict) else {}).get("title") or ""): sheet
        for sheet in sheets
    }
    rows: list[dict[str, Any]] = []
    missing_tabs: list[str] = []
    invalid_tabs: list[dict[str, Any]] = []

    for tab_name in selected_tabs:
        if tab_name not in available_tabs:
            missing_tabs.append(tab_name)
            continue
        encoded_range = urllib.parse.quote(f"'{tab_name}'!A1:ZZ{capped_limit + 1}", safe="")
        try:
            values_payload = _request_sheets_json(
                selected_spreadsheet_id,
                f"/values/{encoded_range}",
                {"valueRenderOption": "FORMATTED_VALUE"},
                access_token,
            )
        except GoogleDriveError as error:
            invalid_tabs.append({"tab": tab_name, "reason": str(error)})
            continue
        values = values_payload.get("values") if isinstance(values_payload.get("values"), list) else []
        if not values:
            invalid_tabs.append({"tab": tab_name, "reason": "no rows"})
            continue
        headers = values[0] if isinstance(values[0], list) else []
        columns = _material_field_map(headers)
        missing_fields = [field for field in MATERIAL_REGISTRY_REQUIRED_FIELDS if columns.get(field) is None]
        if missing_fields:
            invalid_tabs.append({"tab": tab_name, "reason": "missing fields", "missing_fields": missing_fields})
            continue
        tab_rows = [
            _safe_material_registry_row(row, index + 2, columns, tab_name)
            for index, row in enumerate(values[1:])
            if isinstance(row, list)
        ]
        rows.extend([row for row in tab_rows if row.get("material_id") or row.get("title")])

    spreadsheet_title = str((metadata.get("properties") if isinstance(metadata.get("properties"), dict) else {}).get("title") or "NurtureAny material registry")
    spreadsheet_url = MATERIAL_REGISTRY_SPREADSHEET_URL_TEMPLATE.format(spreadsheet_id=selected_spreadsheet_id)
    return {
        "answer": {
            "spreadsheet_title": spreadsheet_title,
            "spreadsheet_url": spreadsheet_url,
            "registry_contract": _material_registry_contract(),
            "rows": rows,
            "row_count": len(rows),
            "missing_tabs": missing_tabs,
            "invalid_tabs": invalid_tabs,
            "next_step": "Use rows as read-only material context only; daily nurture automation is disabled pending refinement.",
        },
        "source": "Google Sheets NurtureAny material registry",
        "scope": {**scope, "tabs": selected_tabs, "requested_limit_per_tab": capped_limit},
        "total": len(rows),
        "requested_limit": capped_limit,
        "returned_count": len(rows),
        "has_more": False,
        "truncated": False,
        "confidence": "needs-check" if missing_tabs or invalid_tabs else "verified",
        "caveat": "Read-only Google Sheet registry. HubSpot remains source of truth for target accounts, ownership, contacts, and follow-up status.",
    }


@mcp.tool()
def read_indonesia_event_registration_attendance(
    slack_user_email: str,
    event_name: str = "",
    event_date: str = "",
    event_tags: list[str] | None = None,
    sheet_name: str = "",
    spreadsheet_id: str = ID_REV_EVENTS_SPREADSHEET_ID,
    limit: int = MAX_REGISTRATION_ROWS,
    row_sample_limit: int = DEFAULT_REGISTRATION_ROW_SAMPLE,
    account_email: str = DEFAULT_ACCOUNT_EMAIL,
) -> dict[str, Any]:
    """Read compact attendance keys from the Indonesia Rev LL/HHH registration Sheet.

    Use only as a manual fallback when Luma checked_in_at attendance is empty or
    not used. The output omits phone numbers and full emails, returns only a
    small safe row sample, and should be matched back to scoped HubSpot target
    accounts before Slack account answers.
    """

    configured_account = _account_email()
    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    selected_spreadsheet_id = (spreadsheet_id or ID_REV_EVENTS_SPREADSHEET_ID).strip()
    capped_limit = max(1, min(int(limit or MAX_REGISTRATION_ROWS), MAX_REGISTRATION_ROWS))
    capped_sample_limit = max(0, min(int(row_sample_limit or 0), MAX_REGISTRATION_ROW_SAMPLE))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "drive_access_mode": "team_oauth_drive_readonly",
            "spreadsheet_id": selected_spreadsheet_id,
            "spreadsheet_title": ID_REV_EVENTS_SPREADSHEET_TITLE,
            "event_name": event_name,
            "event_date": event_date,
            "event_tags": event_tags or [],
            "manual_fallback_for": "Luma checked_in_at empty or not used for Indonesia events",
            "safety": "Compact match keys plus a small safe row sample only. No phone numbers, full emails, raw exports, or Drive mutations.",
        },
    )

    if requested_account != configured_account:
        return _blocked("Google Drive connector is restricted to team@staffany.com.", scope)
    if selected_spreadsheet_id != ID_REV_EVENTS_SPREADSHEET_ID:
        return _blocked("Indonesia event registration fallback is restricted to the ID REV - LL & HHH EVENTS spreadsheet.", scope)

    try:
        access_token = _access_token()
        metadata_params = {"fields": "properties(title),sheets(properties(sheetId,title,index,hidden,gridProperties(rowCount,columnCount)))"}
        try:
            metadata = _request_sheets_json(selected_spreadsheet_id, "", metadata_params, access_token)
        except GoogleDriveError as error:
            if error.status_code != 401:
                raise
            access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
            metadata = _request_sheets_json(selected_spreadsheet_id, "", metadata_params, access_token)
        sheets = metadata.get("sheets") if isinstance(metadata.get("sheets"), list) else []
        selected_sheet = _select_registration_sheet(sheets, sheet_name, event_name, event_date, event_tags)
        if not selected_sheet:
            return _blocked(
                "Could not resolve an Indonesia event registration RSVP tab. Provide sheet_name such as 'HHH Bali 7 May - Rsvp'.",
                scope,
            )
        sheet_props = selected_sheet.get("properties") if isinstance(selected_sheet.get("properties"), dict) else {}
        selected_sheet_name = str(sheet_props.get("title") or "").strip()
        encoded_range = urllib.parse.quote(f"'{selected_sheet_name}'!A1:AE{capped_limit + 2}", safe="")
        values_payload = _request_sheets_json(
            selected_spreadsheet_id,
            f"/values/{encoded_range}",
            {"valueRenderOption": "FORMATTED_VALUE"},
            access_token,
        )
    except GoogleDriveError as error:
        return _blocked(str(error), scope)

    values = values_payload.get("values") if isinstance(values_payload.get("values"), list) else []
    if not values:
        return _blocked("Registration sheet returned no rows.", {**scope, "sheet_name": selected_sheet_name})

    headers = values[0] if isinstance(values[0], list) else []
    columns = _registration_column_map(headers)
    required = ["company_name", "attend_the_event"]
    if any(columns.get(key) is None for key in required):
        return _blocked(
            "Registration sheet is missing required Company Name or Attend The Event columns.",
            {**scope, "sheet_name": selected_sheet_name, "headers": [str(header) for header in headers]},
        )

    raw_rows = [row for row in values[1:] if isinstance(row, list)]
    parsed_rows = [_safe_registration_row(row, index + 2, columns) for index, row in enumerate(raw_rows)]
    parsed_rows = [row for row in parsed_rows if row.get("company_name") or row.get("email_domain")]
    has_more = len(parsed_rows) > capped_limit
    rows = parsed_rows[:capped_limit]
    attended_rows = [row for row in rows if row.get("attended") is True]
    row_sample = attended_rows[:capped_sample_limit]
    email_domains = _unique_limited([str(row.get("email_domain") or "") for row in rows])
    company_candidates = _unique_limited([str(row.get("company_name") or "") for row in rows])
    attended_email_domains = _unique_limited([str(row.get("email_domain") or "") for row in attended_rows])
    attended_company_candidates = _unique_limited([str(row.get("company_name") or "") for row in attended_rows])

    spreadsheet_url = f"{ID_REV_EVENTS_SPREADSHEET_URL}?gid={sheet_props.get('sheetId')}#gid={sheet_props.get('sheetId')}"
    return {
        "answer": {
            "spreadsheet_title": ID_REV_EVENTS_SPREADSHEET_TITLE,
            "spreadsheet_url": spreadsheet_url,
            "sheet_name": selected_sheet_name,
            "attendance_definition": "Attend The Event is TRUE/Yes in the Indonesia registration Sheet",
            "registration_rows_sample": row_sample,
            "registration_rows_returned": len(row_sample),
            "row_details_truncated": len(rows) > len(row_sample),
            "counts": {
                "read_rows": len(rows),
                "attended_rows": len(attended_rows),
                "approved_rows": sum(1 for row in rows if str(row.get("approval_status") or "").lower() == "approved"),
                "wa_confirm_yes_rows": sum(1 for row in rows if str(row.get("wa_confirm") or "").strip().lower() == "yes"),
            },
            "match_keys": {
                "email_domains": attended_email_domains,
                "company_name_candidates": attended_company_candidates,
                "attended_email_domains": attended_email_domains,
                "attended_company_name_candidates": attended_company_candidates,
            },
            "all_rsvp_match_key_counts": {
                "email_domains": len(email_domains),
                "company_name_candidates": len(company_candidates),
            },
            "next_step": "Use attended match keys to resolve scoped HubSpot target accounts before account-level Slack output.",
        },
        "source": "Google Sheets ID Rev events registration attendance fallback",
        "scope": {**scope, "sheet_name": selected_sheet_name, "sheet_id": sheet_props.get("sheetId"), "requested_limit": capped_limit},
        "total": len(parsed_rows),
        "requested_limit": capped_limit,
        "returned_count": len(row_sample),
        "has_more": has_more,
        "truncated": has_more or len(rows) > len(row_sample),
        "confidence": "needs-check",
        "caveat": "Manual registration Sheet fallback only. HubSpot remains required for target-account scope and follow-up status. Output is compact; full emails, phone numbers, and raw registration exports are not returned.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
