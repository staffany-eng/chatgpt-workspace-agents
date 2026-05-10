#!/usr/bin/env python3
"""Read-only Google Drive MCP adapter for NurtureAny Sales Bot.

This server lists bounded image metadata from the StaffAny team@staffany.com
Drive account and can transiently inspect Drive images for OCR/vision clues. It
never exports files, mutates Drive, or stores raw image bytes.
"""

from __future__ import annotations

import base64
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
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
GOOGLE_DRIVE_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DEFAULT_ACCOUNT_EMAIL = "team@staffany.com"
DEFAULT_DRIVE_FOLDER_ID = "1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-"
GOOGLE_DRIVE_TIMEOUT_SECONDS = 15
MAX_DRIVE_FILES = 100
MAX_VISION_FILES = 5
MAX_IMAGE_BYTES = 7_500_000
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_VISION_MODEL = "claude-sonnet-4-6"
SUPPORTED_VISION_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
SLACK_API_BASE_URL = "https://slack.com/api"
SLACK_BOT_TOKEN_ENV = "SLACK_BOT_TOKEN"
SLACK_USER_ID_PATTERN = re.compile(r"^[UW][A-Z0-9]+$")
SLACK_EXPORT_FILENAME_PATTERN = re.compile(
    r"^(?P<source_timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)-(?P<slack_user_id>[UW][A-Z0-9]+)-(?P<original_filename>.+)$"
)
_SLACK_USER_CACHE: dict[str, dict[str, str]] = {}


mcp = FastMCP(
    "google_drive_nurtureany",
    instructions=(
        "Read-only Google Drive photo metadata for NurtureAny. Use only the "
        "team@staffany.com account, list bounded image metadata, extract transient vision/OCR clues, "
        "and never store raw images or mutate Drive files."
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


def _media_type_for_image(metadata: dict[str, Any], downloaded_media_type: str = "") -> str:
    media_type = (downloaded_media_type or metadata.get("mimeType") or metadata.get("mime_type") or "").strip().lower()
    if media_type == "image/jpg":
        return "image/jpeg"
    return media_type


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


if __name__ == "__main__":
    mcp.run("stdio")
