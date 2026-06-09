#!/usr/bin/env python3
"""
google_sa.py — Google API helper using Launchbot service account credentials.

Reads GOOGLE_SERVICE_ACCOUNT_EMAIL, GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY,
GOOGLE_SERVICE_ACCOUNT_TOKEN_URI from /home/leekaiyi/.hermes/profiles/launchbot/.env

Usage:
  python google_sa.py docs get <DOC_ID>
  python google_sa.py sheets get <SHEET_ID> <RANGE>
  python google_sa.py sheets list <SHEET_ID>
  python google_sa.py drive get <FILE_ID>
  python google_sa.py drive search <query>

Output: JSON to stdout.
"""

import sys
import json
import os
import re

ENV_FILE = "/home/leekaiyi/.hermes/profiles/launchbot/.env"

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def load_env():
    env = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_credentials():
    from google.oauth2 import service_account

    env = load_env()
    email = env.get("GOOGLE_SERVICE_ACCOUNT_EMAIL", "")
    raw_key = env.get("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY", "")
    token_uri = env.get("GOOGLE_SERVICE_ACCOUNT_TOKEN_URI", "https://oauth2.googleapis.com/token")

    if not email or not raw_key:
        raise ValueError("Missing GOOGLE_SERVICE_ACCOUNT_EMAIL or GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY in .env")

    # Unescape \\n → actual newlines if stored as single-line string
    private_key = raw_key.replace("\\n", "\n")

    info = {
        "type": "service_account",
        "client_email": email,
        "private_key": private_key,
        "token_uri": token_uri,
    }
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def build_service(api, version):
    from googleapiclient.discovery import build
    creds = get_credentials()
    return build(api, version, credentials=creds)


# ── Docs ──────────────────────────────────────────────────────────────────────

def docs_get(doc_id):
    svc = build_service("docs", "v1")
    doc = svc.documents().get(documentId=doc_id).execute()

    # Extract plain text from body
    text_parts = []
    body = doc.get("body", {}).get("content", [])
    for block in body:
        para = block.get("paragraph")
        if para:
            for el in para.get("elements", []):
                tr = el.get("textRun")
                if tr:
                    text_parts.append(tr.get("content", ""))

    return {
        "doc_id": doc_id,
        "title": doc.get("title", ""),
        "text": "".join(text_parts),
        "raw": doc,
    }


# ── Sheets ────────────────────────────────────────────────────────────────────

def sheets_get(sheet_id, range_notation):
    svc = build_service("sheets", "v4")
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_notation
    ).execute()
    return {
        "sheet_id": sheet_id,
        "range": result.get("range"),
        "values": result.get("values", []),
    }


def sheets_list(sheet_id):
    svc = build_service("sheets", "v4")
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheets = [
        {"title": s["properties"]["title"], "sheetId": s["properties"]["sheetId"]}
        for s in meta.get("sheets", [])
    ]
    return {"sheet_id": sheet_id, "title": meta.get("properties", {}).get("title"), "sheets": sheets}


# ── Drive ─────────────────────────────────────────────────────────────────────

def drive_get(file_id):
    svc = build_service("drive", "v3")
    meta = svc.files().get(fileId=file_id, fields="id,name,mimeType,modifiedTime,webViewLink").execute()
    return meta


def drive_search(query, max_results=20):
    svc = build_service("drive", "v3")
    result = svc.files().list(
        q=query,
        pageSize=max_results,
        fields="files(id,name,mimeType,modifiedTime,webViewLink)",
    ).execute()
    return {"files": result.get("files", [])}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "Usage: google_sa.py <service> <action> [args...]"}))
        sys.exit(1)

    service = args[0]
    action = args[1] if len(args) > 1 else ""

    try:
        if service == "docs" and action == "get":
            print(json.dumps(docs_get(args[2]), ensure_ascii=False, indent=2))
        elif service == "sheets" and action == "get":
            print(json.dumps(sheets_get(args[2], args[3]), ensure_ascii=False, indent=2))
        elif service == "sheets" and action == "list":
            print(json.dumps(sheets_list(args[2]), ensure_ascii=False, indent=2))
        elif service == "drive" and action == "get":
            print(json.dumps(drive_get(args[2]), ensure_ascii=False, indent=2))
        elif service == "drive" and action == "search":
            max_r = int(args[3]) if len(args) > 3 else 20
            print(json.dumps(drive_search(args[2], max_r), ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"error": f"Unknown command: {service} {action}"}))
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
