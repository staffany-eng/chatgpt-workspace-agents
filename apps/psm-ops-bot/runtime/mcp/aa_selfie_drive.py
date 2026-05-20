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
    load_json,
    profile_file as _google_profile_file,
    safe_detail,
    token_scopes,
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


def configuration_status() -> tuple[str, str]:
    """Return a structured Drive configuration status: (code, human-readable reason).

    Codes: ``ok`` (ready to upload), ``missing_folder_id`` (no folder configured
    and no default), ``missing_token`` (folder fine but the OAuth token file is
    absent). The reason string is safe to surface in Slack replies.
    """

    if not _drive_folder_id():
        return "missing_folder_id", "Drive folder ID is not configured."
    token_path = _drive_token_path()
    if not token_path.exists():
        return "missing_token", f"Drive OAuth token file missing at {token_path}."
    return "ok", ""


def _is_configured() -> bool:
    return configuration_status()[0] == "ok"


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


def _build_filename(
    company: str,
    pic: str,
    mimetype: str,
    original_name: str,
    sequence: int,
    slack_file_id: str = "",
) -> str:
    ext = _extension_for(original_name, mimetype)
    base = f"{_slugify(company)}_{_slugify(pic)}"
    if slack_file_id:
        return f"{base}__{slack_file_id}{ext}"
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
    metadata: dict[str, Any] = {
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


def health_check() -> dict[str, Any]:
    """Diagnose Drive OAuth without uploading anything.

    Steps: configuration status, refresh-token attempt, then a single
    ``GET /about?fields=user,storageQuota`` call to confirm the access token
    actually works against Drive. Returns a structured dict so the bot can
    quote the failure cause verbatim instead of guessing.

    ``status`` values:
      - ``ok`` — refresh succeeded and the ``/about`` ping returned 200.
      - ``missing_folder_id`` / ``missing_token`` — pre-flight configuration miss.
      - ``refresh_failed`` — the refresh-token call to Google was rejected
        (revoked grant, wrong client secret, expired refresh token).
      - ``api_unauthorized`` — refresh succeeded but Drive rejected the access
        token (scope mismatch, account disabled).
      - ``api_failed`` — refresh succeeded but the ``/about`` call failed for a
        non-auth reason (network, 5xx).
    """

    folder_id = _drive_folder_id()
    token_path = _drive_token_path()
    out: dict[str, Any] = {
        "status": "ok",
        "reason": "",
        "folder_id": folder_id,
        "token_path": str(token_path),
        "user_email": "",
        "scopes": [],
    }
    status_code, status_reason = configuration_status()
    if status_code != "ok":
        out["status"] = status_code
        out["reason"] = status_reason
        return out
    try:
        token = _drive_access_token()
    except AaSelfieDriveError as error:
        out["status"] = "refresh_failed"
        out["reason"] = (
            "Google rejected the refresh-token exchange. Re-run the Drive "
            "OAuth setup to mint a fresh refresh_token."
        )
        out["last_error"] = str(error)
        return out

    request = urllib.request.Request(
        f"{DRIVE_API_BASE_URL}/about?fields=user(emailAddress),storageQuota",
        headers={
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "user-agent": DRIVE_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=DRIVE_TIMEOUT_SECONDS) as response:
            import json as _json

            payload = _json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code in (401, 403):
            out["status"] = "api_unauthorized"
            out["reason"] = (
                f"Drive rejected the refreshed access token ({error.code}). "
                "Likely scope mismatch or revoked account."
            )
        else:
            out["status"] = "api_failed"
            out["reason"] = f"Drive /about returned {error.code}."
        out["last_error"] = safe_detail(detail)
        return out
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        out["status"] = "api_failed"
        reason = getattr(error, "reason", error)
        out["reason"] = f"Drive /about call could not complete: {reason}."
        out["last_error"] = str(reason)
        return out

    user = payload.get("user") if isinstance(payload, dict) else None
    if isinstance(user, dict):
        out["user_email"] = str(user.get("emailAddress") or "")
    # The token file may now carry a fresh scope payload if a refresh happened.
    try:
        cached = load_json(token_path, "Drive", AaSelfieDriveError)
        out["scopes"] = sorted(token_scopes(cached))
    except AaSelfieDriveError:
        pass
    return out


def upload_aa_selfies_detailed(
    images: list[dict[str, Any]],
    company: str,
    pic: str,
) -> dict[str, Any]:
    """Upload selfies to Drive and return a structured result.

    Returns ``{"uploaded": list[dict], "drive_status": str,
    "drive_reason": str, "failure_count": int, "last_error": str}``.
    ``drive_status`` mirrors :func:`configuration_status` codes plus
    ``upload_failed`` (config OK but every upload errored). Callers should
    surface ``drive_reason`` / ``last_error`` verbatim instead of inventing
    a cause when the upload returns fewer items than were submitted.
    Never raises: every error is captured so the caller can stay on the
    create-first path.
    """

    if not images:
        return {
            "uploaded": [],
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
    status_code, status_reason = configuration_status()
    if status_code != "ok":
        return {
            "uploaded": [],
            "drive_status": status_code,
            "drive_reason": status_reason,
            "failure_count": 0,
            "last_error": "",
        }
    try:
        token = _drive_access_token()
    except AaSelfieDriveError as error:
        return {
            "uploaded": [],
            "drive_status": "auth_failed",
            "drive_reason": "Drive OAuth token could not be refreshed.",
            "failure_count": 0,
            "last_error": str(error),
        }

    uploaded: list[dict[str, Any]] = []
    failure_count = 0
    last_error = ""
    sequence = 0
    for entry in images:
        sequence += 1
        content = entry.get("content") if isinstance(entry, dict) else None
        if not isinstance(content, (bytes, bytearray)) or not content:
            failure_count += 1
            last_error = last_error or "Skipped image with empty content."
            continue
        mimetype = str(entry.get("mimetype") or "image/jpeg")
        original_name = str(entry.get("name") or "selfie")
        slack_file_id = str(entry.get("slack_file_id") or "")
        filename = _build_filename(
            company,
            pic,
            mimetype,
            original_name,
            sequence,
            slack_file_id=slack_file_id,
        )
        try:
            uploaded.append(_upload_one(bytes(content), filename, mimetype, token))
        except AaSelfieDriveError as error:
            failure_count += 1
            last_error = str(error)
            continue
    drive_status = "ok" if uploaded else ("upload_failed" if failure_count else "ok")
    drive_reason = "" if uploaded else last_error
    return {
        "uploaded": uploaded,
        "drive_status": drive_status,
        "drive_reason": drive_reason,
        "failure_count": failure_count,
        "last_error": last_error,
    }


def upload_aa_selfies(
    images: list[dict[str, Any]],
    company: str,
    pic: str,
) -> list[dict[str, Any]]:
    """Backwards-compatible thin wrapper returning only the uploaded list.

    Prefer :func:`upload_aa_selfies_detailed` so callers can surface the real
    Drive failure reason instead of guessing.
    """

    return upload_aa_selfies_detailed(images, company, pic)["uploaded"]
