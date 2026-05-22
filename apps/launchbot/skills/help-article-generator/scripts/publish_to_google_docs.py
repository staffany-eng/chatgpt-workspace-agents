#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Google Doc from an HTML file using Drive import."
    )
    parser.add_argument("--html", "-i", required=True, help="Path to input HTML file")
    parser.add_argument("--title", "-t", required=True, help="Google Doc title")
    parser.add_argument(
        "--credentials",
        "-c",
        required=True,
        help="OAuth client credentials JSON downloaded from Google Cloud console",
    )
    parser.add_argument(
        "--token",
        default="apps/launchbot/skills/help-article-generator/.tokens/google-token.json",
        help="Token cache file path (default: skill-local token cache)",
    )
    parser.add_argument(
        "--folder-id",
        default="",
        help="Optional Drive folder id for the created Google Doc",
    )
    return parser.parse_args()


def load_services(credentials_path: Path, token_path: Path) -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=creds)


def create_google_doc(
    drive_service: Any,
    html_path: Path,
    title: str,
    folder_id: str,
) -> dict[str, str]:
    from googleapiclient.http import MediaFileUpload

    metadata: dict[str, Any] = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaFileUpload(str(html_path), mimetype="text/html", resumable=False)
    doc = (
        drive_service.files()
        .create(body=metadata, media_body=media, fields="id,name,webViewLink")
        .execute()
    )

    return {
        "id": doc.get("id", ""),
        "name": doc.get("name", title),
        "url": doc.get("webViewLink", ""),
    }


def main() -> int:
    args = parse_args()
    html_path = Path(args.html)
    credentials_path = Path(args.credentials)
    token_path = Path(args.token)

    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    if not credentials_path.exists():
        raise FileNotFoundError(f"Credentials file not found: {credentials_path}")

    drive_service = load_services(credentials_path, token_path)
    doc = create_google_doc(
        drive_service=drive_service,
        html_path=html_path,
        title=args.title,
        folder_id=args.folder_id,
    )

    print(json.dumps(doc, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
