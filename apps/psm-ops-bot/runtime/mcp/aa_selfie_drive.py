"""Google Drive selfie uploader for Event AA intake.

Best-effort: when the configured Drive folder or OAuth creds are missing, every
function returns an empty result so the Event AA intake path is never blocked.
"""

from __future__ import annotations

import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from google_oauth import (
    access_token as _google_access_token,
    profile_file as _google_profile_file,
    safe_detail,
)


DRIVE_API_BASE_URL = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_BASE_URL = "https://www.googleapis.com/upload/drive/v3"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_BROAD_SCOPE = "https://www.googleapis.com/auth/drive"
DRIVE_ALLOWED_SCOPES = {DRIVE_FILE_SCOPE, DRIVE_BROAD_SCOPE}
DRIVE_USER_AGENT = "StaffAny-PSMOps-AA/1.0 (+https://staffany.com)"
DRIVE_TIMEOUT_SECONDS = 30
DEFAULT_AA_SELFIE_DRIVE_FOLDER_ID = "1hxeLDkyLLoVwuKCBPTjLK7ypnZTB9xHc"


class AaSelfieDriveError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _drive_folder_id() -> str:
    return os.environ.get("PSM_OPS_AA_SELFIE_DRIVE_FOLDER_ID", "").strip() or DEFAULT_AA_SELFIE_DRIVE_FOLDER_ID


def _drive_token_path() -> Path:
    return _google_profile_file("PSM_OPS_DRIVE_TOKEN_FILE", "drive-token.json")


def _drive_client_secret_path() -> Path:
    return _google_profile_file("PSM_OPS_DRIVE_CLIENT_SECRET_FILE", "drive-client-secret.json")


def _is_configured() -> bool:
    if not _drive_folder_id():
        return False
    token_path = _drive_token_path()
    return token_path.exists()


def _drive_access_token() -> str:
    return _google_access_token(
        _drive_token_path(),
        _drive_client_secret_path(),
        DRIVE_ALLOWED_SCOPES,
        DRIVE_USER_AGENT,
        DRIVE_TIMEOUT_SECONDS,
        "Drive",
        AaSelfieDriveError,
    )


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip()).strip("-")
    return cleaned.lower() or "unknown"


def _extension_for(name: str, mimetype: str) -> str:
    fallback = ".jpg"
    if name and "." in name:
        ext = "." + name.rsplit(".", 1)[-1].strip().lower()
        if 2 <= len(ext) <= 6 and re.fullmatch(r"\.[a-z0-9]+", ext):
            return ext
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/heic": ".heic",
        "image/heif": ".heif",
        "image/webp": ".webp",
    }
    return mapping.get((mimetype or "").lower(), fallback)


def _build_filename(company: str, pic: str, mimetype: str, original_name: str, sequence: int) -> str:
    ext = _extension_for(original_name, mimetype)
    base = f"{_slugify(company)}_{_slugify(pic)}"
    if sequence > 1:
        base = f"{base}-{sequence}"
    return f"{base}{ext}"


def _multipart_body(metadata: dict[str, Any], content: bytes, mimetype: str, boundary: str) -> bytes:
    import json as _json

    metadata_part = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{_json.dumps(metadata)}\r\n"
    ).encode("utf-8")
    media_part_header = (
        f"--{boundary}\r\n"
        f"Content-Type: {mimetype or 'application/octet-stream'}\r\n\r\n"
    ).encode("utf-8")
    closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return metadata_part + media_part_header + content + closing


def _upload_one(content: bytes, filename: str, mimetype: str, token: str) -> dict[str, Any]:
    import json as _json

    boundary = f"----PsmOpsAaSelfieBoundary{uuid.uuid4().hex}"
    metadata = {
        "name": filename,
        "parents": [_drive_folder_id()],
    }
    body = _multipart_body(metadata, content, mimetype, boundary)
    url = (
        f"{DRIVE_UPLOAD_BASE_URL}/files?uploadType=multipart"
        "&fields=id%2Cname%2CwebViewLink"
    )
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": f"multipart/related; boundary={boundary}",
            "user-agent": DRIVE_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DRIVE_TIMEOUT_SECONDS) as response:
            payload = _json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AaSelfieDriveError(
            f"Drive upload failed: {error.code} {safe_detail(detail)}",
            error.code,
        ) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise AaSelfieDriveError(f"Drive upload timed out or failed: {reason}") from error
    return {
        "drive_file_id": str(payload.get("id") or ""),
        "name": str(payload.get("name") or filename),
        "web_view_link": str(payload.get("webViewLink") or ""),
    }


def upload_aa_selfies(
    images: list[dict[str, Any]],
    company: str,
    pic: str,
) -> list[dict[str, Any]]:
    """Upload selfie images to the configured Drive folder.

    Each ``images`` entry must include ``content`` (bytes), ``name`` (original
    filename), and ``mimetype``. Returns the per-file Drive metadata on success.
    Returns an empty list when Drive is not configured or no images are given.
    Silently swallows per-file errors so AA intake creation is never blocked.
    """

    if not images or not _is_configured():
        return []
    try:
        token = _drive_access_token()
    except AaSelfieDriveError:
        return []
    uploaded: list[dict[str, Any]] = []
    sequence = 0
    for entry in images:
        sequence += 1
        content = entry.get("content") if isinstance(entry, dict) else None
        if not isinstance(content, (bytes, bytearray)) or not content:
            continue
        mimetype = str(entry.get("mimetype") or "image/jpeg")
        original_name = str(entry.get("name") or "selfie")
        filename = _build_filename(company, pic, mimetype, original_name, sequence)
        try:
            uploaded.append(_upload_one(bytes(content), filename, mimetype, token))
        except AaSelfieDriveError:
            continue
    return uploaded
